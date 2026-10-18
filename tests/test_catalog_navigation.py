import json
from unittest.mock import patch

from little_tinker_rig.core.catalog_history import History, reference
from little_tinker_rig.core.snippets import builtin_snippets


def test_history_bounds_counts_expires_and_keeps_favorites_and_document_scope():
    history = History(now=100 * 86400)
    for index in range(16):
        history.use(f"test/actions/action_{index}")
    identity = "test/actions/action_0"
    history.use(identity)
    history.favorite(identity)
    history.favorite("document/functions/run", "/one.py", "Run")
    history.favorite("document/functions/run", "/two.py", "Run")
    history.move(history.favorites[-1], -1)
    assert len(history.recent) == 12
    assert history.recent[0] == reference(identity)
    assert history.frequent()[0] == reference(identity)
    assert len(set(history.favorites)) == 3
    saved = history.dumps()
    restored = History(saved, now=129 * 86400)
    assert restored.frequent() == history.frequent()
    expired = History(saved, now=130 * 86400)
    assert expired.frequent() == []
    assert expired.favorites == history.favorites
    restored.clear_recent()
    assert restored.recent == [] and restored.frequent()
    restored.reset_usage()
    assert not restored.frequent() and restored.favorites == history.favorites
    assert set(json.loads(restored.dumps())["entries"]) == set(history.favorites)


def test_family_navigation_filters_variants_and_retains_personal_links(
    tmp_path, qt_app
):
    from PySide6.QtCore import QSettings

    from little_tinker_rig.i18n import set_language, tr
    from little_tinker_rig.qt.library import IDENTITY, Library

    settings = QSettings(str(tmp_path / "catalog.ini"), QSettings.Format.IniFormat)
    snippets = builtin_snippets()
    library = Library(snippets, settings)
    identity = "pybricks/motors/motor_target"
    variant = "pybricks/motors/target_background"
    key = reference(identity)
    try:
        item = library.rows[key]
        library.headings["movement"].setExpanded(True)
        library.setCurrentItem(item)
        library.select_variant(variant)
        assert item.data(0, IDENTITY) == variant
        assert (
            bytes(
                library.mimeData([item]).data("application/x-little-tinker-rig-snippet")
            )
            == variant.encode()
        )
        library.filter("no matching operation")
        library.load(snippets)
        library.filter("")
        assert library.currentItem() is library.rows[key]
        assert library.headings["movement"].isExpanded()
        assert not library.headings["program"].isExpanded()
        library.filter("coast")
        stop = library.rows[reference("pybricks/motors/stop_motor")]
        assert library.snippets[stop.data(0, IDENTITY)].variant == "Coast"
        library.setCurrentItem(stop)
        library.select_variant("pybricks/motors/stop_motor")
        library.filter("coast")
        assert stop.data(0, IDENTITY) == "pybricks/motors/stop_motor"
        library.filter("")
        library.setCurrentItem(library.rows[key])
        library.toggle_favorite()
        library.record_use(identity)
        library.record_use(variant)
        assert library.history.recent == [key]
        assert sum(library.history.entries[key]["days"].values()) == 2
        library.set_view("frequent")
        assert library.topLevelItemCount() == 1
        library.record_use("python/basics/display")
        assert library.topLevelItemCount() == 1
        library.set_view("catalog")
        library.set_view("frequent")
        assert library.topLevelItemCount() == 2
        library.set_view("catalog")
        alias = "pybricks/motor_motion/motor_run_target_speed_target_angle_then_wait"
        library.stage_ids = frozenset({alias})
        library.set_view("lesson")
        library.filter("", "beginner")
        item = library.rows[key]
        assert not item.isHidden() and item.data(0, IDENTITY) == alias
        library.setCurrentItem(item)
        assert [s.identity for s in library.current_choices()] == [alias]
        library.select_variant(variant)
        assert item.data(0, IDENTITY) == alias
        library.set_view("favorites")
        set_language("ru")
        library.load(())
        assert library.topLevelItemCount() == 1
        assert library.topLevelItem(0).data(0, IDENTITY) is None
        help_text = next(s.help for s in snippets if s.identity == identity)
        assert library.topLevelItem(0).text(0) == tr(help_text).splitlines()[0]
        assert library.history.favorites == [key]
        library.load(snippets)
        assert library.topLevelItem(0).data(0, IDENTITY) == identity
        persisted = History(settings.value("blockLibrary"))
        assert persisted.favorites == [key] and persisted.recent[-1] == key
    finally:
        library.close()


def test_group_titles_toggle_once_for_top_level_and_nested_branches(qt_app):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.library import Library

    library = Library(builtin_snippets())
    library.resize(320, 520)
    library.show()
    try:
        def click_title(item):
            library.scrollToItem(item)
            qt_app.processEvents()
            rect = library.visualItemRect(item)
            QTest.mouseClick(
                library.viewport(),
                Qt.MouseButton.LeftButton,
                pos=QPoint(rect.left() + 55, rect.center().y()),
            )

        top = library.headings["movement"]
        top.setExpanded(False)
        click_title(top)
        assert top.isExpanded()
        click_title(top)
        assert not top.isExpanded()

        rect = library.visualItemRect(top)
        QTest.mouseClick(
            library.viewport(),
            Qt.MouseButton.LeftButton,
            pos=QPoint(max(2, rect.left() - 6), rect.center().y()),
        )
        assert top.isExpanded()

        nested = next(
            item
            for key, item in library.headings.items()
            if key.startswith("movement/") and item.parent() is top
        )
        nested.setExpanded(False)
        click_title(nested)
        assert nested.isExpanded()
        click_title(nested)
        assert not nested.isExpanded()
    finally:
        library.close()


def test_long_catalog_title_gains_a_second_line_in_compact_russian_view(
    tmp_path, qt_app
):
    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "main.py")
    window.show()
    try:
        window.change_language("ru")
        qt_app.processEvents()
        card = next(
            item
            for item in window.library.rows.values()
            if item.text(0) == "Повернуть ходовую часть"
        )
        wide_height = window.library.visualItemRect(card).height()
        window.resize(930, 620)
        qt_app.processEvents()
        qt_app.processEvents()
        compact_height = window.library.visualItemRect(card).height()
        assert compact_height > wide_height
    finally:
        window.recovery.close()
        window.deleteLater()


def test_catalog_insertions_count_once_in_program_and_both_scratch_paths(
    tmp_path, qt_app
):
    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import QDropEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.library import FAVORITE, favorite_rect

    window = Studio(tmp_path / "main.py")
    identity = "python/basics/display"
    key = reference(identity)

    def count():
        return sum(window.library.history.entries[key]["days"].values())

    window.show()
    qt_app.processEvents()
    try:
        window.library.setCurrentItem(window.library.rows[key])
        window.insert_selected()
        assert count() == 1
        window.session.editor.undo()
        window.refresh_views()
        window.session.editor.redo()
        window.refresh_views()
        assert count() == 1
        data = QMimeData()
        data.setData("application/x-little-tinker-rig-snippet", identity.encode())
        event = QDropEvent(
            QPointF(20, 20),
            Qt.DropAction.CopyAction,
            data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        window.scratch.dropEvent(event)
        assert event.isAccepted() and count() == 2
        window.scratch.cells[0].insert_snippet(identity)
        assert count() == 3
        failures = []
        window.scratch.failed.disconnect(window.error)
        window.scratch.failed.connect(failures.append)
        window.scratch.cells[0].insert_snippet(identity)
        assert not failures and count() == 4
        QTest.mouseClick(
            window.view_filter.buttons["recent"], Qt.MouseButton.LeftButton
        )
        assert window.library.topLevelItemCount() == 1
        item = window.library.topLevelItem(0)
        star = favorite_rect(window.library.visualItemRect(item)).center()
        before = window.session.document.state
        QTest.mouseClick(window.library.viewport(), Qt.MouseButton.LeftButton, pos=star)
        assert window.library.history.favorites == [key]
        assert item.data(0, FAVORITE)
        assert window.session.document.state is before and count() == 4
        QTest.mouseClick(window.library.viewport(), Qt.MouseButton.LeftButton, pos=star)
        assert not window.library.history.favorites and not item.data(0, FAVORITE)
        QTest.mouseClick(window.library.viewport(), Qt.MouseButton.LeftButton, pos=star)
        window.library.load(())
        window.view_filter.select("favorites")
        unavailable = window.library.topLevelItem(0)
        star = favorite_rect(window.library.visualItemRect(unavailable)).center()
        QTest.mouseClick(window.library.viewport(), Qt.MouseButton.LeftButton, pos=star)
        assert not window.library.history.favorites
        window.view_filter.select("recent")
        QTest.mouseClick(window.clear_usage, Qt.MouseButton.LeftButton)
        assert window.library.history.recent == [] and count() == 4
    finally:
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard
        ):
            window.close()


def test_unnamed_function_scope_survives_recovery_and_moves_on_first_save(
    tmp_path, qt_app
):
    from PySide6.QtWidgets import QFileDialog

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.document import DocumentPage
    from little_tinker_rig.qt.library import IDENTITY

    window = Studio()
    window.confirm_close = lambda *_: True
    restored = DocumentPage(tmp_path / "recovery.py")
    try:
        window.session.editor.commit("def run():\n    pass\n")
        window.refresh_views()
        window.level_filter.select("all")
        old_scope = window.document_page.catalog_scope
        identity = "document/functions/run"
        key = reference(identity, old_scope)
        window.library.setCurrentItem(window.library.rows[key])
        window.library.toggle_favorite()
        window.insert_snippet(identity)
        checkpoint = window.document_page.checkpoint()
        restored.restore(checkpoint)
        assert restored.catalog_scope == old_scope
        destination = tmp_path / "saved.py"
        with patch.object(
            QFileDialog, "getSaveFileName", return_value=(str(destination), "")
        ):
            assert window.save_as()
        saved_key = reference(identity, str(destination.resolve()))
        assert window.library.history.favorites == [saved_key]
        assert window.library.history.recent == [saved_key]
        assert sum(window.library.history.entries[saved_key]["days"].values()) == 1
        window.new_file()
        assert window.document_page.catalog_scope != old_scope
        window.session.editor.commit("def run():\n    pass\n")
        window.refresh_views()
        window.library.set_view("favorites")
        assert window.library.topLevelItem(0).data(0, IDENTITY) is None
        assert window.library.history.favorites == [saved_key]
    finally:
        restored.close()
        restored.deleteLater()
        window.close()
