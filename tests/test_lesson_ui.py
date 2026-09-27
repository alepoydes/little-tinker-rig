import json

import pytest

from little_tinker_rig.core.lessons import StudentProject


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
        assert "lesson.ltr" in prompts[0] and "all open programs" in prompts[0]
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


def test_stage_palette_preserves_source_and_free_exploration(tmp_path, qt_app):
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
        assert window.source.expression_ids == frozenset(["pybricks/drive/brake"])
        visible = {
            g.child(j).data(0, IDENTITY)
            for i in range(window.library.topLevelItemCount())
            for g in [window.library.topLevelItem(i)]
            for j in range(g.childCount())
            if not g.child(j).isHidden()
        }
        assert visible <= {"pybricks/drive/brake"}
        assert len(page.session.snippets) > 20
        window.lessons.set_explore(True)
        assert window.source.expression_ids is None
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


def test_lesson_navigation_is_explicit_and_restores_workspace(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "plain.py")
    window.show()
    try:
        page = window.lessons.open(make_lesson(tmp_path))
        lesson = window.lessons
        assert window.pages.currentIndex() == 4
        assert lesson.card.isVisible()
        assert not lesson.explore.isVisible()
        window.set_mode(2)
        assert lesson.card.isVisible()
        window.set_mode(4)
        assert not lesson.actions["previous"].isEnabled()
        assert lesson.actions["next"].isEnabled()
        lesson.actions["next"].trigger()
        assert lesson.current.stage["id"] == "stop"
        assert not lesson.current.progress["completed"]
        assert not lesson.actions["next"].isEnabled()
        lesson.actions["previous"].trigger()
        assert lesson.current.stage["id"] == "drive"
        assert not lesson.actions["hint"].isVisible()
        assert not lesson.actions["starter"].isVisible()
        lesson.actions["start"].trigger()
        assert window.pages.currentIndex() == 0
        assert lesson.card.isVisible()
        assert lesson.explore.isVisible()
        assert not lesson.actions["start"].isVisible()
        page.session.editor.commit("drive.straight(200)\n")
        lesson.actions["complete"].trigger()
        assert not lesson.stages.item(0).icon().isNull()
        assert lesson.stages.item(1).icon().isNull()
        assert window.pages.currentIndex() == 0
        assert lesson.actions["next"].isEnabled()
        lesson.actions["next"].trigger()
        assert window.pages.currentIndex() == 4
        assert lesson.current.stage["id"] == "stop"
        assert page.text == "drive.straight(200)\n"
        lesson.actions["start"].trigger()
        lesson.guidance.trigger()
        assert not lesson.card.isVisible()
        window.set_mode(1)
        project = lesson.current
        project.path = tmp_path / "work.ltr"
        lesson.save(project)
        window.open_document(tmp_path / "plain.py")
        assert not lesson.card.isVisible()
        lesson.open(project.path)
        assert window.pages.currentIndex() == 1
        assert not lesson.guidance.isChecked()
        lesson.guidance.trigger()
        assert lesson.card.isVisible()
        window.confirm_close = lambda *_: True
        window.close_document(window.documents.currentIndex())
        page = lesson.open(project.path)
        assert window.pages.currentIndex() == 1
        assert page.text == "drive.straight(200)\n"
        assert not lesson.guidance.isChecked()
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
        assert not window.modes.item(5).isHidden()
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
        + "Read the instructions and check each connection.\n\n" * 30
        + "| Port | Device |\n|---|---|\n| A | Motor |\n"
    )
    (root / "robot.ldr").write_text("0 Original model\n")
    (root / "robot.json").write_text(
        json.dumps(
            {"format": 1, "model": "robot.ldr", "steps": {"1": {}, "2": {}, "3": {}}}
        )
    )
    data = json.loads((root / "lesson.json").read_text())
    data["robot"] = "robot.json"
    data["stages"][0].update(mode="assembly", assembly=[2, 3])
    (root / "lesson.json").write_text(json.dumps(data))
    window = Studio(tmp_path / "plain.py")
    window.show()
    try:
        page = window.lessons.open(root)
        lesson = window.lessons
        page.session.editor.commit("unfinished_work = 42\n")
        lesson.guidance.trigger()
        qt_app.processEvents()
        assert lesson.card.isHidden()
        assert 'href="assembly:"' in lesson.description.toHtml()
        assert lesson.description.verticalScrollBar().maximum() > 0
        assert lesson.description.verticalScrollBar().value() == 0
        assert not lesson.assembly.attempted
        lesson.assembly_host.open(root / "robot.json")
        assert not lesson.assembly_host.showing_lesson
        cursor = lesson.description.document().find("Open 3D building instructions")
        cursor.setPosition(cursor.selectionStart() + 5)
        position = lesson.description.cursorRect(cursor).center()
        assert lesson.description.viewport().rect().contains(position)
        QTest.mouseClick(
            lesson.description.viewport(), Qt.MouseButton.LeftButton, pos=position
        )
        assert window.pages.currentIndex() == 5
        assert lesson.assembly_host.showing_lesson
        assert lesson.assembly.step == 1
        lesson.assembly.set_step(2)
        lesson.follow_link(QUrl("lesson:"))
        lesson.description.anchorClicked.emit(QUrl("assembly:"))
        assert lesson.assembly.step == 2
        assert page.text == "unfinished_work = 42\n"
        assert lesson.current.stage["id"] == "drive"
        assert not lesson.current.progress["completed"]
        lesson.select_stage(1)
        assert 'href="assembly:"' not in lesson.description.toHtml()
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
        assert not starter.session.project.path.exists()
        assert page.text == "unfinished(\n"
        assert (root / "starter.py").read_text() == "new_value = 2\n"
        window.lessons.open_starter()
        assert window.document_page is not starter
        assert window.document_page.session.project.path != starter.session.project.path
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
        lesson.follow_link(QUrl("program:second.py"))
        assert window.document_page is not first
        assert window.document_page.text == "second = 2\n"
        assert window.document_page.lesson_project is first.lesson_project
        lesson.select_stage(0)
        assert lesson.actions["start"].isVisible()
        lesson.start_stage()
        assert window.document_page is first
        assert first.text == "if unfinished >\n"
        assert not lesson.actions["start"].isVisible()
        lesson.follow_link(QUrl("LICENSE.txt"))
        assert "Lesson license" in lesson.description.toPlainText()
        lesson.follow_link(QUrl("lesson:"))
        assert "Make the robot move." in lesson.description.toPlainText()
    finally:
        window.recovery.close()
        window.deleteLater()
