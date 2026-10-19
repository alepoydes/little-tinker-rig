import ast
import json
from pathlib import Path

import pytest

from little_tinker_rig.core.example_work import ExampleWork, attempts_directory
from little_tinker_rig.core.project import ExternalChangeError
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


def test_snapshot_prefers_package_over_unreachable_same_named_module(tmp_path):
    entry = tmp_path / "main.py"
    entry.write_text("from helper import value\nprint(value)\n", encoding="utf-8")
    unused = tmp_path / "helper.py"
    unused.write_text("unfinished(\n", encoding="utf-8")
    package = tmp_path / "helper"
    package.mkdir()
    initializer = package / "__init__.py"
    initializer.write_text("value = 42\n", encoding="utf-8")

    program = Program(entry)
    try:
        assert set(program.sources) == {entry, initializer}
        assert (
            program.entry.parent / "helper/__init__.py"
        ).read_text() == "value = 42\n"
        assert not (program.entry.parent / "helper.py").exists()
    finally:
        program.cleanup()


def test_snapshot_does_not_descend_into_a_plain_module(tmp_path):
    entry = tmp_path / "main.py"
    entry.write_text("from helper import value\nprint(value)\n", encoding="utf-8")
    helper = tmp_path / "helper.py"
    helper.write_text("value = 42\n", encoding="utf-8")
    misleading = tmp_path / "helper"
    misleading.mkdir()
    (misleading / "value.py").write_text("unfinished(\n", encoding="utf-8")

    program = Program(entry)
    try:
        assert set(program.sources) == {entry, helper}
        assert not (program.entry.parent / "helper/value.py").exists()
    finally:
        program.cleanup()


def test_snapshot_includes_regular_and_relative_package_imports(tmp_path):
    entry = tmp_path / "main.py"
    entry.write_text("from package.runner import value\n", encoding="utf-8")
    package = tmp_path / "package"
    package.mkdir()
    initializer = package / "__init__.py"
    initializer.write_text("", encoding="utf-8")
    runner = package / "runner.py"
    runner.write_text("from . import helper\nvalue = helper.value\n", encoding="utf-8")
    helper = package / "helper.py"
    helper.write_text("value = 42\n", encoding="utf-8")

    program = Program(entry)
    try:
        assert set(program.sources) == {entry, initializer, runner, helper}
    finally:
        program.cleanup()


def test_snapshot_follows_unsaved_module_in_a_new_namespace(tmp_path):
    entry = tmp_path / "main.py"
    module = tmp_path / "virtual" / "sub.py"
    program = Program(
        entry,
        {
            entry: "from virtual.sub import value\nprint(value)\n",
            module: "value = 42\n",
        },
    )
    try:
        assert set(program.sources) == {entry, module}
        assert (program.entry.parent / "virtual/sub.py").read_text() == "value = 42\n"
    finally:
        program.cleanup()


def test_snapshot_does_not_execute_entry_directory_initializer(tmp_path):
    entry = tmp_path / "main.py"
    entry.write_text("from helper import value\n", encoding="utf-8")
    helper = tmp_path / "helper.py"
    helper.write_text("value = 42\n", encoding="utf-8")
    (tmp_path / "__init__.py").write_text("unfinished(\n", encoding="utf-8")

    program = Program(entry)
    try:
        assert set(program.sources) == {entry, helper}
    finally:
        program.cleanup()


def test_disk_sources_are_utf8_in_snapshot_without_rewriting_originals(tmp_path):
    entry, helper = tmp_path / "main.py", tmp_path / "helper.py"
    main_bytes = (
        '# coding: latin-1\nfrom helper import word\nprint("café", word)\n'
    ).encode("latin-1")
    helper_bytes = '# coding: cp1251\nword = "Привет"\n'.encode("cp1251")
    entry.write_bytes(main_bytes)
    helper.write_bytes(helper_bytes)

    program = Program(entry)
    try:
        assert set(program.sources) == {entry, helper}
        for file, original in ((entry, main_bytes), (helper, helper_bytes)):
            snapshot = program.entry.parent / file.name
            assert snapshot.read_bytes().decode("utf-8") == program.sources[file]
            assert "coding: utf-8" in program.sources[file]
            assert file.read_bytes() == original
    finally:
        program.cleanup()


def test_failed_attempt_relocation_keeps_in_memory_file_ownership(tmp_path):
    examples = tmp_path / "bundled"
    examples.mkdir()
    source = examples / "main.py"
    source.write_text("print(1)\n", encoding="utf-8")
    work = ExampleWork.create(source, examples)
    original = json.loads(json.dumps(work.data))
    external = dict(original, opened=original["opened"] + 1)
    work.manifest.write_text(json.dumps(external), encoding="utf-8")

    with pytest.raises(ExternalChangeError):
        work.relocated({work.entry: tmp_path / "saved.py"})
    assert work.data == original
    assert work.entry == Path(original["entry"])
    assert json.loads(work.manifest.read_text(encoding="utf-8")) == external


@pytest.mark.parametrize(
    "example,entry",
    [
        ("../outside.py", None),
        ("", None),
        ("main.py", "relative.py"),
    ],
)
def test_invalid_attempt_paths_are_ignored(tmp_path, monkeypatch, example, entry):
    attempts = tmp_path / "attempts"
    root = attempts / "bad"
    root.mkdir(parents=True)
    file = entry or str(root / "main.py")
    (root / "work.json").write_text(
        json.dumps(
            {
                "format": 1,
                "example": example,
                "opened": 1,
                "created": 1,
                "entry": file,
                "files": [file],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "little_tinker_rig.core.example_work.attempts_directory", lambda: attempts
    )
    assert ExampleWork.all() == []


def test_failed_attempt_timestamp_write_does_not_change_opened_order(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    examples = tmp_path / "bundled"
    examples.mkdir()
    source = examples / "main.py"
    source.write_text("print(1)\n", encoding="utf-8")
    work = ExampleWork.create(source, examples)
    opened = work.data["opened"]
    work.manifest.write_text(
        json.dumps(dict(work.data, opened=opened + 1)), encoding="utf-8"
    )
    window = Studio(tmp_path / "plain.py")
    try:
        with pytest.raises(ExternalChangeError):
            window.example_workspaces.open(work=work)
        assert work.data["opened"] == opened
        assert work.identity not in window.example_workspaces.works
        assert window.documents.count() == 1
    finally:
        window.recovery.close()
        window.deleteLater()


def test_corrupt_attempt_does_not_hide_other_examples(tmp_path, qt_app, monkeypatch):
    from little_tinker_rig.qt.app import Studio

    examples = tmp_path / "bundled"
    examples.mkdir()
    source = examples / "main.py"
    source.write_text("print(1)\n", encoding="utf-8")
    valid = ExampleWork.create(source, examples)
    broken = attempts_directory() / "broken"
    broken.mkdir()
    (broken / "work.json").write_text("{unfinished", encoding="utf-8")
    incomplete = attempts_directory() / "incomplete"
    incomplete.mkdir()
    (incomplete / "work.json").write_text('{"format": 1}', encoding="utf-8")
    undecodable = attempts_directory() / "undecodable"
    undecodable.mkdir()
    (undecodable / "work.json").write_bytes(b"\xff")
    impossible_date = attempts_directory() / "impossible_date"
    impossible_date.mkdir()
    (impossible_date / "work.json").write_text(
        json.dumps({**valid.data, "opened": 10**100}), encoding="utf-8"
    )
    monkeypatch.setattr("little_tinker_rig.qt.app.examples_directory", lambda: examples)

    window = Studio()
    try:
        assert [work.identity for work in ExampleWork.all()] == [valid.identity]
        window.refresh_examples()
        attempts = next(
            action.menu()
            for action in window.examples_menu.actions()
            if action.text() == "My attempts"
        )
        assert attempts.isEnabled() and len(attempts.actions()) == 1
        page = window.example_workspaces.open(source)
        assert page.example_work.identity == valid.identity
    finally:
        window.recovery.close()
        window.deleteLater()


@pytest.mark.parametrize("older_present", [False, True])
def test_open_example_skips_attempt_with_missing_program(
    tmp_path, qt_app, monkeypatch, older_present
):
    from little_tinker_rig.qt.app import Studio

    examples = tmp_path / "bundled"
    examples.mkdir()
    source = examples / "main.py"
    source.write_text("print(1)\n", encoding="utf-8")
    older = ExampleWork.create(source, examples) if older_present else None
    missing = ExampleWork.create(source, examples)
    missing.entry.unlink()
    monkeypatch.setattr("little_tinker_rig.qt.app.examples_directory", lambda: examples)

    window = Studio()
    try:
        selected = window.example_workspaces.open(source).example_work
        assert selected is not None and selected.identity != missing.identity
        if older is not None:
            assert selected.identity == older.identity
        else:
            assert selected.entry.is_file()
            assert len(ExampleWork.all()) == 2
    finally:
        window.recovery.close()
        window.deleteLater()


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
        assert window.save_as() is False
        assert "another example attempt" in window.last_error
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
        assert window.save_as() is False
        assert "different module" in window.last_error
        assert not destination.exists() and collision.read_text() == "value = 99\n"
        assert page.session.project.path == copied
    finally:
        window.confirm_close = lambda *_: True
        window.close()


def test_autosave_continues_after_one_example_conflicts(tmp_path, qt_app, monkeypatch):
    from little_tinker_rig.qt.app import Studio

    examples = tmp_path / "bundled"
    examples.mkdir()
    first_source = examples / "first.py"
    second_source = examples / "second.py"
    first_source.write_text("print(1)\n", encoding="utf-8")
    second_source.write_text("print(2)\n", encoding="utf-8")
    monkeypatch.setattr("little_tinker_rig.qt.app.examples_directory", lambda: examples)

    window = Studio(first_source)
    try:
        first = window.document_page
        first.session.editor.commit("print('unsaved first')\n")
        first_file = first.session.project.path
        first_file.write_text("print('external change')\n", encoding="utf-8")

        second = window.open_document(second_source)
        second.session.editor.commit("print('saved second')\n")
        lesson_saves = []
        monkeypatch.setattr(
            window.lessons, "autosave", lambda: lesson_saves.append(True)
        )

        assert not window.recovery.flush()
        assert first_file.read_text(encoding="utf-8") == "print('external change')\n"
        assert ast.dump(
            ast.parse(second.session.project.path.read_text(encoding="utf-8"))
        ) == ast.dump(ast.parse("print('saved second')\n"))
        assert lesson_saves == [True]
        checkpoint = json.loads(window.recovery.path.read_text(encoding="utf-8"))
        assert len(checkpoint["documents"]) == 2
        assert ast.dump(ast.parse(checkpoint["documents"][0]["source"])) == ast.dump(
            ast.parse("print('unsaved first')\n")
        )
    finally:
        window.confirm_close = lambda *_: True
        window.close()
