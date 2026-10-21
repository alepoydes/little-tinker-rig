import json
from unittest.mock import patch

import pytest

from little_tinker_rig.core.snippets import (
    builtin_snippets,
    load_module,
    snippet_groups,
)
from little_tinker_rig.i18n import DEFAULT_LANGUAGE, language, set_language, tr


def block_position(browser, title):
    from PySide6.QtGui import QTextCursor

    block = browser.document().begin()
    while block.isValid():
        if block.blockFormat().headingLevel() == 2 and block.text() == title:
            return browser.cursorRect(QTextCursor(block)).top()
        block = block.next()
    raise AssertionError(f"Heading not found: {title}")


def test_english_source_and_russian_catalog():
    assert DEFAULT_LANGUAGE == language() == "en"
    assert tr("Run") == "Run"
    set_language("ru")
    assert tr("Run") == "Запустить"
    assert (
        tr("Save {p0} before closing?", p0="report.py")
        == "Сохранить report.py перед закрытием?"
    )
    assert tr("An untranslated message") == "An untranslated message"
    with pytest.raises(ValueError):
        set_language("unknown")
    assert language() == "ru"


@pytest.mark.parametrize(
    "code, labels",
    [
        ("en", ("Programs and lessons", "Robot instructions", "Firmware")),
        ("ru", ("Программы и уроки", "Инструкция сборки робота", "Прошивка")),
    ],
)
def test_file_dialog_filters_translate_labels_without_changing_extensions(
    tmp_path, qt_app, code, labels
):
    from PySide6.QtWidgets import QFileDialog

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.firmware import FirmwareDialog

    path = tmp_path / "program.py"
    path.write_text("print('ready')\n", encoding="utf-8")
    set_language(code)
    window = Studio(path)
    window.confirm_close = lambda *_: True
    filters = []

    def record_files(*args):
        filters.append(args[3])
        return [], ""

    def record_file(*args):
        filters.append(args[3])
        return "", ""

    try:
        with (
            patch.object(QFileDialog, "getOpenFileNames", side_effect=record_files),
            patch.object(QFileDialog, "getOpenFileName", side_effect=record_file),
        ):
            window.open_file()
            window.lessons.assembly_host.choose()
            dialog = FirmwareDialog(window)
            dialog.open_local()
            dialog.close()
        assert filters == [
            f"{labels[0]} (*.py *.ltr *.pylesson *.pyblocks);;"
            "Python (*.py);;LittleTinker Rig (*.ltr *.pylesson *.pyblocks)",
            f"{labels[1]} (*.json)",
            f"{labels[2]} (*.zip *.bin)",
        ]
    finally:
        window.close()


def test_parameter_validation_is_localized_without_changing_source(tmp_path, qt_app):
    from little_tinker_rig.core.session import Session
    from little_tinker_rig.qt.editor import SourceView

    path = tmp_path / "main.py"
    path.write_text("counter = 1\n")
    session = Session(path)
    view = SourceView(session)
    view.show()
    qt_app.processEvents()
    set_language("ru")
    try:
        before = session.document.state
        slot = next(s for s in view.parameter_slots if s.binding)
        view.show_parameter(slot)
        view.parameter_editor.line_edit.setText("not valid")
        assert not view.parameter_editor.apply()
        assert view.parameter_editor.error == tr("Enter a Python identifier")
        assert view.parameter_editor.error != "Enter a Python identifier"
        assert session.document.state is before
    finally:
        view.close()


def test_rename_preserves_settings_without_overwriting_new_preferences(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtCore import QSettings

    from little_tinker_rig.qt import app

    previous = QSettings(str(tmp_path / "old.ini"), QSettings.Format.IniFormat)
    current = QSettings(str(tmp_path / "new.ini"), QSettings.Format.IniFormat)
    previous.setValue("language", "ru")
    previous.setValue("windowMaximized", True)
    monkeypatch.setattr(
        app,
        "QSettings",
        lambda organization, _: previous if organization == "PyBlocks" else current,
    )
    restored = app.application_settings()
    assert restored.value("language") == "ru"
    assert restored.value("windowMaximized", type=bool)
    restored.setValue("language", "en")
    assert app.application_settings().value("language") == "en"
    assert previous.value("language") == "ru"


@pytest.mark.parametrize(
    "stored, expected", [(None, "en"), ("ru", "ru"), ("invalid", "en")]
)
def test_launch_preserves_language_choice(tmp_path, qt_app, stored, expected):
    from PySide6.QtCore import QTimer

    from little_tinker_rig.qt.app import QSettings, launch

    settings = QSettings()
    if stored is not None:
        settings.setValue("language", stored)

    observed = []

    def inspect_window():
        from little_tinker_rig.qt.app import Studio

        window = next(
            w
            for w in qt_app.topLevelWidgets()
            if isinstance(w, Studio) and w.isVisible()
        )
        observed.append(
            (language(), window.modes.item(0).text(), window.help_page.root.name)
        )
        window.close()
        qt_app.quit()

    QTimer.singleShot(0, inspect_window)
    launch(tmp_path / "main.py")
    assert observed == [
        (expected, "Программа" if expected == "ru" else "Program", expected)
    ]


def test_help_groups_links_back_search_and_language(qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.help import HelpPage

    snippets = builtin_snippets()
    page = HelpPage(snippets)
    page.resize(1100, 760)
    page.show()
    qt_app.processEvents()
    try:
        groups = page.tree.topLevelItem(1)
        page.tree.setCurrentItem(groups)
        assert page.current == "index.md"
        assert groups.childCount() == len(snippet_groups(snippets))
        assert all(
            groups.child(i).childCount() == 0 for i in range(groups.childCount())
        )
        page.show_page("pybricks/motors/motor_speed")
        qt_app.processEvents()
        assert page.current == "library/pybricks/motors#motor_speed"
        text = page.browser.toPlainText()
        motors = snippet_groups(snippets)["pybricks/motors"]
        assert all(tr(s.help).splitlines()[0] in text for s in motors)
        assert (
            0
            <= block_position(page.browser, "Motor speed")
            < page.browser.viewport().height()
        )
        page.browser.verticalScrollBar().setValue(0)
        cursor = page.browser.document().find("Connect motor")
        cursor.setPosition(cursor.selectionStart() + 5)
        point = page.browser.cursorRect(cursor).center()
        assert page.browser.anchorAt(point) == "#create_motor"
        QTest.mouseClick(page.browser.viewport(), Qt.MouseButton.LeftButton, pos=point)
        assert page.current.endswith("#create_motor")
        assert (
            0
            <= block_position(page.browser, "Connect motor")
            < page.browser.viewport().height()
        )
        page.back()
        assert page.current == "index.md"
        page.show_page("pybricks/motors/motor_speed")
        page.search.setText("run_target")
        assert not page.tree.currentItem().isHidden()
        visible = {
            groups.child(i).data(0, Qt.ItemDataRole.UserRole)
            for i in range(groups.childCount())
            if not groups.child(i).isHidden()
        }
        assert {
            "library/pybricks/motors",
            "library/pybricks/lessons",
            "library/pybricks/remote",
        } <= visible
        assert "library/python/basics" not in visible
        set_language("ru")
        page.retranslate()
        qt_app.processEvents()
        assert page.current == "library/pybricks/motors#motor_speed"
        assert page.root.name == "ru"
        assert "Моторы" in page.tree.currentItem().text(0)
        assert not page.tree.currentItem().isHidden()
        groups = page.tree.topLevelItem(1)
        assert {
            groups.child(i).data(0, Qt.ItemDataRole.UserRole)
            for i in range(groups.childCount())
            if not groups.child(i).isHidden()
        } == visible
        assert (
            0
            <= block_position(page.browser, "Скорость мотора")
            < page.browser.viewport().height()
        )
        page.show_page("usage.md")
        assert not page.search.text()
        assert not page.tree.currentItem().isHidden()
        page.search.setText("no-such-help-topic-123")
        assert page.no_results.isVisible()
        current = page.current
        page.search.setFocus()
        QTest.keyClick(page.search, Qt.Key.Key_Escape)
        assert not page.no_results.isVisible() and not page.search.text()
        assert page.current == current
        set_language("en")
        page.retranslate()
        assert (
            page.current == "usage.md"
            and "Editing and command-line tools" in page.browser.toPlainText()
        )
        page.show_page("robotics.md#delivery-robot")
        qt_app.processEvents()
        assert (
            0
            <= block_position(page.browser, "Delivery robot")
            < page.browser.viewport().height()
        )
    finally:
        page.close()


def test_help_page_change_keeps_find_query_without_skipping_first_match(qt_app):
    from little_tinker_rig.qt.help import HelpPage

    page = HelpPage(builtin_snippets())
    page.resize(1100, 760)
    page.show()
    qt_app.processEvents()
    try:
        page.show_page("usage.md")
        page.find_field.setText("block")
        assert page.find_index == 0

        page.show_page("index.md")
        assert len(page.find_matches) > 1
        assert page.find_count.text() == f"0/{len(page.find_matches)}"
        page.next_match(1)
        assert page.find_index == 0
        page.show_page("index.md#learn-and-build")
        qt_app.processEvents()
        assert (
            0
            <= block_position(page.browser, "Learn and build")
            < page.browser.viewport().height()
        )
        assert page.find_count.text() == f"0/{len(page.find_matches)}"
        page.next_match(1)
        assert page.find_index == 0

        page.show_page("usage.md")
        page.next_match(-1)
        assert page.find_index == len(page.find_matches) - 1
    finally:
        page.close()


def test_help_search_restores_branches_and_keeps_new_destination_visible(qt_app):
    from little_tinker_rig.qt.help import HelpPage

    page = HelpPage(builtin_snippets())
    page.resize(900, 600)
    page.show()
    qt_app.processEvents()
    try:
        guide = page.tree.topLevelItem(0)
        library = page.tree.topLevelItem(1)
        guide.setExpanded(False)
        library.setExpanded(False)

        page.search.setText("run_target")
        assert library.isExpanded()
        page.search.setText("no-such-help-topic-123")
        assert page.no_results.isVisible()
        page.search.clear()
        assert not guide.isExpanded()
        assert not library.isExpanded()
        assert not page.no_results.isVisible()

        page.search.setText("run_target")
        destination = page.pages["library/pybricks/motors"][1]
        assert not destination.isHidden()
        page.show_page("library/pybricks/motors")
        page.search.clear()
        assert not guide.isExpanded()
        assert library.isExpanded()
        assert page.tree.currentItem() is destination
    finally:
        page.close()


def test_help_language_switch_keeps_current_page_visible_when_search_changes(qt_app):
    from little_tinker_rig.qt.help import HelpPage

    previous_language = language()
    set_language("en")
    page = HelpPage([])
    page.show()
    qt_app.processEvents()
    try:
        page.search.setText("Learn and build")
        assert not page.tree.currentItem().isHidden()

        set_language("ru")
        page.retranslate()
        assert page.current == "index.md"
        assert page.tree.currentItem() is page.pages["index.md"][1]
        assert not page.tree.currentItem().isHidden()
        assert not page.search.text()
        assert not page.no_results.isVisible()

        page.search.setText("LittleTinker Rig")
        set_language("en")
        page.retranslate()
        assert page.search.text() == "LittleTinker Rig"
        assert not page.tree.currentItem().isHidden()
    finally:
        page.close()
        set_language(previous_language)


@pytest.mark.parametrize("query", ["run_target", "no-such-help-topic-123"])
def test_help_content_refresh_preserves_discovery_and_reading_position(qt_app, query):
    from little_tinker_rig.qt.help import HelpPage

    page = HelpPage(builtin_snippets())
    page.resize(900, 600)
    page.show()
    qt_app.processEvents()
    try:
        page.show_page("usage.md")
        page.find_field.setText("block")
        page.next_match(1)
        page.browser.verticalScrollBar().setValue(400)
        for index in (0, 1):
            page.tree.topLevelItem(index).setExpanded(False)
        page.search.setText(query)
        history, recent = page.history[:], page.recent_pages[:]
        scroll = page.browser.verticalScrollBar().value()
        count = page.find_count.text()
        page.snippets = (
            *page.snippets,
            *load_module(
                "def fresh(value=1):\n    return value\n", "custom/fresh", "1"
            ),
        )
        page.refresh_contents()
        assert page.current == "usage.md"
        assert page.search.text() == query
        assert (page.history, page.recent_pages) == (history, recent)
        assert page.browser.verticalScrollBar().value() == scroll
        assert page.find_field.text() == "block" and page.find_count.text() == count
        assert "library/custom/fresh" in page.pages
        assert page.no_results.isVisible() == query.startswith("no-such")
        page.search.clear()
        assert not page.tree.topLevelItem(0).isExpanded()
        assert not page.tree.topLevelItem(1).isExpanded()
    finally:
        page.close()


def test_help_search_enter_opens_visible_result_and_preserves_miss(qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.help import HelpPage

    page = HelpPage(builtin_snippets())
    page.show()
    qt_app.processEvents()
    try:
        page.search.setText("crw-rw----")
        assert page.current == "index.md"
        assert not page.pages["usb.md"][1].isHidden()
        page.search.setFocus()
        QTest.keyClick(page.search, Qt.Key.Key_Return)
        assert page.current == "usb.md"
        assert page.tree.hasFocus()

        page.search.setText("no-such-help-topic-123")
        page.search.setFocus()
        QTest.keyClick(page.search, Qt.Key.Key_Return)
        assert page.current == "usb.md"
        assert page.search.hasFocus()

        QTest.keyClick(page.search, Qt.Key.Key_Escape)
        assert not page.search.text()
        assert page.tree.hasFocus()
    finally:
        page.close()


def test_help_custom_group_without_docstring_excludes_historical_versions(qt_app):
    from little_tinker_rig.qt.help import HelpPage

    source = "def twice(value=2):\n    return value * 2\n"
    current = load_module(source, "custom/math", "2")
    history = load_module(source, "custom/math", "1", historical=True)
    page = HelpPage(current + history)
    try:
        page.show_page("custom/math/twice")
        assert page.current == "library/custom/math#twice"
        assert page.tree.topLevelItem(1).childCount() == 1
        assert page.browser.toPlainText().count("value * 2") == 1
        assert "value" in page.browser.toPlainText()
    finally:
        page.close()


def test_documentation_anchor_names_match_rendered_sections(qt_app):
    from little_tinker_rig.documentation import heading_anchors
    from little_tinker_rig.qt.help import HelpPage

    text = '# Test\n\n## `Motor.run` and **speed**\n\n## Повтор\n\n## Повтор\n\n```python\n# ignored\n```\n\n<a name="stable-id"></a>\n\n## [Final](index.md)\n'
    assert list(heading_anchors(text)) == [
        ["test"],
        ["motorrun-and-speed"],
        ["повтор"],
        ["повтор-1"],
        ["final", "stable-id"],
    ]
    snippets = load_module(
        'def twice(value=2):\n    """Repeat **twice**.\n\nDouble the input.\n    """\n    return value * 2\n',
        "custom/math",
        "1",
    )
    page = HelpPage(snippets)
    page.resize(900, 500)
    page.show()
    try:
        page.show_page("custom/math/twice")
        qt_app.processEvents()
        assert (
            0
            <= block_position(page.browser, "Repeat twice.")
            < page.browser.viewport().height()
        )
    finally:
        page.close()


def test_help_fallback_keeps_page_identity_and_resolves_relative_links(
    tmp_path, qt_app
):
    from PySide6.QtCore import QUrl

    from little_tinker_rig.qt.help import HelpPage

    en, ru = tmp_path / "en", tmp_path / "ru"
    en.mkdir()
    ru.mkdir()
    (en / "index.md").write_text("# English index\n\n[Next](next.md)\n")
    (en / "next.md").write_text("# Next page\n\n[Home](index.md)\n")
    (ru / "next.md").write_text("# Следующая страница\n\n[Домой](index.md)\n")
    set_language("ru")
    page = HelpPage(())
    try:
        page.base_root = tmp_path
        page.retranslate()
        assert page.current == "index.md"
        assert "English index" in page.browser.toPlainText()
        page.follow_link(QUrl("next.md"))
        assert "Следующая страница" in page.browser.toPlainText()
        assert page.current == "next.md"
        page.follow_link(QUrl("index.md"))
        assert page.current == "index.md"
        page.back()
        assert page.current == "next.md"
    finally:
        page.close()


def test_switching_language_preserves_scratch_widgets_and_user_text(tmp_path, qt_app):
    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.scratch import Grip

    set_language("ru")
    window = Studio(tmp_path / "Program.py")
    window.session.set_scratch(None, 'message = "Program — Программа"\n')
    window.refresh_views()
    cell = window.scratch.cells[0]
    before = window.session.document.state
    try:
        assert cell.blocks_button.toolTip() == "Блоки"
        assert cell.blocks_button.accessibleName() == "Блоки"
        assert cell.code_button.accessibleName() == "Python"
        assert cell.findChild(Grip).accessibleName() == cell.findChild(Grip).toolTip()
        set_language("en")
        window.retranslate()
        assert window.scratch.cells[0] is cell
        assert cell.blocks_button.toolTip() == "Blocks"
        assert cell.blocks_button.accessibleName() == "Blocks"
        assert cell.code_button.accessibleName() == "Python"
        assert cell.findChild(Grip).toolTip().startswith("Drag the whole fragment")
        assert cell.findChild(Grip).accessibleName() == cell.findChild(Grip).toolTip()
        assert window.session.document.state is before
        assert "Program.py" in window.windowTitle()
        set_language("ru")
        window.retranslate()
        assert cell.blocks_button.toolTip() == "Блоки"
        assert cell.blocks_button.accessibleName() == "Блоки"
        assert cell.findChild(Grip).accessibleName() == cell.findChild(Grip).toolTip()
        assert window.session.document.state is before
    finally:
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard
        ):
            window.close()


def test_documentation_coverage_links_and_anchors(tmp_path):
    from tools.check_docs import ROOT, check

    assert check(ROOT) == []
    (tmp_path / "little_tinker_rig/locale").mkdir(parents=True)
    (tmp_path / "little_tinker_rig/locale/languages.json").write_text(
        json.dumps({"en": "English", "ru": "Русский"}), encoding="utf-8"
    )
    (tmp_path / "doc/en").mkdir(parents=True)
    (tmp_path / "doc/ru").mkdir()
    (tmp_path / "README.md").write_text(
        "[Start](doc/en/index.md#start)\n", encoding="utf-8"
    )
    (tmp_path / "doc/en/index.md").write_text(
        "# Start\n\n[Missing](missing.md)\n[Section](#absent)\n", encoding="utf-8"
    )
    errors = check(tmp_path)
    assert any("ru: missing documentation page index.md" in error for error in errors)
    assert any("missing link target missing.md" in error for error in errors)
    assert any("missing anchor #absent" in error for error in errors)

    (tmp_path / "doc/en/index.md").write_text("# Start\n", encoding="utf-8")
    (tmp_path / "doc/ru/index.md").write_text("# Начало\n", encoding="utf-8")
    (tmp_path / "doc/en/api.md").write_text("# Developer API\n", encoding="utf-8")
    assert check(tmp_path) == []
    (tmp_path / "doc/ru/api.md").write_text("# API\n", encoding="utf-8")
    assert check(tmp_path) == ["ru: developer page must be English-only: api.md"]
