import ast

import pytest

from little_tinker_rig.core.example_work import ExampleWork
from little_tinker_rig.pybricks.program import Program


def test_snapshots_use_unsaved_modules_and_keep_original_paths(tmp_path):
    entry, helper = tmp_path / "main.py", tmp_path / "helper.py"
    helper.write_text("value = 1\n")
    sources = {
        entry: "from helper import value\nprint(value)\n",
        helper: '# coding: latin-1\nvalue = "Привет"\n',
        tmp_path / "unrelated.py": "unfinished(",
    }
    program = Program(entry, sources)
    sources[helper] = "value = 99\n"
    assert not entry.exists() and helper.read_text() == "value = 1\n"
    assert 'value = "Привет"' in (program.entry.parent / helper.name).read_text()
    assert "coding: utf-8" in program.sources[helper]
    assert program.original_path(helper.name) == helper
    assert len(program.sources) == 2
    with pytest.raises(SyntaxError):
        Program(entry, {**sources, helper: "unfinished("})
    program.cleanup()


def test_example_resume_restart_autosave_and_save_as_with_modules(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from little_tinker_rig.qt.app import Studio

    root = tmp_path / "bundled"
    root.mkdir()
    entry, helper = root / "main.py", root / "helper.py"
    entry.write_text("from helper import value\nprint(value)\n")
    helper.write_text("value = 1\n")
    original = {p: p.read_bytes() for p in (entry, helper)}
    monkeypatch.setattr("little_tinker_rig.qt.app.examples_directory", lambda: root)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard
    )
    window = Studio(entry)
    windows = [window]
    try:
        page = window.document_page
        work = page.example_work
        assert page.session.project.path != entry and work is not None
        helper_page = window.open_document(work.root / "helper.py")
        helper_page.change_mode(1)
        helper_page.code.setPlainText("value = 7\n")
        window.open_document(entry)
        assert window.document_page is page and len(ExampleWork.all()) == 1
        page.change_mode(1)
        page.code.setPlainText("from helper import value\nprint(value)\nif value:\n")
        page.session.set_scratch(None, "unfinished(")
        assert window.recovery.flush()
        assert not page.dirty
        window.close()

        window = Studio(entry)
        windows.append(window)
        page = window.document_page
        assert page.code_active and page.text.endswith("if value:\n")
        assert page.session.document.state.scratch == ("unfinished(",)
        assert (work.root / "helper.py").read_text() == "value = 7\n"
        assert page.example_work.identity == work.identity
        helper_page = window.open_document(work.root / "helper.py")
        helper_page.change_mode(1)
        helper_page.code.setPlainText("value = 8\n")
        helper_page.session.set_scratch(None, "alternative(")
        window.open_document(entry)
        destination = tmp_path / "saved" / "renamed.py"
        destination.parent.mkdir()
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *a: (str(destination), "")
        )
        assert window.save_as()
        assert destination.read_text() == page.text
        assert (destination.parent / "helper.py").read_text() == "value = 8\n"
        assert helper_page.session.project.path == destination.parent / "helper.py"
        assert helper_page.session.document.state.scratch == ("alternative(",)
        assert page.example_work.entry == destination
        window.open_document(entry)
        assert window.document_page is page
        window.close()

        window = Studio(entry)
        windows.append(window)
        old_page = window.document_page
        assert old_page.session.project.path == destination
        old_page.code.setPlainText("print(42)\n")
        window.refresh_examples()
        next(
            a
            for a in window.examples_menu.actions()
            if a.text() == "Start this example again"
        ).trigger()
        fresh = window.document_page
        assert fresh is not old_page and fresh.example_work.identity != work.identity
        assert ast.dump(ast.parse(fresh.text)) == ast.dump(ast.parse(entry.read_text()))
        assert old_page.text == "print(42)\n"
        assert len(ExampleWork.all()) == 2
        with pytest.raises(ValueError, match="another example attempt"):
            window.save_as()
        assert old_page.text == "print(42)\n"
        window.open_document(entry)
        assert window.document_page is fresh
        window.refresh_examples()
        attempts = next(
            a.menu()
            for a in window.examples_menu.actions()
            if a.text() == "My attempts"
        )
        group = attempts.actions()[0].menu()
        next(a for a in group.actions() if a.data() == str(work.root)).trigger()
        assert window.document_page is old_page
        window.open_document(entry)
        assert window.document_page is old_page  # Continue the last chosen attempt.
        window.new_file()
        assert window.document_page.example_work is None
        assert window.document_page.unnamed
        assert all(p.read_bytes() == content for p, content in original.items())
    finally:
        for window in windows:
            window.close()


def test_example_autosave_preserves_external_edits_and_save_as_module_conflicts(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QFileDialog

    from little_tinker_rig.qt.app import Studio

    root = tmp_path / "bundled"
    root.mkdir()
    (root / "main.py").write_text("import helper\nprint(helper.value)\n")
    (root / "helper.py").write_text("value = 1\n")
    monkeypatch.setattr("little_tinker_rig.qt.app.examples_directory", lambda: root)
    window = Studio(root / "main.py")
    try:
        page = window.document_page
        copied = page.session.project.path
        window.session.editor.commit("print(2)\n")
        copied.write_text("external = 3\n")
        assert not window.recovery.flush()
        assert "print(2)" in window.recovery.path.read_text()
        assert copied.read_text() == "external = 3\n"
        assert page.text == "print(2)\n"
        destination = tmp_path / "export" / "renamed.py"
        destination.parent.mkdir()
        collision = destination.parent / "helper.py"
        collision.write_text("value = 99\n")
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *a: (str(destination), "")
        )
        with pytest.raises(ValueError, match="different module"):
            window.save_as()
        assert not destination.exists() and collision.read_text() == "value = 99\n"
        assert page.session.project.path == copied
    finally:
        window.confirm_close = lambda *_: True
        window.close()
