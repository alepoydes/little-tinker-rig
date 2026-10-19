import json
from unittest.mock import patch

import pytest

from little_tinker_rig.core.project import Project
from little_tinker_rig.core.runtime_errors import Tracebacks
from little_tinker_rig.pybricks.program import Program


def close(window):
    from PySide6.QtWidgets import QMessageBox

    with patch.object(
        QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard
    ):
        window.close()


def test_unfinished_source_saves_with_scratch_and_keeps_external_conflicts(tmp_path):
    path = tmp_path / "draft.py"
    project = Project(path)
    project.document.commit("value = 1\n", ("unfinished(",))
    project.draft = "if value:\n"
    project.save()
    reopened = Project(path, allow_draft=True)
    assert reopened.draft == "if value:\n"
    assert reopened.state.scratch == ("unfinished(",)
    assert not reopened.dirty
    path.write_text("external = 2\n")
    with pytest.raises(ValueError, match="outside"):
        reopened.save()
    assert path.read_text() == "external = 2\n"


def test_save_does_not_require_structural_preparation(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    path = tmp_path / "work.py"
    window = Studio(path)
    try:
        window.change_editor(1)
        source = "# --- automatically managed helpers ---\nvalue = 42\n"
        window.code.setPlainText(source)
        window.save()
        assert path.read_text() == source
        assert not window.document_page.dirty
        with pytest.raises(ValueError):
            window.commit_code()
    finally:
        close(window)


def test_saved_draft_can_close_reopen_and_save_as_without_becoming_runnable(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from little_tinker_rig.qt.app import Studio

    path, destination = tmp_path / "main.py", tmp_path / "copy.py"
    path.write_text("print(1)\n")
    window = Studio(path)
    try:
        window.change_editor(1)
        window.code.setPlainText("if True:\n")
        window.save()
        assert not window.document_page.dirty
        assert path.read_text() == window.code.toPlainText()
        with pytest.raises(SyntaxError):
            window.run_hub()
        assert window.robot is None
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            lambda *args: (str(destination), "Python (*.py)"),
        )
        window.save_as()
        assert destination.read_text() == "if True:\n"
        window.code.setPlainText("if False:\n")
        monkeypatch.setattr(
            QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Save
        )
        window.close_document(0)
        assert destination.read_text() == "if False:\n"
        page = window.open_document(destination)
        assert page.code_active and not page.dirty
        assert page.text == "if False:\n"
    finally:
        close(window)


def test_recovery_restores_tabs_scratch_drafts_and_original_disk_baseline(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt.app import Studio

    first, second = tmp_path / "main.py", tmp_path / "new.py"
    first.write_text("value = 1\n")
    old = Studio(first)
    restored = None
    try:
        qt_app.processEvents()
        old.session.editor.commit("value = 2\n", ("pending(",))
        old.change_editor(1)
        old.code.setPlainText("value = 2\nif value:")
        old.open_document(second)
        old.session.editor.commit('print("unsaved")\n')
        old.recovery.flush()
        recovery_path = old.recovery.path
        assert json.loads(recovery_path.read_text())["active"] == 1
        assert not second.exists()
        restored = Studio(first)
        with patch.object(QMessageBox, "question") as prompt:
            restored.recovery.offer()
            prompt.assert_not_called()  # Another live window owns the lock.
        old.recovery.timer.stop()
        old.recovery.lock.unlock()  # The operating system releases this on a crash.
        first.write_text("external = 9\n")
        monkeypatch.setattr(
            QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes
        )
        with patch.object(restored.recovery, "flush", return_value=False):
            restored.recovery.offer()
        assert recovery_path.exists()  # Keep the old copy until the new one is durable.
        restored.recovery.offer()
        assert not recovery_path.exists()
        assert restored.documents.count() == 2
        assert restored.session.project.path == second
        assert restored.document_page.text == 'print("unsaved")\n'
        page = restored.documents.widget(0)
        assert page.code_active and page.dirty
        assert page.text == "value = 2\nif value:"
        assert page.session.document.state.scratch == ("pending(",)
        restored.documents.setCurrentWidget(page)
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        QTimer.singleShot(0, lambda: QApplication.activeModalWidget().reject())
        assert not restored.save()
        assert first.read_text() == "external = 9\n"
        restored.documents.setCurrentIndex(1)
        restored.save()
        assert second.read_text() == 'print("unsaved")\n'
    finally:
        close(old)
        if restored:
            recovery_path = restored.recovery.path
            close(restored)
            assert not recovery_path.exists()


@pytest.mark.parametrize("damage", ["workspace", "source"])
def test_recovery_keeps_draft_when_disk_project_is_unreadable(
    tmp_path, qt_app, monkeypatch, damage
):
    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt.app import Studio

    path = tmp_path / "main.py"
    path.write_text("value = 1\n", encoding="utf-8")
    old = Studio(path)
    restored = None
    try:
        old.session.editor.commit("value = 1\n", ("saved fragment",))
        old.save()
        old.session.editor.commit("value = 2\n", ("unsaved fragment",))
        assert old.recovery.flush()
        recovery_path = old.recovery.path
        old.recovery.timer.stop()
        old.recovery.lock.unlock()  # Simulate the operating system releasing a crash lock.
        workspace = old.session.project.workspace_path
        if damage == "workspace":
            workspace.write_text("{broken", encoding="utf-8")
            orphan = path.with_name("main_recovered_1.py.ltr.json")
            orphan.write_text("{orphan", encoding="utf-8")
        else:
            path.write_bytes(b"\xff")
        original_source = path.read_bytes()
        original_workspace = workspace.read_bytes()

        restored = Studio()
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args: QMessageBox.StandardButton.Yes,
        )
        restored.recovery.offer()

        assert not recovery_path.exists()
        assert restored.document_page.session.project.path != path
        if damage == "workspace":
            assert restored.document_page.session.project.path.name == "main_recovered_2.py"
        assert restored.document_page.text == "value = 2\n"
        assert restored.session.document.state.scratch == ("unsaved fragment",)
        restored.save()
        assert path.read_bytes() == original_source
        assert workspace.read_bytes() == original_workspace
    finally:
        close(old)
        if restored:
            close(restored)


def test_recovery_refreshes_mutated_pins_and_recreates_missing_checkpoint(
    tmp_path, qt_app
):
    from little_tinker_rig.qt.app import Studio

    path = tmp_path / "work.py"
    path.write_text("print(1)\n", encoding="utf-8")
    window = Studio(path)
    try:
        project = window.session.project
        project.pins = {"course": "1.0"}
        assert window.recovery.flush()
        checkpoint = window.recovery.path
        assert json.loads(checkpoint.read_text(encoding="utf-8"))["documents"][0][
            "pins"
        ] == {"course": "1.0"}

        project.pins["course"] = "1.1"
        assert window.recovery.flush()
        assert json.loads(checkpoint.read_text(encoding="utf-8"))["documents"][0][
            "pins"
        ] == {"course": "1.1"}

        checkpoint.unlink()
        assert window.recovery.flush()
        assert checkpoint.exists()
    finally:
        close(window)


def test_cancel_recovery_keeps_all_pending_checkpoints(qt_app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt.app import Studio

    window = Studio()
    try:
        qt_app.processEvents()
        window.recovery.path.parent.mkdir(parents=True, exist_ok=True)
        pending = [
            window.recovery.path.with_name(f"abandoned_{index}.json")
            for index in range(2)
        ]
        for path in pending:
            path.write_text(
                json.dumps(
                    {
                        "format": 1,
                        "active": 0,
                        "documents": [window.document_page.checkpoint()],
                    }
                ),
                encoding="utf-8",
            )
        prompts = []

        def cancel(*args):
            prompts.append(args)
            return QMessageBox.StandardButton.Cancel

        monkeypatch.setattr(QMessageBox, "question", cancel)
        window.recovery.offer()
        assert len(prompts) == 1
        assert all(path.exists() for path in pending)
    finally:
        close(window)


def test_invalid_recovery_active_tab_is_rejected_before_opening(qt_app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt.app import Studio

    window = Studio()
    try:
        qt_app.processEvents()
        window.recovery.path.parent.mkdir(parents=True, exist_ok=True)
        abandoned = window.recovery.path.with_name("abandoned.json")
        abandoned.write_text(
            json.dumps(
                {
                    "format": 1,
                    "active": -9,
                    "documents": [window.document_page.checkpoint()],
                }
            ),
            encoding="utf-8",
        )
        prompts = []
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args: prompts.append(args) or QMessageBox.StandardButton.Yes,
        )
        window.recovery.offer()
        assert not prompts
        assert window.documents.count() == 1
        assert abandoned.exists()
        assert "Could not restore recovery data" in window.last_error
    finally:
        close(window)


@pytest.mark.parametrize("corruption", ["cursor", "committed", "lesson"])
def test_invalid_later_recovery_document_does_not_partly_restore(
    tmp_path, qt_app, monkeypatch, corruption
):
    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt.app import Studio

    first = tmp_path / "first.py"
    first.write_text("value = 1\n", encoding="utf-8")
    window = Studio(first)
    try:
        qt_app.processEvents()
        first_item = window.document_page.checkpoint()
        first_item.update(source="value = 2\n", committed="value = 2\n")
        invalid_item = dict(
            first_item,
            path=str(tmp_path / "second.py"),
            source="other = 3\n",
            committed="other = 3\n",
        )
        if corruption == "cursor":
            invalid_item["cursor"] = "invalid"
        elif corruption == "committed":
            invalid_item["committed"] = "if True:\n"
        else:
            invalid_item["lesson_project"] = {"root": str(tmp_path / "missing")}
        window.recovery.path.parent.mkdir(parents=True, exist_ok=True)
        abandoned = window.recovery.path.with_name("abandoned.json")
        abandoned.write_text(
            json.dumps(
                {"format": 1, "active": 0, "documents": [first_item, invalid_item]}
            ),
            encoding="utf-8",
        )
        prompts = []
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args: prompts.append(args) or QMessageBox.StandardButton.Yes,
        )
        window.recovery.offer()
        assert not prompts
        assert window.documents.count() == 1
        assert window.document_page.text == "value = 1\n"
        assert abandoned.exists()
    finally:
        close(window)


def test_examples_follow_directory_changes_and_reuse_existing_tabs(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QMenu, QMenuBar

    from little_tinker_rig.qt.app import Studio

    root = tmp_path / "examples"
    nested = root / "robot"
    nested.mkdir(parents=True)
    (root / "notes.md").write_text("Not a program")
    (root / ".hidden.py").write_text("")
    one, two = root / "one.py", nested / "51515_two.py"
    one.write_text("print(1)\n")
    two.write_text("print(2)\n")
    monkeypatch.setattr("little_tinker_rig.qt.app.examples_directory", lambda: root)
    window = Studio(tmp_path / "work.py")
    try:
        bar = window.menuWidget().findChild(QMenuBar)
        file_menu = next(a.menu() for a in bar.actions() if a.text() == "File")
        assert window.examples_menu.menuAction() in file_menu.actions()
        assert window.examples_menu.menuAction() not in bar.actions()
        window.refresh_examples()
        actions = [
            a for a in window.examples_menu.actions() if a.data() or a.text() == "robot"
        ]
        assert [a.text() for a in actions] == ["robot", "one.py"]
        action = actions[0].menu().actions()[0]
        assert action.text() == two.name
        action.trigger()
        page = window.document_page
        page.change_mode(1)
        page.code.setPlainText("unfinished(")
        action.trigger()
        assert window.documents.count() == 2 and window.document_page is page
        assert page.text == "unfinished("
        two.unlink()
        three = nested / "three.py"
        three.write_text("print(3)\n")
        window.refresh_examples()
        assert [
            a.text() for a in window.examples_menu.actions()[0].menu().actions()
        ] == ["three.py"]
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not any(
            m.title() == "51515_two.py"
            for m in window.examples_menu.findChildren(QMenu)
        )
    finally:
        close(window)


def test_recovering_another_version_never_replaces_unsaved_tab(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt.app import Studio

    path = tmp_path / "work.py"
    path.write_text("value = 1\n")
    window = Studio(path)
    try:
        qt_app.processEvents()
        checkpoint = window.document_page.checkpoint()
        checkpoint.update(source="value = 3\n", committed="value = 3\n")
        window.session.editor.commit("value = 2\n")
        window.recovery.flush()
        abandoned = window.recovery.path.with_name("abandoned.json")
        abandoned.write_text(
            json.dumps({"format": 1, "active": 0, "documents": [checkpoint]})
        )
        monkeypatch.setattr(
            QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes
        )
        window.recovery.offer()
        assert not abandoned.exists()
        assert window.documents.count() == 2
        assert window.documents.widget(0).text == "value = 2\n"
        assert window.document_page.text == "value = 3\n"
        assert window.session.project.path != path
        window.save()
        assert path.read_text() == "value = 1\n"
        assert window.session.project.path.read_text() == "value = 3\n"
    finally:
        close(window)


def test_execution_snapshot_captures_imports_and_rejects_unrelated_trace_paths(
    tmp_path,
):
    path = tmp_path / "main.py"
    package = tmp_path / "parts"
    package.mkdir()
    (package / "__init__.py").write_text("from .arm import move\n")
    arm = package / "arm.py"
    arm.write_text("def move():\n    return 1 / 0\n")
    path.write_text("from parts import move\nmove()\n")
    program = Program(path)
    arm.write_text("def move():\n    return 42\n")
    assert "1 / 0" in (program.entry.parent / "parts/arm.py").read_text()
    assert program.original_path("parts/arm.py") == arm
    assert program.original_path(str(program.entry.parent / "parts/arm.py")) == arm
    assert program.original_path("/unrelated/main.py") is None
    received = []
    parser = Tracebacks(program, received.append)
    trace = 'output\nTraceback (most recent call last):\n  File "main.py", line 2, in <module>\n  File "parts/arm.py", line 2, in move\nZeroDivisionError: division by zero\n'
    for character in trace:
        parser.feed(character)
    (problem,) = received
    assert (problem.path, problem.line, problem.kind) == (arm, 2, "ZeroDivisionError")
    assert "1 / 0" in problem.source


@pytest.mark.parametrize(
    "trace",
    [
        'Uploading 95%\rTraceback (most recent call last):\r  File "main.py", line 1, in <module>\rZeroDivisionError: division by zero\r',
        '\x1b[31mTraceback (most recent call last):\x1b[0m\n  File "main.py", line 1, in <module>\n\x1b[31mZeroDivisionError: division by zero\x1b[0m\n',
    ],
)
def test_traceback_parser_handles_carriage_returns_and_ansi(tmp_path, trace):
    path = tmp_path / "main.py"
    path.write_text("result = 1 / 0\n", encoding="utf-8")
    program = Program(path)
    try:
        received = []
        parser = Tracebacks(program, received.append)
        for character in trace:
            parser.feed(character)
        assert [(problem.path, problem.line, problem.kind) for problem in received] == [
            (path, 1, "ZeroDivisionError")
        ]
    finally:
        program.cleanup()


def test_managed_helper_errors_locate_call_and_stops_are_not_errors(tmp_path):
    path = tmp_path / "main.py"
    path.write_text(
        "# --- automatically managed helpers ---\ndef action():\n    return 1 / 0\n# --- user program ---\naction()\n"
    )
    program = Program(path)
    received = []
    parser = Tracebacks(program, received.append)
    header = 'Traceback (most recent call last):\n  File "main.py", line 5, in <module>\n  File "main.py", line 3, in action\n'
    parser.feed(header + "ZeroDivisionError: division by zero\n")
    assert received[0].line == 5
    parser.feed(header + "KeyboardInterrupt:\n")
    assert len(received) == 1
    parser.feed(header + "RobotError: details stay intact\n")
    assert received[1].explanation == "RobotError: details stay intact"
    unknown = []
    Tracebacks(None, unknown.append).feed(header + "NameError: missing\n")
    assert unknown[0].path is None and unknown[0].source == ""
    assert "spelling" in unknown[0].explanation


def test_runtime_error_marks_block_but_changed_source_opens_executed_snapshot(
    tmp_path, qt_app
):
    from PySide6.QtWidgets import QDialog

    from little_tinker_rig.core.runtime_errors import RuntimeProblem
    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.code import CodeEdit

    path = tmp_path / "main.py"
    path.write_text("result = 1 / 0\n")
    window = Studio(path)
    dialogs = []
    try:
        program = Program(path)
        problem = RuntimeProblem(
            program, path, 1, "ZeroDivisionError", "division by zero"
        )
        window.runtime_panel.receive(problem)
        assert any(
            note.error and "zero" in note.description
            for notes in window.source.notes.values()
            for note in notes
        )
        from little_tinker_rig.i18n import set_language

        set_language("ru")
        window.retranslate()
        assert window.examples_menu.title() == "Примеры"
        assert window.runtime_panel.locate.text() == "Показать блок"
        assert "ноль" in window.runtime_panel.message.text()
        window.runtime_panel.show_block()
        assert (
            window.session.editor.selection is not window.session.document.syntax.tree
        )
        window.session.editor.commit("print(42)\n")
        window.refresh_views()
        assert not any(
            note.error for notes in window.source.notes.values() for note in notes
        )
        window.runtime_panel.show_block()
        dialogs = window.findChildren(QDialog)
        editor = next(d.findChild(CodeEdit) for d in dialogs if d.findChild(CodeEdit))
        assert editor.isReadOnly() and editor.toPlainText() == program.sources[path]
        assert window.document_page.text == "print(42)\n"
    finally:
        for dialog in dialogs:
            dialog.close()
        close(window)


@pytest.mark.parametrize(
    "replacement",
    [
        b"# coding: unknown-codec\nresult = 2\n",
        b"# coding: utf-8\nresult = \xff\n",
    ],
)
def test_runtime_location_uses_snapshot_if_module_encoding_changed(
    tmp_path, qt_app, replacement
):
    from PySide6.QtWidgets import QDialog

    from little_tinker_rig.core.runtime_errors import RuntimeProblem
    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.code import CodeEdit

    path = tmp_path / "main.py"
    module = tmp_path / "helper.py"
    path.write_text("import helper\n", encoding="utf-8")
    module.write_text("result = 1 / 0\n", encoding="utf-8")
    window = Studio(path)
    program = Program(path)
    dialogs = []
    try:
        module.write_bytes(replacement)
        problem = RuntimeProblem(program, module, 1, "ZeroDivisionError", "")
        window.runtime_panel.receive(problem)
        window.runtime_panel.show_block()
        dialogs = [
            dialog
            for dialog in window.findChildren(QDialog)
            if dialog.findChild(CodeEdit)
        ]
        assert len(dialogs) == 1
        editor = dialogs[0].findChild(CodeEdit)
        assert editor.isReadOnly()
        assert editor.toPlainText() == program.sources[module]
        assert window.documents.count() == 1
    finally:
        for dialog in dialogs:
            dialog.close()
        program.cleanup()
        close(window)


def test_virtual_runtime_and_run_stored_keep_the_uploaded_source(tmp_path, qt_app):
    from time import monotonic

    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    def wait_until(predicate):
        deadline = monotonic() + 10
        while not predicate():
            assert monotonic() < deadline, "Virtual run did not finish"
            QTest.qWait(20)

    path = tmp_path / "main.py"
    path.write_text("result = 1 / 0\n")
    window = Studio(path)
    try:
        robot = window._robot()
        robot.connect_hub(transport="virtual")
        wait_until(lambda: window.hub_info.connected and not window.hub_is_busy)
        window.run_hub()
        wait_until(
            lambda: window.runtime_panel.problem is not None and not window.hub_is_busy
        )
        first = window.runtime_panel.problem
        assert (first.path, first.line, first.kind) == (path, 1, "ZeroDivisionError")
        assert "Traceback" in window.console.toPlainText()
        window.session.editor.commit("print(42)\n")
        window.save()
        window.run_stored_hub()
        wait_until(
            lambda: window.runtime_panel.problem is not None
            and window.runtime_panel.problem is not first
            and not window.hub_is_busy
        )
        assert window.runtime_panel.problem.source == "result = 1 / 0\n"
        assert window.document_page.text == path.read_text() == "print(42)\n"
        assert not any(
            note.error for notes in window.source.notes.values() for note in notes
        )
    finally:
        close(window)
