import json

from pyblocks.core.lessons import StudentProject


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


def test_stage_palette_preserves_source_and_free_exploration(tmp_path, qt_app):
    from pyblocks.qt.app import Studio
    from pyblocks.qt.library import IDENTITY

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
        project.path = tmp_path / "work.pyblocks"
        assert window.lessons.save(project)
        opened = StudentProject.open(project.path)
        assert opened.main.read_text() == "if distance >\n"
        assert opened.progress["stage"] == "stop"
    finally:
        window.recovery.close()
        window.deleteLater()


def test_starter_is_undoable_and_device_check_uses_stage_ports(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QMessageBox

    from pyblocks.pybricks.devices import HubInfo
    from pyblocks.qt.app import Studio

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
        monkeypatch.setattr(
            QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes
        )
        window.lessons.apply_starter()
        assert "new_value = 2" in page.text
        page.session.editor.undo()
        assert page.text == "old_value = 1\n"
        project.lesson.data["robot"] = "robot.json"
        project.stage.update(check="devices", devices=["left"])
        window.update_hub(
            HubInfo(connected=True, monitoring=True, ports={"A": {"type": "motor"}})
        )
        assert window.lessons.check_ready()
        window.lessons.complete()
        assert project.progress["completed"] == ["drive"]
        window.update_hub(HubInfo(connected=False, ports={"A": {"type": "motor"}}))
        assert not window.lessons.check_ready()
    finally:
        window.recovery.close()
        window.deleteLater()


def test_project_reopens_program_tabs_and_recovers_unsaved_progress(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QMessageBox

    from pyblocks.qt.app import Studio

    old = Studio(tmp_path / "plain.py")
    restored = None
    try:
        page = old.lessons.open(make_lesson(tmp_path))
        project = page.lesson_project
        project.path = tmp_path / "lesson.pyblocks"
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

    from pyblocks.qt import recovery
    from pyblocks.qt.app import Studio

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
