import json

import pytest

from little_tinker_rig.core.lessons import Lesson, StudentProject
from little_tinker_rig.i18n import language, set_language


def make_lesson(tmp_path):
    root = tmp_path / "lesson"
    root.mkdir()
    (root / "goal.md").write_text("Make the robot move.")
    (root / "lesson.json").write_text(
        json.dumps(
            {
                "format": 1,
                "id": "car",
                "title": "Drive",
                "stages": [
                    {
                        "id": "drive",
                        "title": "Drive",
                        "description": "goal.md",
                        "blocks": ["pybricks/drive/straight"],
                    },
                    {
                        "id": "stop",
                        "title": "Stop",
                        "description": "goal.md",
                        "blocks": ["pybricks/drive/brake"],
                    },
                ],
            }
        )
    )
    return root


@pytest.mark.parametrize(
    "workspace",
    [
        {"documents": [], "active": "main.py"},
        {"documents": {"main.py": {"python": "yes"}}, "active": "main.py"},
        {"documents": {"main.py": {"scroll": 2**100}}, "active": "main.py"},
        {"documents": {}, "active": 5},
    ],
)
def test_bad_lesson_tab_layout_does_not_prevent_opening_program(
    tmp_path, qt_app, workspace
):
    from little_tinker_rig.qt.app import Studio

    project = StudentProject.create(make_lesson(tmp_path))
    project.main.write_text("answer = 7\n", encoding="utf-8")
    (project.root / "workspace.json").write_text(
        json.dumps(workspace), encoding="utf-8"
    )
    window = Studio(tmp_path / "plain.py")
    try:
        page = window.lessons.open(project.data["origin"], attempt=project)
        assert page.lesson_project is project
        assert page.text == "answer = 7\n"
        assert window.documents.count() == 2
    finally:
        window.recovery.close()
        window.deleteLater()


def test_lesson_tab_layout_cannot_replace_program_checkpoint(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    project = StudentProject.create(make_lesson(tmp_path))
    project.main.write_text("answer = 7\n", encoding="utf-8")
    (project.root / "workspace.json").write_text(
        json.dumps(
            {
                "documents": {
                    "main.py": {
                        "python": True,
                        "cursor": 0,
                        "scroll": 0,
                        "source": "answer = 99\n",
                        "committed": "answer = 99\n",
                    }
                },
                "active": "main.py",
            }
        ),
        encoding="utf-8",
    )
    window = Studio(tmp_path / "plain.py")
    try:
        page = window.lessons.open(project.data["origin"], attempt=project)
        assert page.text == "answer = 7\n"
        assert page.code_active
        assert project.main.read_text(encoding="utf-8") == "answer = 7\n"
    finally:
        window.recovery.close()
        window.deleteLater()


def test_lesson_autosave_continues_after_a_program_conflict(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    lesson = make_lesson(tmp_path)
    first = StudentProject.create(lesson)
    second = StudentProject.create(lesson)
    helper = first.main.parent / "helper.py"
    helper.write_text("value = 1\n", encoding="utf-8")

    window = Studio(tmp_path / "plain.py")
    try:
        first_page = window.lessons.open(lesson, attempt=first)
        helper_page = window.open_document(helper)
        assert helper_page.lesson_project is first
        second_page = window.lessons.open(lesson, attempt=second)

        first_page.session.editor.commit("answer = 11\n")
        first.main.write_text("answer = 99\n", encoding="utf-8")
        helper_page.session.editor.commit("value = 22\n")
        second_page.session.editor.commit("answer = 33\n")

        assert not window.recovery.flush()
        assert first.main.read_text(encoding="utf-8") == "answer = 99\n"
        assert helper.read_text(encoding="utf-8") == "value = 22\n"
        assert second.main.read_text(encoding="utf-8") == "answer = 33\n"
        checkpoint = json.loads(window.recovery.path.read_text(encoding="utf-8"))
        assert any(
            item["path"] == str(first.main) and item["source"] == "answer = 11\n"
            for item in checkpoint["documents"]
        )
    finally:
        window.recovery.close()
        window.deleteLater()


def test_lesson_save_confirms_the_normalized_archive_destination(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from little_tinker_rig.qt.app import Studio

    source = make_lesson(tmp_path)
    destination = tmp_path / "student.ltr"
    destination.write_bytes(b"Existing project")
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args: (str(tmp_path / "student.txt"), ""),
    )
    answers = iter((QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: next(answers))

    window = Studio(tmp_path / "plain.py")
    try:
        project = window.lessons.open(source).lesson_project
        assert not window.lessons.save(project, choose=True)
        assert destination.read_bytes() == b"Existing project"
        assert project.path is None

        assert window.lessons.save(project, choose=True)
        assert StudentProject.open(destination).data["id"] == project.data["id"]
    finally:
        window.recovery.close()
        window.deleteLater()


def test_lesson_save_failure_reports_error_and_keeps_program(
    tmp_path, qt_app, monkeypatch
):
    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    try:
        page = window.lessons.open(make_lesson(tmp_path))
        page.session.editor.commit("answer = 42\n")

        def fail_save(*args, **kwargs):
            raise OSError("lesson disk full")

        monkeypatch.setattr(window.lessons, "save", fail_save)
        assert window.save_document(page) is False
        assert "lesson disk full" in window.last_error
        assert page.text == "answer = 42\n" and page.dirty
    finally:
        window.recovery.close()
        window.deleteLater()


def test_invalid_later_lesson_tab_does_not_partly_restore_layout(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    project = StudentProject.create(make_lesson(tmp_path))
    helper = project.main.parent / "helper.py"
    helper.write_text("value = 2\n", encoding="utf-8")
    (project.root / "workspace.json").write_text(
        json.dumps(
            {
                "documents": {
                    "main.py": {"python": True, "cursor": 0, "scroll": 0},
                    "helper.py": {"python": "invalid"},
                },
                "active": "helper.py",
            }
        ),
        encoding="utf-8",
    )
    window = Studio(tmp_path / "plain.py")
    try:
        page = window.lessons.open(project.data["origin"], attempt=project)
        assert window.documents.count() == 2
        assert window.document_page is page
        assert not page.code_active
        assert helper.read_text(encoding="utf-8") == "value = 2\n"
    finally:
        window.recovery.close()
        window.deleteLater()


def test_lesson_template_resumes_latest_attempt_after_clean_close(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    source = make_lesson(tmp_path)
    first_window = Studio(tmp_path / "plain.py")
    try:
        page = first_window.lessons.open(source)
        project = page.lesson_project
        page.session.editor.commit("answer = 42\n")
        page.session.document.commit(page.text, ("print(answer)\n",))
        first_window.lessons.select_stage(1)
        assert first_window.lessons.open(source) is page
        assert first_window.documents.count() == 2
        root = project.root
        assert first_window.close()
        assert root.is_dir()
    finally:
        first_window.recovery.close()
        first_window.deleteLater()

    second_window = Studio(tmp_path / "other.py")
    try:
        resumed = second_window.lessons.open(source)
        assert resumed.lesson_project.root == root
        assert resumed.text == "answer = 42\n"
        assert resumed.session.document.state.scratch == ("print(answer)\n",)
        assert resumed.lesson_project.stage["id"] == "stop"
        new = second_window.lessons.open(source, new=True)
        assert new.lesson_project.root != root
        assert second_window.lessons.open(source) is new
        assert root.is_dir()
        older = next(
            attempt
            for attempt in StudentProject.attempts(source)
            if attempt.root == root
        )
        assert (
            second_window.lessons.open(source, attempt=older).lesson_project.root
            == root
        )
        assert second_window.lessons.open(source).lesson_project.root == root
    finally:
        second_window.recovery.close()
        second_window.deleteLater()


def test_invalid_attempt_date_does_not_break_lesson_menu(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    source = make_lesson(tmp_path)
    valid = StudentProject.create(source)
    invalid = StudentProject.create(source)
    manifest = invalid.root / "project.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["opened"] = 10**100
    manifest.write_text(json.dumps(data), encoding="utf-8")

    window = Studio()
    try:
        assert [attempt.root for attempt in StudentProject.attempts(source)] == [
            valid.root
        ]
        window.lessons.populate()
        attempts = next(
            action.menu()
            for action in window.lessons.menu.actions()
            if action.text() == "My lesson attempts"
        )
        assert len(attempts.actions()) == 1
    finally:
        window.recovery.close()
        window.deleteLater()


def test_lesson_program_tab_is_distinct_from_plain_main_file(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    original_language = language()
    window = Studio(tmp_path / "main.py")
    try:
        page = window.lessons.open(make_lesson(tmp_path))
        lesson_index = window.documents.indexOf(page)
        assert window.documents.tabText(0) == "main.py"
        set_language("en")
        window.retranslate()
        assert window.documents.tabText(lesson_index) == "main.py · Lesson"
        assert "Drive" in window.documents.tabToolTip(lesson_index)
        set_language("ru")
        window.retranslate()
        assert window.documents.tabText(lesson_index) == "main.py · Урок"
    finally:
        set_language(original_language)
        window.recovery.close()
        window.deleteLater()


def test_open_template_in_second_window_returns_to_live_attempt(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    source = make_lesson(tmp_path)
    first = Studio(tmp_path / "first.py")
    second = Studio(tmp_path / "second.py")
    try:
        page = first.lessons.open(source)
        first.set_mode(0)
        assert second.lessons.open(source) is page
        assert first.pages.currentIndex() == 2
        assert first.help_page.current == "lesson/instructions#task-drive"
        assert second.lessons.current is None
        assert first.lessons.current is page.lesson_project
        assert len(StudentProject.attempts(source)) == 1
    finally:
        first.recovery.close()
        second.recovery.close()
        first.deleteLater()
        second.deleteLater()


def test_task_panel_collapses_to_progress_chip_on_small_window(tmp_path, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QTabBar

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.resize(1024, 768)
    window.show()
    try:
        window.lessons.open(make_lesson(tmp_path))
        qt_app.processEvents()
        assert window.pages.currentIndex() == 2
        assert not window.lessons.panel.isVisible()
        assert window.lessons.progress_button.isVisible()
        assert window.lessons.progress_button.parent() is window.main_toolbar
        actions = window.main_toolbar.actions()
        assert actions.index(window.lessons.progress_action) + 1 == actions.index(
            window.hub_button_action
        )
        QTest.mouseClick(window.lessons.progress_button, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert window.lessons.overlay.isVisible()
        assert not window.lessons.dock.isVisible()
        assert window.lessons.panel.isVisible()
        assert window.lessons.overlay.height() > 500
        assert window.pages.width() > 600
        window.lessons.set_panel_expanded(False)
        qt_app.processEvents()
        QTest.mouseClick(window.lessons.progress_button, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert window.lessons.panel.isVisible()
        window.lessons.cards["drive"]["body"].setFocus()
        QTest.keyClick(window.lessons.cards["drive"]["body"], Qt.Key.Key_Escape)
        qt_app.processEvents()
        assert window.lessons.progress_button.isVisible()
        QTest.mouseClick(window.lessons.progress_button, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        QTest.mouseClick(window.source.viewport(), Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert window.lessons.progress_button.isVisible()
        assert window.lessons.current.progress["panel_expanded"]
        assert not window.lessons.guidance.isChecked()
        window.lessons.guidance.trigger()
        qt_app.processEvents()
        assert window.lessons.overlay.isVisible()
        window.resize(1250, 800)
        qt_app.processEvents()
        assert window.lessons.overlay.isVisible()
        assert not window.lessons.dock.isVisible()
        window.resize(1440, 900)
        qt_app.processEvents()
        assert window.lessons.dock.isVisible()
        assert window.lessons.panel.isVisible()
        window.scratch_dock.show()
        qt_app.processEvents()
        tabs = next(
            bar
            for bar in window.findChildren(QTabBar)
            if window.scratch_dock.windowTitle()
            in (bar.tabText(i) for i in range(bar.count()))
        )
        scratch_index = next(
            i
            for i in range(tabs.count())
            if tabs.tabText(i) == window.scratch_dock.windowTitle()
        )
        QTest.mouseClick(
            tabs, Qt.MouseButton.LeftButton, pos=tabs.tabRect(scratch_index).center()
        )
        qt_app.processEvents()
        assert window.scratch_dock.isVisible()
        assert window.lessons.progress_button.isVisible()
        assert window.lessons.current.progress["panel_expanded"]
        QTest.mouseClick(window.lessons.progress_button, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert window.lessons.dock.isVisible()
        assert not window.lessons.progress_button.isVisible()
    finally:
        window.recovery.close()
        window.deleteLater()


def test_collapsing_task_panel_reclaims_help_width_on_wide_window(tmp_path, qt_app):
    from pathlib import Path

    from PySide6.QtWidgets import QSplitter

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.resize(1920, 1050)
    window.show()
    try:
        source = Path(__file__).resolve().parents[1] / "lessons" / "first_drive"
        window.lessons.open(source, new=True)
        qt_app.processEvents()
        assert window.lessons.dock.isVisible()
        help_page = window.help_page
        splitter = help_page.findChild(QSplitter)
        pane_width = help_page.browser.width()
        sidebar_width = splitter.widget(0).width()
        window.lessons.set_panel_expanded(False)
        qt_app.processEvents()
        assert not window.lessons.dock.isVisible()
        assert help_page.browser.width() >= pane_width + 250
        assert splitter.widget(0).width() == sidebar_width
        assert help_page.browser.viewport().width() <= 1120
    finally:
        window.recovery.close()
        window.deleteLater()


def test_help_recent_pages_deduplicates_lesson_sections_and_back(tmp_path, qt_app):
    from pathlib import Path

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.show()
    try:
        source = Path(__file__).resolve().parents[1] / "lessons" / "first_drive"
        window.lessons.open(source, new=True)
        help_page = window.help_page
        initial_history = help_page.history[:]
        help_page.show_page("lesson/instructions#build")
        help_page.show_page("lesson/instructions#experiment")
        assert help_page.history == initial_history
        assert [action.data() for action in help_page.recent_menu.actions()] == [
            "index.md"
        ]
        help_page.show_page("usage.md")
        assert help_page.history == initial_history + ["lesson/instructions#experiment"]
        assert help_page.recent_menu.actions()[0].data() == (
            "lesson/instructions#experiment"
        )
        help_page.back_button.click()
        assert help_page.current == "lesson/instructions#experiment"
        help_page.show_page("usage.md")
        help_page.show_page("index.md")
        help_page.show_page("usage.md")
        assert (
            len([key for key in help_page.recent_pages if key.startswith("usage.md")])
            == 1
        )
        assert [action.data() for action in help_page.recent_menu.actions()][:2] == [
            "index.md",
            "lesson/instructions#experiment",
        ]
        help_page.recent_menu.actions()[1].trigger()
        assert help_page.current == "lesson/instructions#experiment"
    finally:
        window.recovery.close()
        window.deleteLater()


def test_language_change_skips_closed_window_with_removed_lesson(tmp_path, qt_app):
    import shutil

    from little_tinker_rig.qt.app import Studio

    first = Studio(tmp_path / "first.py")
    first.show()
    first.lessons.open(make_lesson(tmp_path))
    first.confirm_close = lambda *_: True
    assert first.close()
    assert not first.isVisible()
    lesson_root = first.help_page.lesson.root
    shutil.rmtree(lesson_root)
    second = Studio(tmp_path / "second.py")
    second.show()
    try:
        second.change_language("ru")
        assert second.help_page.root.name == "ru"
    finally:
        first.recovery.close()
        second.recovery.close()
        first.deleteLater()
        second.deleteLater()


def test_task_checkbox_points_and_evidence_are_idempotent(tmp_path, qt_app):
    from little_tinker_rig.pybricks.devices import HubInfo
    from little_tinker_rig.qt.app import Studio

    root = make_lesson(tmp_path)
    (root / "robot.ldr").write_text("0 Original model\n", encoding="utf-8")
    (root / "robot.json").write_text(
        json.dumps(
            {
                "format": 1,
                "model": "robot.ldr",
                "devices": [
                    {
                        "instance": "left",
                        "name": "Left motor",
                        "port": "A",
                        "type": "motor",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    data = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    data["robot"] = "robot.json"
    data["stages"][0]["points"] = 2
    data["stages"][1].update(check="devices", devices=["left"], points=3)
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    window = Studio(tmp_path / "plain.py")
    try:
        window.lessons.open(root)
        lesson = window.lessons
        lesson.cards["drive"]["check"].setChecked(True)
        assert lesson.current.score == (2, 5)
        lesson.cards["drive"]["check"].setChecked(False)
        assert lesson.current.score == (0, 5)
        lesson.set_completion("stop", True)
        assert lesson.current.score == (0, 5)
        window.update_hub(
            HubInfo(connected=True, monitoring=True, ports={"A": {"type": "motor"}})
        )
        stage = lesson.current.lesson.stages[1]
        for required in ([], ["left", "left"], ["unknown"]):
            stage["devices"] = required
            assert not lesson.check_ready(stage)
            lesson.set_completion("stop", True)
            assert lesson.current.score == (0, 5)
        stage["devices"] = ["left"]
        lesson.cards["stop"]["check"].setChecked(True)
        assert lesson.current.score == (3, 5)
        assert lesson.current.progress["evidence"] == {"stop": "devices"}
        lesson.cards["stop"]["check"].setChecked(True)
        assert lesson.current.score == (3, 5)
        assert "1/2" in lesson.progress_button.text()
        assert "3/5" in lesson.summary.text()
        assert lesson.progress_bar.maximum() == 2
        assert lesson.progress_bar.value() == 1
        assert lesson.cards["stop"]["number"].property("completed") is True
    finally:
        window.recovery.close()
        window.deleteLater()


def test_task_material_links_open_markdown_controls_and_seeded_scratch(
    tmp_path, qt_app
):
    from PySide6.QtCore import QUrl

    from little_tinker_rig.qt.app import Studio

    root = make_lesson(tmp_path)
    (root / "extra.md").write_text(
        "# Extra help\nTry another idea.\n", encoding="utf-8"
    )
    (root / "idea.py").write_text("distance = 200\n", encoding="utf-8")
    data = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    data["scratch_seeds"] = {"main.py": ["idea.py"]}
    data["stages"][0]["links"] = [
        {"kind": "markdown", "label": "Extra help", "target": "extra.md"},
        {"kind": "control", "label": "Try controls"},
        {"kind": "scratch", "label": "Scratch idea", "target": "main.py"},
    ]
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    window = Studio(tmp_path / "plain.py")
    window.show()
    try:
        page = window.lessons.open(root)
        lesson = window.lessons
        assert window.help_page.lesson_group.childCount() == 1
        assert page.session.document.state.scratch == ("distance = 200\n",)
        body = lesson.cards["drive"]["body"]
        assert "Extra help" in body.toPlainText()
        lesson.follow_task_anchor("drive", QUrl("task:extra/0"), body)
        assert window.pages.currentIndex() == 2
        assert "Try another idea" in window.help_page.browser.toPlainText()
        assert window.help_page.lesson_group.childCount() == 1
        window.help_page.tree.itemClicked.emit(window.help_page.lesson_item, 0)
        assert window.help_page.current == "lesson/instructions"
        assert "Make the robot move" in window.help_page.browser.toPlainText()
        lesson.follow_task_anchor("drive", QUrl("task:extra/1"), body)
        assert window.pages.currentIndex() == 1
        lesson.follow_task_anchor("drive", QUrl("task:extra/2"), body)
        assert window.pages.currentIndex() == 0
        assert window.document_page is page
        assert window.scratch_dock.isVisible()
        assert not lesson.current.progress["completed"]
    finally:
        window.recovery.close()
        window.deleteLater()


def test_authored_task_card_link_opens_instructions_from_visible_markdown(
    tmp_path, qt_app
):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    root = make_lesson(tmp_path)
    (root / "panel.md").write_text("Try a short journey.\n", encoding="utf-8")
    data = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    data["stages"][0]["panel"] = "panel.md"
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    window = Studio(tmp_path / "plain.py")
    window.resize(1440, 900)
    window.show()
    try:
        window.lessons.open(root)
        qt_app.processEvents()
        body = window.lessons.cards["drive"]["body"]
        assert "Try a short journey." in body.toPlainText()
        assert "Instructions" in body.toPlainText()
        cursor = body.document().find("Instructions")
        cursor.setPosition(cursor.selectionStart() + 5)
        position = body.cursorRect(cursor).center()
        assert body.viewport().rect().contains(position)
        QTest.mouseClick(body.viewport(), Qt.MouseButton.LeftButton, pos=position)
        qt_app.processEvents()
        assert window.pages.currentIndex() == 2
        assert "Make the robot move" in window.help_page.browser.toPlainText()
        assert not window.lessons.current.progress["completed"]
    finally:
        window.recovery.close()
        window.deleteLater()


@pytest.mark.parametrize("width,height", [(1380, 880), (800, 620)])
def test_task_completion_keeps_keyboard_focus(tmp_path, qt_app, width, height):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAccessible
    from PySide6.QtTest import QSignalSpy, QTest

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.resize(width, height)
    window.show()
    try:
        window.lessons.open(make_lesson(tmp_path))
        window.lessons.set_panel_expanded(True)
        qt_app.processEvents()
        assert window.lessons.panel.isVisible()
        window.lessons.collapse_button.setFocus()
        QTest.keyClick(window.lessons.collapse_button, Qt.Key.Key_Tab)
        assert qt_app.focusWidget() is window.lessons.task_area
        QTest.keyClick(window.lessons.task_area, Qt.Key.Key_Tab)
        assert qt_app.focusWidget() is window.lessons.cards["drive"]["check"]
        for checked in (True, False):
            check = window.lessons.cards["drive"]["check"]
            check.setFocus()
            QTest.keyClick(check, Qt.Key.Key_Space)
            qt_app.processEvents()
            current = window.lessons.cards["drive"]["check"]
            assert current.isChecked() is checked
            assert qt_app.focusWidget() is current
        QTest.keyClick(current, Qt.Key.Key_Tab)
        title = window.lessons.cards["drive"]["title"]
        assert qt_app.focusWidget() is title
        assert (
            QAccessible.queryAccessibleInterface(title).role()
            == QAccessible.Role.PushButton
        )
        QTest.keyClick(title, Qt.Key.Key_Tab)
        assert qt_app.focusWidget() is window.lessons.cards["drive"]["body"]
        title.setFocus()
        activated = QSignalSpy(title.clicked)
        QTest.keyClick(title, Qt.Key.Key_Return)
        assert activated.count() == 1
        assert window.pages.currentIndex() == 2
        window.set_mode(0)
        window.lessons.set_panel_expanded(True)
        title = window.lessons.cards["drive"]["title"]
        title.setFocus()
        activated = QSignalSpy(title.clicked)
        QTest.keyClick(title, Qt.Key.Key_Space)
        assert activated.count() == 1
        assert window.pages.currentIndex() == 2
    finally:
        window.recovery.close()
        window.deleteLater()


def test_lesson_help_title_fits_compact_russian_window_with_console(tmp_path, qt_app):
    from pathlib import Path

    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "main.py")
    window.resize(930, 620)
    window.show()
    try:
        window.change_language("ru")
        window.lessons.open(Path("lessons/first_drive"))
        window.set_mode(2)
        window.console_dock.show()
        QTest.qWait(80)
        browser = window.help_page.browser
        title = browser.document().begin()
        assert browser.width() <= 620
        assert title.blockFormat().headingLevel() == 1
        assert "45678" in title.text()
        assert title.layout().lineCount() == 1
    finally:
        window.confirm_close = lambda *_: True
        window.recovery.close()
        window.close()


def test_compact_tasks_keep_lesson_instructions_readable(tmp_path, qt_app):
    from pathlib import Path

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.show()
    try:
        window.change_language("ru")
        window.lessons.open(Path("lessons/first_python"))
        window.set_mode(2)
        QTest.qWait(90)
        page = window.help_page
        assert page.sidebar.isVisible()
        assert page.browser.viewport().width() >= 400
        original_split = page.sidebar.parentWidget().sizes()

        window.lessons.set_panel_expanded(True)
        QTest.qWait(90)
        assert window.lessons.overlay.isVisible()
        assert not page.sidebar.isVisible()
        assert page.browser.viewport().width() >= 300
        browser_right = page.browser.mapTo(
            window.workspace, page.browser.rect().topRight()
        ).x()
        assert browser_right < window.lessons.overlay.x()
        assert "Первая программа на Python" in page.browser.toPlainText()

        window.set_mode(0)
        assert page._overlay_clearance == 0
        window.set_mode(2)
        assert page._overlay_clearance == window.lessons.overlay.width()
        window.lessons.show_stage()
        QTest.qWait(90)
        assert not window.lessons.overlay.isVisible()
        assert page.sidebar.isVisible()
        assert page.browser.viewport().width() >= 400
        assert page.sidebar.parentWidget().sizes() == original_split

        window.lessons.set_panel_expanded(True)
        QTest.mouseClick(
            page.browser.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(20, 20)
        )
        QTest.qWait(50)
        assert not window.lessons.overlay.isVisible()
        assert page.sidebar.isVisible()
    finally:
        window.confirm_close = lambda *_: True
        window.close()
        window.deleteLater()


def test_compact_task_overlay_leaves_program_editable(tmp_path, qt_app):
    from pathlib import Path

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.confirm_close = lambda *_: True
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.show()
    try:
        window.lessons.open(Path("lessons/first_python"))
        window.set_mode(0)
        window.lessons.set_panel_expanded(True)
        QTest.qWait(90)

        overlay = window.lessons.overlay
        assert overlay.isVisible()
        assert not window.library_pane.isVisible()
        editor_left = (
            window.source.viewport()
            .mapTo(window.workspace, window.source.viewport().rect().topLeft())
            .x()
        )
        assert overlay.x() - editor_left >= 300

        QTest.mouseClick(
            window.source.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(20, 200)
        )
        QTest.qWait(30)
        assert not overlay.isVisible()
        assert window.library_pane.isVisible()

        window.lessons.set_panel_expanded(True)
        QTest.qWait(30)
        assert not window.library_pane.isVisible()
        window.lessons.set_panel_expanded(False)
        QTest.qWait(30)
        assert window.library_pane.isVisible()
        assert window.source.viewport().width() >= 300

        window.change_editor(1)
        window.lessons.set_panel_expanded(True)
        window.lessons.set_panel_expanded(False)
        assert not window.library_pane.isVisible()
        window.change_editor(0)
        assert window.library_pane.isVisible()
    finally:
        window.close()
        window.deleteLater()


def test_compact_task_overlay_keeps_program_lines_scrollable(tmp_path, qt_app):
    from pathlib import Path

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.confirm_close = lambda *_: True
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.show()
    try:
        window.lessons.open(Path("lessons/first_python"))
        window.set_mode(0)
        window.lessons.set_panel_expanded(True)
        qt_app.processEvents()
        overlay = window.lessons.overlay
        assert (
            window.source.viewport()
            .mapTo(window.workspace, window.source.viewport().rect().topRight())
            .x()
            < overlay.x()
        )
        window.document_page.change_mode(1)
        window.code.setPlainText('value = "' + "x" * 55 + '"\n')
        window.lessons.set_panel_expanded(False)
        qt_app.processEvents()
        full_width = window.code.viewport().width()
        assert window.code.horizontalScrollBar().maximum() == 0

        window.lessons.set_panel_expanded(True)
        qt_app.processEvents()
        assert overlay.isVisible()
        assert window.code.viewport().width() < full_width
        assert (
            window.code.viewport()
            .mapTo(window.workspace, window.code.viewport().rect().topRight())
            .x()
            < overlay.x()
        )
        assert window.code.horizontalScrollBar().maximum() > 0

        window.lessons.set_panel_expanded(False)
        qt_app.processEvents()
        assert window.code.horizontalScrollBar().maximum() == 0
    finally:
        window.close()
        window.deleteLater()


def test_compact_task_overlay_releases_control_assembly_and_block_editor(
    tmp_path, qt_app
):
    from pathlib import Path

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.resize(930, 620)
    window.show()
    try:
        window.lessons.open(Path("lessons/first_python"))
        for mode in (3, 1, 4):
            window.lessons.set_panel_expanded(True)
            qt_app.processEvents()
            assert window.lessons.overlay.isVisible()
            window.set_mode(mode)
            qt_app.processEvents()
            assert not window.lessons.overlay.isVisible()
            assert window.lessons.progress_button.isVisible()
            if mode == 3:
                assert window.block_editor.code.viewport().width() >= 450

        window.lessons.progress_button.click()
        qt_app.processEvents()
        assert window.lessons.overlay.isVisible()
        window.set_mode(4)
        assert window.lessons.overlay.isVisible()
    finally:
        window.recovery.close()
        window.deleteLater()


def test_assembly_restores_user_split_after_compact_tasks(qt_app, monkeypatch):
    from PySide6.QtWidgets import QWidget

    from little_tinker_rig.qt.assembly import AssemblyPage

    monkeypatch.setattr(AssemblyPage, "load", lambda self: None)
    page = AssemblyPage("lessons/first_drive/robot/robot.json")
    page.view_container = QWidget()
    page.view_host.layout().addWidget(page.view_container)
    page.placeholder.hide()
    page.resize(1200, 720)
    page.show()
    try:
        qt_app.processEvents()
        for width in (500, 400):
            page.splitter.setSizes([page.splitter.width() - width, width])
            before = page.splitter.sizes()
            page.set_overlay_compact(True)
            page.resize(700, 720)
            qt_app.processEvents()
            page.set_overlay_compact(False)
            qt_app.processEvents()
            page.resize(1200, 720)
            qt_app.processEvents()
            assert abs(page.splitter.sizes()[1] - before[1]) <= 2
    finally:
        page.close()


@pytest.mark.parametrize("assembly_state", ["loading", "failure", "fallback", "model"])
def test_compact_lesson_assembly_stays_usable_beside_tasks(
    tmp_path, qt_app, monkeypatch, assembly_state
):
    from pathlib import Path
    from types import SimpleNamespace

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QWindow
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QWidget

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.assembly import AssemblyPage
    from little_tinker_rig.qt.resources import ResourceJob

    class PlaceholderView(QWindow):
        def select(self, *_args, **_kwargs):
            pass

        def update(self):
            pass

    monkeypatch.setattr(AssemblyPage, "load", lambda self: None)
    window = Studio(tmp_path / "plain.py")
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.show()
    try:
        window.change_language("ru")
        window.change_visual_theme("dark")
        window.lessons.open(Path("lessons/first_drive"))
        window.console_dock.show()
        window.set_mode(4)
        window.lessons.set_panel_expanded(True)
        page = window.lessons.assembly_host.lesson_page
        if assembly_state in ("fallback", "model"):
            page.scene = SimpleNamespace(step_count=2, instances=[])
            page.set_step(0)
        if assembly_state == "model":
            page.view = PlaceholderView()
            page.view_container = QWidget.createWindowContainer(page.view)
            page.view_host.layout().addWidget(page.view_container)
            page.placeholder.hide()
            page.set_overlay_compact(True)
        elif assembly_state == "fallback":
            page.show_error("")
        elif assembly_state == "failure":
            page.loaded(None, "unavailable")
        else:
            page.job = ResourceJob(lambda **_kwargs: None)
            page.loading_phase = "prepare"
            page.update_loading_status()
            page.progress.show()
            page.cancel.show()
        qt_app.processEvents()
        QTest.qWait(30)

        overlay = window.lessons.overlay
        assert overlay.isVisible()
        assert window.lessons.assembly_host._overlay_clearance == overlay.width()
        if assembly_state == "model":
            assert page.view_host.width() >= 200
            assert page.sidebar.width() >= 210
            assert (
                page.splitter.width() >= page.view_host.width() + page.sidebar.width()
            ), (
                page.width(),
                page.splitter.geometry().getRect(),
                page.splitter.sizes(),
                page.view_host.geometry().getRect(),
                page.sidebar.geometry().getRect(),
            )
        widgets = [page.caption, page.notes]
        if assembly_state in ("fallback", "model"):
            widgets += [
                page.parts_caption,
                page.parts,
                page.back,
                page.slider,
                page.next_step,
            ]
        elif assembly_state == "failure":
            widgets += [page.error, page.retry]
        else:
            widgets += [page.download_status, page.progress, page.cancel]
        for widget in widgets:
            assert widget.isVisible()
            assert (
                widget.mapTo(window.workspace, widget.rect().topRight()).x()
                < overlay.geometry().left()
            )
        if assembly_state in ("fallback", "model"):
            QTest.mouseClick(page.next_step, Qt.MouseButton.LeftButton)
            assert page.step == 1
        else:
            assert page.view_host.isHidden()

        compact_width = page.notes.viewport().width()
        window.lessons.set_panel_expanded(False)
        qt_app.processEvents()
        QTest.qWait(30)
        assert window.lessons.assembly_host._overlay_clearance == 0
        if assembly_state in ("fallback", "model"):
            assert page.notes.viewport().width() > compact_width
        else:
            assert page.view_host.isVisible()

        window.lessons.set_panel_expanded(True)
        qt_app.processEvents()
        QTest.qWait(30)
        assert overlay.isVisible()
        assert (
            page.notes.mapTo(window.workspace, page.notes.rect().topRight()).x()
            < overlay.geometry().left()
        )
        if assembly_state in ("loading", "failure"):
            assert page.view_host.isHidden()
    finally:
        window.close()
        window.deleteLater()


@pytest.mark.parametrize("width, minimum_code", [(800, 340), (930, 350)])
def test_compact_tasks_leave_block_editor_commands_and_code_visible(
    tmp_path, qt_app, width, minimum_code
):
    from pathlib import Path

    from PySide6.QtCore import Qt

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.confirm_close = lambda *_: True
    window.resize(width, 620)
    window.show()
    try:
        window.change_language("ru")
        window.lessons.open(Path("lessons/first_python"))
        window.console_dock.show()
        window.set_mode(3)
        qt_app.processEvents()
        editor = window.block_editor
        browser_before = editor.browser_pane.isVisible()
        window.lessons.set_panel_expanded(True)
        qt_app.processEvents()

        overlay = window.lessons.overlay
        assert overlay.isVisible()
        assert not editor.browser_pane.isVisible()
        assert editor.preview_splitter.orientation() == Qt.Orientation.Vertical
        assert editor.code.viewport().width() >= minimum_code
        assert editor.code.viewport().height() >= 140
        assert editor.focus_preview.isVisible()
        assert not editor.preview_top.isVisible()
        assert editor.metadata_bar.isVisible()
        assert not editor.caption.isVisible()
        assert editor.level.width() >= 100
        assert editor.icon.width() >= 165
        assert editor.color.width() >= 135
        source = editor.code.toPlainText()
        assert window.workspace.width() - overlay.width() >= 500
        save_edge = editor.save_button.mapTo(
            window.workspace, editor.save_button.rect().topRight()
        ).x()
        assert save_edge < overlay.geometry().left()

        editor.focus_preview.click()
        qt_app.processEvents()
        assert editor.preview_top.isVisible()
        assert not editor.code_stack.isVisible()
        assert editor.preview_stack.height() >= 90
        assert editor.focus_preview.toolTip() == "Исходный код Python"

        window.console_dock.hide()
        qt_app.processEvents()
        assert not editor.focus_preview.isVisible()
        assert editor.preview_top.isVisible() and editor.code_stack.isVisible()
        window.console_dock.show()
        qt_app.processEvents()
        assert editor.focus_preview.isVisible()
        assert not editor.preview_top.isVisible() and editor.code_stack.isVisible()

        window.lessons.set_panel_expanded(False)
        qt_app.processEvents()
        assert editor.browser_pane.isVisible() == browser_before
        assert editor.level.isVisible()
        assert not editor.focus_preview.isVisible()
        assert editor.preview_top.isVisible() and editor.code_stack.isVisible()
        assert not editor.metadata_bar.isVisible()
        assert editor.caption.isVisible()
        assert editor.code.toPlainText() == source
    finally:
        window.close()
        window.deleteLater()


def test_compact_tasks_leave_manual_controls_accessible(tmp_path, qt_app):
    from pathlib import Path

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.pybricks.devices import HubInfo
    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.confirm_close = lambda *_: True
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.show()
    try:
        window.change_language("ru")
        window.lessons.open(Path("lessons/first_python"))
        window.console_dock.show()
        window.set_mode(1)
        window.lessons.set_panel_expanded(True)
        qt_app.processEvents()
        QTest.qWait(50)

        controls = window.controls
        overlay = window.lessons.overlay
        scroll = controls.parentWidget().parentWidget()
        assert overlay.isVisible() and controls.compact_actions.isVisible()
        assert scroll.horizontalScrollBar().maximum() == 0
        for widget in (
            controls.controller.left,
            controls.controller.right,
            *controls.controller.triggers,
        ):
            assert (
                widget.mapTo(window.workspace, widget.rect().topRight()).x()
                < overlay.geometry().left()
            )
            assert qt_app.widgetAt(widget.mapToGlobal(widget.rect().center())) is widget
        for label in controls.controller.stick_labels:
            assert label.visibleRegion().boundingRect().height() == label.height()

        controls.update_info(
            HubInfo(
                connected=True,
                monitoring=True,
                ports={port: {"type": "motor"} for port in "AB"},
            )
        )
        qt_app.processEvents()
        QTest.qWait(80)
        for port, key, prefix in (("A", "left_x", "LX"), ("B", "left_y", "LY")):
            source = controls.rows[port][0]
            source.setCurrentIndex(source.findData(key))
            assert source.width() <= 80, (
                window.width(),
                controls.width(),
                controls.table.width(),
                source.width(),
            )
            visible = source.fontMetrics().elidedText(
                source.currentText(), Qt.TextElideMode.ElideRight, source.width() - 24
            )
            assert visible.startswith(prefix + " ·")
        assert controls.table.horizontalScrollBar().maximum() == 0

        right = controls.controller.right
        point = QPoint(75, 50)
        QTest.mousePress(right, Qt.MouseButton.LeftButton, pos=point)
        assert right.x_value > 0.5
        QTest.mouseRelease(right, Qt.MouseButton.LeftButton, pos=point)
        assert right.x_value == 0

        controls.target.setCurrentIndex(1)
        qt_app.processEvents()
        QTest.qWait(30)
        assert scroll.horizontalScrollBar().maximum() == 0
        scroll.ensureWidgetVisible(right)
        qt_app.processEvents()
        assert qt_app.widgetAt(right.mapToGlobal(right.rect().center())) is right

        window.lessons.set_panel_expanded(False)
        qt_app.processEvents()
        QTest.qWait(30)
        assert not controls.compact_actions.isVisible()
        assert scroll.horizontalScrollBar().maximum() == 0
    finally:
        window.close()
        window.deleteLater()


@pytest.mark.parametrize("width", [800, 1100])
def test_compact_lesson_help_shows_first_task_with_console_open(
    tmp_path, qt_app, width
):
    from pathlib import Path

    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.confirm_close = lambda *_: True
    window.setMinimumWidth(0)
    window.resize(width, 620)
    window.show()
    try:
        window.change_language("ru")
        window.lessons.open(Path("lessons/first_python"))
        window.console_dock.show()
        window.lessons.set_panel_expanded(True)
        window.help_page.show_lesson_home(window.lessons.current.lesson)
        QTest.qWait(90)

        browser = window.help_page.browser
        first_task = browser.document().find("Придумай своё сообщение")
        assert not first_task.isNull()
        assert browser.verticalScrollBar().value() == 0
        assert (
            browser.viewport().rect().contains(browser.cursorRect(first_task).center())
        )
        help_page = window.help_page
        overlay = window.lessons.overlay
        assert not help_page.sidebar.isVisible()
        assert help_page.back_button.isVisible()
        assert help_page.recent_button.isVisible()
        assert help_page.find_field.width() >= 260
        assert browser.document().documentMargin() == 14
        for button in (help_page.back_button, help_page.recent_button):
            assert (
                button.mapTo(window.workspace, button.rect().topRight()).x()
                < overlay.geometry().left()
            )

        help_page.show_page("robotics.md")
        qt_app.processEvents()
        assert help_page.back_button.isEnabled()
        assert help_page.recent_button.isEnabled()
        QTest.mouseClick(help_page.back_button, Qt.MouseButton.LeftButton)
        assert help_page.current == "lesson/instructions"
        assert not overlay.isVisible()
        assert help_page.sidebar.isVisible()
        assert any(
            action.data() == "robotics.md" for action in help_page.recent_menu.actions()
        )
    finally:
        window.close()
        window.deleteLater()


def test_help_destination_link_clears_compact_task_overlay(tmp_path, qt_app):
    from pathlib import Path

    from PySide6.QtCore import QUrl
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.confirm_close = lambda *_: True
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.show()
    try:
        window.lessons.open(Path("lessons/first_python"))
        window.lessons.set_panel_expanded(True)
        QTest.qWait(70)
        assert window.pages.currentIndex() == 2
        assert window.lessons.overlay.isVisible()

        window.help_page.follow_link(QUrl("program:main.py"))
        QTest.qWait(30)
        assert window.pages.currentIndex() == 0
        assert window.document_page.lesson_project is window.lessons.current
        assert not window.lessons.overlay.isVisible()
        assert window.lessons.progress_button.isVisible()
    finally:
        window.close()
        window.deleteLater()


def test_lesson_connect_link_keeps_an_existing_hub_connected(
    tmp_path, qt_app, monkeypatch
):
    from pathlib import Path

    from PySide6.QtCore import QUrl

    from little_tinker_rig.pybricks.devices import HubInfo
    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.confirm_close = lambda *_: True
    window.show()
    try:
        window.lessons.open(Path("lessons/first_python"))
        window.update_hub(HubInfo(connected=True, transport="virtual"))
        disconnected = []
        monkeypatch.setattr(window, "disconnect_hub", lambda: disconnected.append(True))

        window.help_page.follow_link(QUrl("connect:"))
        assert not disconnected
        assert window.device_dock.isVisible()
    finally:
        window.close()
        window.deleteLater()


def test_first_lesson_connect_links_choose_virtual_hub(tmp_path, qt_app, monkeypatch):
    from pathlib import Path

    from PySide6.QtCore import QUrl
    from PySide6.QtWidgets import QDialog

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.device import ConnectDialog

    choices = []

    def reject_after_inspection(dialog):
        choices.append((dialog.transport.currentData(), dialog.model.currentData()))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(ConnectDialog, "exec", reject_after_inspection)
    window = Studio(tmp_path / "plain.py")
    window.confirm_close = lambda *_: True
    window.show()
    try:
        window.lessons.open(Path("lessons/first_python"))
        run_link = window.lessons.current.lesson.stages[-1]["links"][0]
        assert run_link["target"] == "virtual"
        window.lessons.select_stage(2)
        body = window.lessons.cards["run"]["body"]
        window.lessons.follow_task_anchor("run", QUrl("task:extra/0"), body)
        window.help_page.follow_link(QUrl("connect:virtual"))
        assert choices == [("virtual", "inventor"), ("virtual", "inventor")]

        ordinary = ConnectDialog(window)
        assert ordinary.transport.currentData() == "virtual"
        ordinary.close()
    finally:
        window.close()
        window.deleteLater()


def test_bundled_lesson_sections_share_one_help_document(tmp_path, qt_app):
    from pathlib import Path

    from PySide6.QtCore import QPoint, QUrl

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.theme import colors

    source = Path(__file__).resolve().parents[1] / "lessons" / "first_drive"
    window = Studio(tmp_path / "plain.py")
    original_theme = window.visual_theme
    window.resize(1024, 768)
    window.show()
    try:
        window.lessons.open(source)
        qt_app.processEvents()
        assert window.pages.currentIndex() == 2
        assert window.help_page.current == "lesson/instructions"
        assert window.help_page.lesson_group.childCount() == 1
        assert "Build a rolling base" in window.help_page.browser.toPlainText()
        assert "Stop before the obstacle" in window.help_page.browser.toPlainText()
        window.lessons.select_stage(2)
        window.lessons.show_stage()
        qt_app.processEvents()
        first = window.help_page.current
        first_scroll = window.help_page.browser.verticalScrollBar().value()
        assert first == "lesson/instructions#drive"
        assert window.pages.currentIndex() == 2
        assert window.lessons.progress_button.isVisible()
        assert "Build a rolling base" in window.help_page.browser.toPlainText()
        assert "Stop before the obstacle" in window.help_page.browser.toPlainText()
        window.change_language("ru")
        qt_app.processEvents()
        assert window.help_page.current == "lesson/instructions#drive"
        assert (
            "Первая поездка"
            in window.help_page.browser.cursorForPosition(QPoint(20, 20)).block().text()
        )
        window.change_language("en")
        window.lessons.select_stage(5)
        window.lessons.show_stage()
        qt_app.processEvents()
        assert window.help_page.current == "lesson/instructions#stop"
        assert window.help_page.browser.verticalScrollBar().value() > first_scroll
        assert window.help_page.page_paths["lesson/instructions"].name == "en.md"
        assert window.help_page.lesson_group.childCount() == 1
        window.change_language("ru")
        qt_app.processEvents()
        assert window.help_page.current == "lesson/instructions#stop"
        assert "Остановись перед препятствием" in window.help_page.browser.toPlainText()
        assert window.help_page.lesson_group.childCount() == 1
        window.help_page.tree.itemClicked.emit(window.help_page.lesson_item, 0)
        assert window.help_page.current == "lesson/instructions"
        assert window.help_page.browser.verticalScrollBar().value() == 0
        window.lessons.show_stage()
        assert window.help_page.current == "lesson/instructions#stop"
        window.lessons.open(source)
        assert window.help_page.current == "lesson/instructions#stop"
        assert window.pages.currentIndex() == 2
        window.change_visual_theme("light" if original_theme == "dark" else "dark")
        badge = window.help_page.browser.document().resource(
            window.help_page.browser.document().ResourceType.ImageResource,
            QUrl("lesson-number:1"),
        )
        assert badge.pixelColor(13, 4).name() == colors()["accent"]
        window.open_document(tmp_path / "plain.py")
        assert window.help_page.lesson is None
        assert not window.help_page.current.startswith("lesson/")
    finally:
        window.change_visual_theme(original_theme)
        window.recovery.close()
        window.deleteLater()


def test_language_switch_keeps_task_section_with_localized_anchor(tmp_path, qt_app):
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.help import HelpPage

    root = tmp_path / "translated"
    root.mkdir()
    (root / "en.md").write_text(
        "# Training\n\n## First\n\n"
        + "Start here.\n\n" * 35
        + "## Second\n\n"
        + "Continue here.\n\n" * 35,
        encoding="utf-8",
    )
    (root / "ru.md").write_text(
        "# Обучение\n\n## Первый\n\n"
        + "Начни здесь.\n\n" * 35
        + "## Второй\n\n"
        + "Продолжай здесь.\n\n" * 35,
        encoding="utf-8",
    )
    (root / "lesson.json").write_text(
        json.dumps(
            {
                "format": 1,
                "id": "translated",
                "title": {"en": "Training", "ru": "Обучение"},
                "instructions": {"en": "en.md", "ru": "ru.md"},
                "stages": [
                    {
                        "id": "first",
                        "title": {"en": "First", "ru": "Первый"},
                        "description": {"en": "en.md#first", "ru": "ru.md#первый"},
                    },
                    {
                        "id": "second",
                        "title": {"en": "Second", "ru": "Второй"},
                        "description": {"en": "en.md#second", "ru": "ru.md#второй"},
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    lesson = Lesson.load(root)
    previous_language = language()
    set_language("en")
    page = HelpPage([])
    page.resize(760, 520)
    page.show()
    try:
        page.show_lesson_stage(lesson, lesson.stages[1])
        QTest.qWait(30)
        assert page.current == "lesson/instructions#second"
        assert page.browser.verticalScrollBar().value() > 0

        set_language("ru")
        page.retranslate()
        QTest.qWait(30)
        assert page.current == "lesson/instructions#второй"
        assert "Продолжай здесь." in page.browser.toPlainText()
        assert page.browser.verticalScrollBar().value() > 0
        assert "Второй" in page.browser.cursorForPosition(QPoint(24, 24)).block().text()
    finally:
        set_language(previous_language)
        page.close()
        page.deleteLater()


def test_language_switch_keeps_localized_task_material_in_help_history(
    tmp_path, qt_app
):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.help import HelpPage

    root = tmp_path / "materials"
    root.mkdir()
    (root / "en.md").write_text(
        "# Training\n\n## First\n\nStart here.\n", encoding="utf-8"
    )
    (root / "ru.md").write_text(
        "# Обучение\n\n## Первый\n\nНачни здесь.\n", encoding="utf-8"
    )
    (root / "extra_en.md").write_text(
        "# More\n\n## Details\n\nEnglish details.\n", encoding="utf-8"
    )
    (root / "extra_ru.md").write_text(
        "# Ещё\n\n## Подробности\n\nРусские подробности.\n", encoding="utf-8"
    )
    (root / "lesson.json").write_text(
        json.dumps(
            {
                "format": 1,
                "id": "materials",
                "title": {"en": "Training", "ru": "Обучение"},
                "instructions": {"en": "en.md", "ru": "ru.md"},
                "stages": [
                    {
                        "id": "first",
                        "title": {"en": "First", "ru": "Первый"},
                        "description": {"en": "en.md#first", "ru": "ru.md#первый"},
                        "links": [
                            {
                                "kind": "markdown",
                                "label": {"en": "More", "ru": "Подробнее"},
                                "target": {
                                    "en": "extra_en.md#details",
                                    "ru": "extra_ru.md#подробности",
                                },
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    lesson = Lesson.load(root)
    previous_language = language()
    set_language("en")
    page = HelpPage([])
    page.show()
    qt_app.processEvents()
    try:
        page.show_lesson_stage(lesson, lesson.stages[0])
        page.show_lesson_material(lesson, "extra_en.md#details", "More")
        assert page.current == "lesson/resource/extra_en.md#details"
        page.back()
        assert page.current == "lesson/instructions#first"
        page.search.setText("English details.")
        page.search.setFocus()
        QTest.keyClick(page.search, Qt.Key.Key_Return)
        assert page.current == "lesson/resource/extra_en.md#details"
        page.back()
        assert page.current == "lesson/instructions#first"
        page.tree.itemClicked.emit(page.lesson_item, 0)
        assert page.current == "lesson/resource/extra_en.md#details"
        page.search.clear()
        assert page.history[-1] == "lesson/instructions#first"
        page.back()
        english_action = next(
            action
            for action in page.recent_menu.actions()
            if action.data() == "lesson/resource/extra_en.md#details"
        )
        assert english_action.text() == "Training · More"
        english_action.trigger()

        page.search.setText("English details.")
        set_language("ru")
        page.retranslate()
        assert page.current == "lesson/resource/extra_ru.md#подробности"
        assert not page.search.text()
        assert not page.lesson_item.isHidden()
        assert page.page_paths["lesson/resource/extra_ru.md"] == root / "extra_ru.md"
        assert "Русские подробности." in page.browser.toPlainText()
        assert page.history[-1] == "lesson/instructions#первый"

        page.back()
        assert page.current == "lesson/instructions#первый"
        resource_action = next(
            action
            for action in page.recent_menu.actions()
            if action.data() == "lesson/resource/extra_ru.md#подробности"
        )
        assert resource_action.text() == "Обучение · Подробнее"
        resource_action.trigger()
        assert page.current == "lesson/resource/extra_ru.md#подробности"
        instruction_action = next(
            action
            for action in page.recent_menu.actions()
            if action.data() == "lesson/instructions#первый"
        )
        instruction_action.trigger()
        assert page.current == "lesson/instructions#первый"

        set_language("en")
        page.retranslate()
        assert page.current == "lesson/instructions#first"
        english_resource = next(
            action
            for action in page.recent_menu.actions()
            if action.data() == "lesson/resource/extra_en.md#details"
        )
        english_resource.trigger()
        assert page.current == "lesson/resource/extra_en.md#details"
    finally:
        set_language(previous_language)
        page.deleteLater()


def test_instruction_heading_numbers_match_task_panel_order(tmp_path, qt_app):
    from pathlib import Path

    from little_tinker_rig.qt.help import HelpPage

    root = Path(__file__).resolve().parents[1] / "lessons"
    sources = [path.parent for path in root.rglob("lesson.json")]
    sources.append(make_lesson(tmp_path))
    original_language = language()
    page = HelpPage([])
    try:
        for code in ("en", "ru"):
            set_language(code)
            for source in sources:
                lesson = Lesson.load(source)
                page.show_lesson_home(lesson)
                expected = {
                    lesson.instructions_anchor(stage, code): index
                    for index, stage in enumerate(lesson.stages, 1)
                }
                numbered = {}
                index_badges = {}
                block = page.browser.document().begin()
                while block.isValid():
                    item = block.begin()
                    while not item.atEnd():
                        fragment = item.fragment()
                        fmt = fragment.charFormat()
                        anchor = fmt.anchorHref().removeprefix("#")
                        if fmt.isImageFormat() and anchor in expected:
                            number = expected[anchor]
                            assert fmt.toImageFormat().name() == (
                                f"lesson-number:{number}"
                            )
                            assert block.textList() is None
                            index_badges[anchor] = number
                        item += 1
                    if block.blockFormat().headingLevel() == 2:
                        fragments = []
                        item = block.begin()
                        while not item.atEnd():
                            fragments.append(item.fragment())
                            item += 1
                        names = {
                            name
                            for fragment in fragments
                            for name in fragment.charFormat().anchorNames()
                        }
                        anchors = names & expected.keys()
                        if anchors:
                            assert len(anchors) == 1
                            anchor = anchors.pop()
                            number = expected[anchor]
                            image = fragments[0].charFormat().toImageFormat()
                            assert image.name() == f"lesson-number:{number}"
                            assert image.width() == image.height() == 26
                            numbered[anchor] = number
                    block = block.next()
                assert numbered == expected
                assert index_badges == expected
                index_text = page.pages["lesson/instructions"][0]
                assert all(f"](#{anchor})" in index_text for anchor in expected)
                page.show_lesson_stage(lesson, lesson.stages[-1])
                assert page.current == (
                    "lesson/instructions#"
                    + lesson.instructions_anchor(lesson.stages[-1], code)
                )
    finally:
        set_language(original_language)
        page.deleteLater()


def test_lesson_index_badge_opens_its_instruction_section(qt_app):
    from pathlib import Path

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.help import HelpPage

    lesson = Lesson.load(Path("lessons/first_python"))
    page = HelpPage([])
    page.resize(900, 650)
    page.show()
    try:
        page.show_lesson_home(lesson)
        browser = page.browser
        block = browser.document().begin()
        badge_position = None
        while block.isValid() and badge_position is None:
            item = block.begin()
            while not item.atEnd():
                fragment = item.fragment()
                fmt = fragment.charFormat()
                if fmt.isImageFormat() and fmt.anchorHref() == "#message":
                    badge_position = fragment.position()
                    break
                item += 1
            block = block.next()
        assert badge_position is not None
        cursor = QTextCursor(browser.document())
        cursor.setPosition(badge_position)
        point = browser.cursorRect(cursor).center()
        assert browser.viewport().rect().contains(point)
        QTest.mouseClick(browser.viewport(), Qt.MouseButton.LeftButton, pos=point)
        assert page.current == "lesson/instructions#message"
    finally:
        page.close()
        page.deleteLater()


def test_first_drive_illustrations_render_in_both_languages_and_export(
    tmp_path, qt_app
):
    from io import BytesIO
    from pathlib import Path
    from zipfile import ZipFile

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextDocument

    from little_tinker_rig.core.lessons import pack
    from little_tinker_rig.qt.app import Studio

    source = Path(__file__).resolve().parents[1] / "lessons" / "first_drive"
    window = Studio(tmp_path / "plain.py")
    window.resize(1380, 880)
    window.show()
    try:
        window.lessons.open(source, new=True)
        for _ in range(4):
            qt_app.processEvents()

        def images(browser):
            result = []
            block = browser.document().begin()
            while block.isValid():
                fragment = block.begin()
                while not fragment.atEnd():
                    item = fragment.fragment()
                    if item.charFormat().isImageFormat():
                        fmt = item.charFormat().toImageFormat()
                        image = browser.document().resource(
                            QTextDocument.ResourceType.ImageResource, QUrl(fmt.name())
                        )
                        assert image is not None and image.width() > 0
                        assert 0 < fmt.width() <= browser.viewport().width()
                        if not fmt.name().startswith("lesson-number:"):
                            result.append(fmt.name())
                    fragment += 1
                block = block.next()
            return result

        assert len(images(window.help_page.browser)) == 3
        assert len(images(window.lessons.cards["build"]["body"])) == 1
        window.change_visual_theme("dark")
        window.change_language("ru")
        for _ in range(4):
            qt_app.processEvents()
        assert len(images(window.help_page.browser)) == 3
        assert len(images(window.lessons.cards["build"]["body"])) == 1
        assert "Вид колёсной базы" in (source / "ru.md").read_text(encoding="utf-8")
        with ZipFile(BytesIO(pack(source))) as archive:
            assert all(
                f"illustrations/{name}.svg" in archive.namelist()
                for name in ("rolling-base", "motion", "obstacle")
            )
    finally:
        window.recovery.close()
        window.deleteLater()


def test_task_status_stays_below_illustrated_card_after_workspace_resize(
    tmp_path, qt_app
):
    from pathlib import Path

    from little_tinker_rig.qt.app import Studio

    source = Path(__file__).resolve().parents[1] / "lessons" / "first_drive"
    window = Studio(tmp_path / "plain.py")
    window.resize(1380, 880)
    window.show()
    try:
        window.lessons.open(source, new=True)
        window.change_visual_theme("dark")
        window.change_language("ru")
        window.set_mode(2)
        for _ in range(4):
            qt_app.processEvents()
        window.set_mode(0)
        window.resize(930, 620)
        for _ in range(4):
            qt_app.processEvents()
        window.resize(1380, 880)
        window.set_mode(4)
        for _ in range(4):
            qt_app.processEvents()
        card = window.lessons.cards["build"]
        assert card["status"].geometry().top() > card["body"].geometry().bottom()
    finally:
        window.recovery.close()
        window.deleteLater()


def test_task_title_navigates_checkbox_stays_put_and_help_finds_text(tmp_path, qt_app):
    from pathlib import Path

    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    source = Path(__file__).resolve().parents[1] / "lessons" / "first_drive"
    window = Studio(tmp_path / "plain.py")
    window.resize(1440, 900)
    window.show()
    try:
        window.lessons.open(source, new=True)
        help_page = window.help_page
        assert help_page.lesson_item.text(0).startswith("First drive")
        assert "Tasks in this lesson" in help_page.browser.toPlainText()
        window.lessons.cards["experiment"]["title"].click()
        qt_app.processEvents()
        assert window.lessons.current.stage["id"] == "experiment"
        assert help_page.current == "lesson/instructions#experiment"
        assert window.lessons.cards["experiment"]["body"].isVisible()
        assert not window.lessons.cards["build"]["body"].isVisible()
        window.lessons.cards["build"]["check"].setChecked(True)
        assert window.lessons.current.stage["id"] == "experiment"
        assert help_page.current == "lesson/instructions#experiment"
        QTest.keyClick(
            help_page.browser, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier
        )
        assert help_page.find_field.isVisible()
        help_page.find_field.setText("motor")
        assert len(help_page.find_matches) > 1
        first = help_page.find_index
        help_page.next_match(1)
        assert help_page.find_index != first
        before = help_page.browser.verticalScrollBar().value()
        help_page.find_field.setText("no-such-lesson-word-99321")
        assert help_page.find_count.text() == "0/0"
        assert help_page.browser.verticalScrollBar().value() == before
        QTest.keyClick(help_page.find_field, Qt.Key.Key_Escape)
        assert help_page.find_field.isVisible()
        assert not help_page.find_field.text()
        assert not help_page.find_count.isVisible()
        assert help_page.current == "lesson/instructions#experiment"
        assert 'href="devices:"' in help_page.browser.toHtml()
        help_page.follow_link(QUrl("devices:"))
        assert window.device_dock.isVisible()
        window.lessons.select_stage(1)
        body = window.lessons.cards["connect"]["body"]
        assert "Hub and devices" in body.toPlainText()
        window.lessons.follow_task_anchor("connect", QUrl("task:extra/2"), body)
        assert window.device_dock.isVisible()
    finally:
        window.recovery.close()
        window.deleteLater()


def test_task_title_waits_for_invalid_block_parameter(tmp_path, qt_app):
    from pathlib import Path

    from little_tinker_rig.qt.app import Studio

    source = Path(__file__).resolve().parents[1] / "lessons" / "first_python"
    window = Studio(tmp_path / "plain.py")
    window.resize(1440, 900)
    window.show()
    try:
        window.lessons.open(source, new=True)
        window.set_mode(0)
        slot = next(
            slot
            for slot in window.source.parameter_slots
            if slot.parameter.name == "argument 1"
        )
        window.source.show_parameter(slot)
        field = window.source.parameter_editor.line_edit
        field.setText("1 +")
        previous_help = window.help_page.current

        window.lessons.cards["repeat"]["title"].click()
        qt_app.processEvents()
        assert window.lessons.current.stage["id"] == "message"
        assert window.help_page.current == previous_help
        assert window.pages.currentIndex() == 0
        assert field.isVisible() and field.text() == "1 +"

        field.setText("4")
        window.lessons.cards["repeat"]["title"].click()
        qt_app.processEvents()
        assert window.lessons.current.stage["id"] == "repeat"
        assert window.help_page.current == "lesson/instructions#repeat"
        assert window.pages.currentIndex() == 2
        assert "range(4)" in window.document_page.text
    finally:
        window.recovery.close()
        window.deleteLater()


def test_guided_lessons_and_exploration_projects_are_separate(tmp_path, qt_app):
    from pathlib import Path

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    try:
        window.lessons.populate()
        menus = {
            action.text(): action.menu()
            for action in window.lessons.menu.actions()
            if action.menu()
        }
        assert "Guided lessons" in menus
        assert "Explore projects" in menus
        assert any(
            "First drive" in action.text()
            for action in menus["Guided lessons"].actions()
        )
        assert any(action.menu() for action in menus["Explore projects"].actions())
        project = (
            Path(__file__).resolve().parents[1] / "lessons/pybricks/spike_45678_cnc"
        )
        window.lessons.open(project, new=True)
        assert window.lessons.progress_button.text().startswith("Project ·")
        assert window.help_page.lesson_group.text(0) == "This project"
        assert "Activities in this project" in window.help_page.browser.toPlainText()
        window.change_language("ru")
        assert window.lessons.progress_button.text().startswith("Проект ·")
        assert window.help_page.lesson_group.text(0) == "Этот проект"
        assert window.help_page.back_button.toolTip() == "Назад"
        assert window.help_page.recent_button.toolTip() == "Недавние страницы"
        assert window.help_page.search.placeholderText() == "Поиск в справке…"
    finally:
        window.recovery.close()
        window.deleteLater()


def test_missing_task_recommendation_keeps_lesson_usable(tmp_path, qt_app, monkeypatch):
    from little_tinker_rig.qt.app import Studio

    root = make_lesson(tmp_path)
    data = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    data["stages"][0]["blocks"] = ["removed/block"]
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    window = Studio(tmp_path / "plain.py")
    monkeypatch.setattr(window, "error", lambda message: pytest.fail(message))
    try:
        page = window.lessons.open(root)
        assert page.lesson_project is window.lessons.current
        assert "removed/block" in window.lessons.status.text()
        assert len(window.lessons.cards) == 2
    finally:
        window.recovery.close()
        window.deleteLater()


@pytest.mark.parametrize("decision", ["Discard", "Save", "Cancel"])
def test_window_close_decides_once_for_whole_lesson_project(
    tmp_path, qt_app, monkeypatch, decision
):
    from zipfile import ZipFile

    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    try:
        first = window.lessons.open(make_lesson(tmp_path))
        project = first.lesson_project
        project.path = tmp_path / "lesson.ltr"
        first.session.editor.commit("first = 1\n")
        window.lessons.new_program()
        second = window.document_page
        second.session.editor.commit("second = 2\n")
        window.lessons.save(project)
        saved = project.path.read_bytes()
        # A clean first tab must not hide changes in a later tab of its archive.
        if decision != "Save":
            first.session.editor.commit("first = 10\n")
        second.change_mode(1)
        second.code.setPlainText("second = 20\n")
        texts = [first.text, second.text]
        names = [
            p.session.project.path.relative_to(project.root).as_posix()
            for p in (first, second)
        ]
        prompts = []

        def answer(parent, title, message, *args):
            prompts.append(message)
            return (
                getattr(QMessageBox.StandardButton, decision)
                if len(prompts) == 1
                else QMessageBox.StandardButton.Save
            )

        monkeypatch.setattr(QMessageBox, "question", answer)
        assert window.close() == (decision != "Cancel")
        assert len(prompts) == 1
        assert "lesson.ltr" in prompts[0] and "local attempt" in prompts[0]
        if decision == "Save":
            with ZipFile(project.path) as archive:
                assert [archive.read(name).decode() for name in names] == texts
        else:
            assert project.path.read_bytes() == saved
        if decision == "Cancel":
            assert project.root.is_dir()
            assert [first.text, second.text] == texts
            assert window.documents.count() == 3
    finally:
        monkeypatch.setattr(
            QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Discard
        )
        window.close()


def test_task_recommendations_keep_full_catalog_and_source(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.library import IDENTITY

    window = Studio(tmp_path / "plain.py")
    try:
        page = window.lessons.open(make_lesson(tmp_path))
        page.session.document.commit("drive.straight(100)\n")
        page.session.editor.select(0)
        before = page.text
        window.lessons.select_stage(1)
        assert page.text == before
        assert not page.lesson_project.progress["completed"]
        assert window.source.expression_ids is None
        assert window.level_filter.isEnabled()
        window.library.set_view("lesson")
        visible = {
            card.data(0, IDENTITY)
            for card in window.library.rows.values()
            if not card.isHidden()
        }
        assert visible <= {"pybricks/drive/brake"}
        assert len(page.session.snippets) > 20
        window.library.set_view("catalog")
        visible = {
            card.data(0, IDENTITY)
            for card in window.library.rows.values()
            if not card.isHidden()
        }
        assert len(visible) > 1
        page.change_mode(1)
        page.code.setPlainText("if distance >\n")
        page.session.document.commit(
            page.session.document.state.source, ("spare = 1\n",)
        )
        page.session.editor.select(0)
        project = page.lesson_project
        project.path = tmp_path / "work.ltr"
        assert window.lessons.save(project)
        opened = StudentProject.open(project.path)
        assert opened.main.read_text() == "if distance >\n"
        assert opened.progress["stage"] == "stop"
    finally:
        window.recovery.close()
        window.deleteLater()


def test_lesson_navigation_opens_instructions_and_preserves_explicit_moves(
    tmp_path, qt_app
):
    from PySide6.QtCore import Qt

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.show()
    try:
        page = window.lessons.open(make_lesson(tmp_path))
        lesson = window.lessons
        assert window.pages.currentIndex() == 2
        assert window.help_page.current == "lesson/instructions"
        assert lesson.panel.isVisible()
        assert window.pages.count() == 6
        assert window.pages.widget(5) is window.home_page
        window.set_mode(2)
        assert lesson.panel.isVisible()
        window.set_mode(3)
        assert lesson.panel.isVisible()
        assert not lesson.actions["previous"].isEnabled()
        assert lesson.actions["next"].isEnabled()
        lesson.actions["next"].trigger()
        assert lesson.current.stage["id"] == "stop"
        assert window.pages.currentIndex() == 3
        assert not lesson.current.progress["completed"]
        assert not lesson.actions["next"].isEnabled()
        lesson.actions["previous"].trigger()
        assert lesson.current.stage["id"] == "drive"
        assert "Next hint" not in lesson.cards["drive"]["body"].toPlainText()
        assert "Open starter program" not in lesson.cards["drive"]["body"].toPlainText()
        lesson.open_task_program()
        assert window.pages.currentIndex() == 0
        assert lesson.panel.isVisible()
        page.session.editor.commit("drive.straight(200)\n")
        lesson.cards["drive"]["check"].setChecked(True)
        assert lesson.cards["drive"]["check"].checkState() == Qt.CheckState.Checked
        assert lesson.current.score == (1, 2)
        assert window.pages.currentIndex() == 0
        assert lesson.actions["next"].isEnabled()
        lesson.actions["next"].trigger()
        assert window.pages.currentIndex() == 0
        assert lesson.current.stage["id"] == "stop"
        assert page.text == "drive.straight(200)\n"
        lesson.guidance.trigger()
        qt_app.processEvents()
        assert not lesson.panel.isVisible()
        assert lesson.progress_button.isVisible()
        window.set_mode(1)
        project = lesson.current
        project.path = tmp_path / "work.ltr"
        lesson.save(project)
        window.open_document(tmp_path / "plain.py")
        qt_app.processEvents()
        assert not lesson.progress_button.isVisible()
        lesson.open(project.path)
        assert window.pages.currentIndex() == 2
        assert window.help_page.current == "lesson/instructions#task-stop"
        assert not lesson.guidance.isChecked()
        lesson.guidance.trigger()
        assert lesson.panel.isVisible()
        window.confirm_close = lambda *_: True
        window.close_document(window.documents.currentIndex())
        page = lesson.open(project.path)
        assert window.pages.currentIndex() == 2
        assert window.help_page.current == "lesson/instructions#task-stop"
        assert page.text == "drive.straight(200)\n"
        assert lesson.guidance.isChecked()
        assert lesson.panel.isVisible()
    finally:
        window.confirm_close = lambda *_: True
        window.close()
        window.deleteLater()


def test_independent_assembly_survives_lesson_and_document_changes(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    (tmp_path / "robot.ldr").write_text("0 Original model\n")
    path = tmp_path / "robot.json"
    path.write_text(
        json.dumps({"format": 1, "model": "robot.ldr", "steps": {"1": {}, "2": {}}})
    )
    window = Studio(tmp_path / "plain.py")
    try:
        assembly = window.lessons.assembly_host
        assembly.open(path)
        viewer = assembly.free_page
        viewer.set_step(1)
        assert not viewer.attempted  # Loading stays lazy until Assembly is shown.
        page = window.lessons.open(make_lesson(tmp_path))
        window.open_document(tmp_path / "plain.py")
        assert window.lessons.current is None
        assert not window.modes.item(4).isHidden()
        assert assembly.free_page is viewer and viewer.step == 1
        assert assembly.pages.currentWidget() is viewer
        before = page.lesson_project.progress.copy()
        viewer.set_step(0)
        assert page.lesson_project.progress == before
        assert json.loads(window.settings.value("assembly/state"))["step"] == 0
    finally:
        window.confirm_close = lambda *_: True
        window.close()
        window.deleteLater()


@pytest.mark.parametrize(
    "saved_state",
    [
        [],
        {"step": "bad"},
        {"step": True},
        {"step": 10**400},
        {"camera": {"center": [0, 0, 0], "extent": "wide", "yaw": 0, "pitch": 0}},
        {"camera": {"center": [10**400, 0, 0], "extent": 10, "yaw": 0, "pitch": 0}},
    ],
)
def test_free_assembly_discards_invalid_saved_view_state(
    tmp_path, qt_app, monkeypatch, saved_state
):
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QShowEvent

    from little_tinker_rig.qt.assembly import AssemblyPage, AssemblyWorkspace

    (tmp_path / "robot.ldr").write_text("0 Robot\n", encoding="utf-8")
    path = tmp_path / "robot.json"
    path.write_text(json.dumps({"format": 1, "model": "robot.ldr"}), encoding="utf-8")
    settings = QSettings(str(tmp_path / "assembly.ini"), QSettings.Format.IniFormat)
    settings.setValue("assembly/path", str(path))
    settings.setValue("assembly/state", json.dumps(saved_state))
    monkeypatch.setattr(AssemblyPage, "load", lambda self: None)
    workspace = AssemblyWorkspace(settings)
    try:
        workspace.showEvent(QShowEvent())
        assert workspace.free_page is not None
        assert workspace.free_page.step == 0
        assert workspace.free_page.state["step"] == 0
        assert "camera" not in workspace.free_page.state
    finally:
        workspace.deleteLater()


def test_free_assembly_keeps_valid_saved_view_state(tmp_path, qt_app, monkeypatch):
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QShowEvent

    from little_tinker_rig.qt.assembly import AssemblyPage, AssemblyWorkspace

    (tmp_path / "robot.ldr").write_text("0 Robot\n", encoding="utf-8")
    path = tmp_path / "robot.json"
    path.write_text(json.dumps({"format": 1, "model": "robot.ldr"}), encoding="utf-8")
    state = {
        "step": 2,
        "camera": {"center": [0, 0, 0], "extent": 10, "yaw": 0, "pitch": 0},
    }
    settings = QSettings(str(tmp_path / "assembly.ini"), QSettings.Format.IniFormat)
    settings.setValue("assembly/path", str(path))
    settings.setValue("assembly/state", json.dumps(state))
    monkeypatch.setattr(AssemblyPage, "load", lambda self: None)
    workspace = AssemblyWorkspace(settings)
    try:
        workspace.showEvent(QShowEvent())
        assert workspace.free_page.step == 2
        assert workspace.free_page.state == state
    finally:
        workspace.deleteLater()


def test_assembly_link_works_without_task_card_and_selects_lesson_robot(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.assembly import AssemblyPage

    # Navigation does not depend on geometry loading or a graphics context.
    monkeypatch.setattr(AssemblyPage, "load", lambda self: None)
    root = make_lesson(tmp_path)
    (root / "goal.md").write_text(
        "# Build the robot\n\n"
        + "[Open 3D building instructions](assembly:)\n\n"
        + "Read the instructions and check each connection.\n\n" * 30
        + "| Port | Device |\n|---|---|\n| A | Motor |\n"
    )
    (root / "other.md").write_text("# Another task\n", encoding="utf-8")
    (root / "robot.ldr").write_text("0 Original model\n")
    (root / "robot.json").write_text(
        json.dumps(
            {"format": 1, "model": "robot.ldr", "steps": {"1": {}, "2": {}, "3": {}}}
        )
    )
    data = json.loads((root / "lesson.json").read_text())
    data["robot"] = "robot.json"
    data["stages"][0].update(mode="assembly", assembly=[2, 3])
    data["stages"][1]["description"] = "other.md"
    (root / "lesson.json").write_text(json.dumps(data))
    window = Studio(tmp_path / "plain.py")
    window.show()
    try:
        page = window.lessons.open(root)
        lesson = window.lessons
        page.session.editor.commit("unfinished_work = 42\n")
        lesson.guidance.trigger()
        qt_app.processEvents()
        assert not lesson.panel.isVisible()
        assert lesson.progress_button.isVisible()
        lesson.show_stage()
        browser = window.help_page.browser
        assert window.pages.currentIndex() == 2
        assert 'href="assembly:"' in browser.toHtml()
        assert browser.verticalScrollBar().maximum() > 0
        assert browser.verticalScrollBar().value() > 0
        assert not lesson.assembly.attempted
        lesson.assembly_host.open(root / "robot.json")
        assert not lesson.assembly_host.showing_lesson
        cursor = browser.document().find("Open 3D building instructions")
        cursor.setPosition(cursor.selectionStart() + 5)
        position = browser.cursorRect(cursor).center()
        assert browser.viewport().rect().contains(position)
        QTest.mouseClick(browser.viewport(), Qt.MouseButton.LeftButton, pos=position)
        assert window.pages.currentIndex() == 4
        assert lesson.assembly_host.showing_lesson
        assert lesson.assembly.step == 1
        lesson.assembly.set_step(2)
        lesson.follow_link(QUrl("lesson:"))
        browser.anchorClicked.emit(QUrl("assembly:"))
        assert lesson.assembly.step == 2
        assert page.text == "unfinished_work = 42\n"
        assert lesson.current.stage["id"] == "drive"
        assert not lesson.current.progress["completed"]
        lesson.select_stage(1)
        lesson.show_stage()
        assert window.help_page.current == "lesson/instructions#task-stop"
        assert "Another task" in browser.toPlainText()
        assert 'href="assembly:"' in browser.toHtml()
        assert window.help_page.lesson_group.childCount() == 1
    finally:
        window.recovery.close()
        window.deleteLater()


def test_starter_preserves_draft_and_device_check_uses_stage_ports(tmp_path, qt_app):
    from little_tinker_rig.pybricks.devices import HubInfo
    from little_tinker_rig.qt.app import Studio

    root = make_lesson(tmp_path)
    (root / "starter.py").write_text("new_value = 2\n")
    (root / "robot.json").write_text(
        json.dumps(
            {
                "devices": [
                    {"instance": "left", "port": "A", "type": "motor"},
                    {"instance": "sensor", "port": "D", "type": "ultrasonic"},
                ]
            }
        )
    )
    window = Studio(tmp_path / "plain.py")
    try:
        page = window.lessons.open(root)
        project = page.lesson_project
        project.stage["starter"] = "starter.py"
        page.session.editor.commit("old_value = 1\n")
        page.change_mode(1)
        page.code.setPlainText("unfinished(\n")
        window.lessons.actions["starter"].trigger()
        starter = window.document_page
        assert starter is not page
        assert starter.lesson_project is project
        assert "new_value = 2" in starter.text
        assert starter.session.project.path.exists()
        count = window.documents.count()
        window.lessons.open_starter()
        assert window.document_page is starter
        assert window.documents.count() == count
        assert page.text == "unfinished(\n"
        assert (root / "starter.py").read_text() == "new_value = 2\n"
        project.lesson.data["robot"] = "robot.json"
        project.stage.update(check="devices", devices=["left"])
        window.lessons.update_check()
        assert not window.lessons.actions["complete"].isEnabled()
        assert window.lessons.actions["next"].isEnabled()
        window.lessons.complete()
        assert not project.progress["completed"]
        assert window.lessons.status.text()
        window.update_hub(
            HubInfo(connected=True, monitoring=True, ports={"A": {"type": "motor"}})
        )
        assert window.lessons.check_ready()
        window.lessons.complete()
        assert project.progress["completed"] == ["drive"]
        window.update_hub(HubInfo(connected=False, ports={"A": {"type": "motor"}}))
        assert not window.lessons.check_ready()
        project.path = tmp_path / "work.ltr"
        assert window.lessons.save(project)
        saved = StudentProject.open(project.path)
        try:
            assert saved.main.read_text() == "unfinished(\n"
            assert (
                saved.main.parent / starter.session.project.path.name
            ).read_text() == starter.text
        finally:
            saved.discard_working_copy()
    finally:
        window.recovery.close()
        window.deleteLater()


def test_project_reopens_program_tabs_and_recovers_unsaved_progress(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt.app import Studio

    old = Studio(tmp_path / "plain.py")
    restored = None
    try:
        page = old.lessons.open(make_lesson(tmp_path))
        project = page.lesson_project
        project.path = tmp_path / "lesson.ltr"
        page.session.editor.commit("saved = 1\n")
        old.lessons.new_program()
        second = old.document_page
        second.session.editor.commit("other = 2\n")
        old.lessons.save(project)
        old.lessons.select_stage(1)
        second.change_mode(1)
        second.code.setPlainText("unfinished(\n")
        old.recovery.flush()
        old.recovery.lock.unlock()
        old.recovery.lock = None
        old.recovery.closed = True
        monkeypatch.setattr(
            QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes
        )
        restored = Studio(tmp_path / "elsewhere.py")
        restored.recovery.offer()
        assert restored.document_page.text == "unfinished(\n"
        assert restored.lessons.current.progress["stage"] == "stop"
        assert restored.document_page.lesson_project.dirty
        restored.lessons.save(restored.lessons.current)
        other = StudentProject.open(project.path)
        assert other.progress["stage"] == "stop"
        assert (
            other.root / "programs" / second.session.project.path.name
        ).read_text() == "unfinished(\n"
    finally:
        old.recovery.close()
        old.deleteLater()
        if restored:
            restored.recovery.close()
            restored.deleteLater()


def test_close_keeps_working_files_when_recovery_update_fails(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt import recovery
    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    try:
        page = window.lessons.open(make_lesson(tmp_path))
        project = page.lesson_project
        page.session.editor.commit("unfinished_work = 42\n")
        assert window.recovery.flush()
        checkpoint = json.loads(window.recovery.path.read_text())
        saved = next(
            item for item in checkpoint["documents"] if item.get("lesson_project")
        )

        def fail_write(*args):
            raise OSError("Disk full")

        monkeypatch.setattr(recovery, "atomic_write", fail_write)
        monkeypatch.setattr(
            QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard
        )
        window.close_document(window.documents.indexOf(page))
        assert project.root.is_dir()
        assert StudentProject.restore(saved["lesson_project"]).main.exists()
        assert json.loads(window.recovery.path.read_text()) == checkpoint
        assert saved["source"] == "unfinished_work = 42\n"
    finally:
        window.recovery.close()
        window.deleteLater()


def test_named_program_links_preserve_drafts_and_stage_navigation(tmp_path, qt_app):
    from PySide6.QtCore import QUrl

    from little_tinker_rig.qt.app import Studio

    root = make_lesson(tmp_path)
    (root / "first.py").write_text("first = 1\n")
    (root / "second.py").write_text("second = 2\n")
    (root / "LICENSE.txt").write_text("Lesson license")
    data = json.loads((root / "lesson.json").read_text())
    data.update(programs={n: n for n in ("first.py", "second.py")}, main="first.py")
    data["stages"][0]["program"] = "first.py"
    data["stages"][1]["program"] = "second.py"
    (root / "lesson.json").write_text(json.dumps(data))
    window = Studio(tmp_path / "plain.py")
    try:
        first = window.lessons.open(root)
        lesson = window.lessons
        first.change_mode(1)
        first.code.setPlainText("if unfinished >\n")
        lesson.select_stage(1)
        assert window.document_page is first
        lesson.show_stage()
        window.help_page.follow_link(QUrl("program:second.py"))
        assert window.document_page is not first
        assert window.document_page.text == "second = 2\n"
        assert window.document_page.lesson_project is first.lesson_project
        lesson.select_stage(0)
        lesson.open_task_program()
        assert window.document_page is first
        assert first.text == "if unfinished >\n"
        assert not lesson.panel.isHidden() or not lesson.progress_button.isHidden()
        lesson.show_stage()
        window.help_page.follow_link(QUrl("LICENSE.txt"))
        assert "Lesson license" in window.help_page.browser.toPlainText()
        lesson.follow_link(QUrl("lesson:"))
        assert "Make the robot move." in window.help_page.browser.toPlainText()
    finally:
        window.recovery.close()
        window.deleteLater()
