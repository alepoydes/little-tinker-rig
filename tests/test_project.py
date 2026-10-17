import json

import pytest

from little_tinker_rig.cli.main import main
from little_tinker_rig.core.project import Project
from little_tinker_rig.core.session import Session


@pytest.mark.parametrize("suffix", [".ltr.json", ".pyblocks.json"])
def test_save_reopen_and_external_change_detection(tmp_path, suffix):
    path = tmp_path / "main.py"
    project = Project(path)
    project.document.commit("x = 2\n", ("incomplete(",))
    project.save()
    project.workspace_path.rename(path.with_suffix(".py" + suffix))
    restored = Project(path)
    assert restored.document.state == project.document.state
    path.write_text("x = 3\n")
    with pytest.raises(ValueError, match="outside"):
        project.save()
    assert path.read_text() == "x = 3\n"


@pytest.mark.parametrize(
    "encoding, text, edited_cookie",
    [
        ("latin-1", "café", "cp1251"),
        ("cp1251", "Привет", "utf-8"),
        ("utf-8-sig", "Привет", "unknown"),
    ],
)
def test_legacy_source_and_edited_cookie_save_as_utf8(
    tmp_path, encoding, text, edited_cookie
):
    path = tmp_path / "main.py"
    cookie = "utf-8" if encoding == "utf-8-sig" else encoding
    source = f'# coding: {cookie}\nname = "{text}"\n'
    path.write_bytes(source.encode(encoding))
    project = Project(path)
    edited = source.replace(cookie, edited_cookie)
    project.document.commit(edited)
    project.save()
    expected = source.replace(cookie, "utf-8")
    assert path.read_bytes() == expected.encode("utf-8")
    assert project.state.source == Project(path).state.source == expected
    assert not project.dirty
    if edited != expected:
        project.document.undo()
        assert project.state.source == edited and project.dirty


def test_session_selection_survives_save_normalization_and_subsequent_edits(tmp_path):
    path = tmp_path / "main.py"
    path.write_bytes(b"# coding: latin-1\nvalue = 1\n")
    session = Session(path)
    session.editor.select(session.document.state.source.index("value"))
    session.project.save()
    assert session.document.syntax.text(session.editor.selection) == "value"
    session.editor.commit(session.document.state.source.replace("= 1", "= 2"))
    session.project.save()
    assert Project(path).state.source == "# coding: utf-8\nvalue = 2\n"
    session.editor.undo()
    assert session.editor.selection in session.document.syntax.spans
    assert session.project.dirty


def test_external_scratch_change_is_not_overwritten(tmp_path):
    project = Project(tmp_path / "main.py")
    project.document.commit("value = 1\n", ("draft(",))
    project.save()
    other = Project(project.path)
    other.document.commit("value = 1\n", ("new_draft(",))
    other.save()
    project.document.commit("value = 2\n")
    with pytest.raises(ValueError, match="Workspace changed outside"):
        project.save()
    reopened = Project(project.path)
    assert reopened.document.state == other.document.state


def test_session_inserts_imports_and_edits_parameters_atomically(tmp_path):
    session = Session(tmp_path / "main.py")
    snippet = next(s for s in session.snippets if s.identity.endswith("/create_motor"))
    session.insert_snippet(snippet, {"name": "left_motor"})
    assert "from pybricks.pupdevices import Motor" in session.document.state.source
    session.editor.select(session.document.state.source.index("left_motor"))
    assert session.selected_match().snippet == snippet
    session.edit_parameters({"port": "Port.B"})
    assert "Motor(Port.B)" in session.document.state.source
    before = session.document.state
    with pytest.raises((ValueError, SyntaxError)):
        session.edit_parameters({"name": "1 + 2"})
    assert session.document.state == before


def test_cli_transform_is_read_only_without_write(tmp_path, capsys):
    path = tmp_path / "main.py"
    path.write_text("x=1\n")
    assert main(["replace", str(path), "2 + 3", "--at", "1:4"]) == 0
    assert "2 + 3" in capsys.readouterr().out
    assert path.read_text() == "x=1\n"
    assert main(["inspect", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["regions"]


def test_cli_can_export_hub_helper(tmp_path):
    path = tmp_path / "little_tinker_rig_controller.py"
    assert main(["controller", str(path), "--write"]) == 0
    assert "class Controller:" in path.read_text()


def test_interrupted_restore_save_preserves_scratch_copy(tmp_path, monkeypatch):
    from little_tinker_rig.core import project as storage

    path = tmp_path / "main.py"
    project = Project(path)
    project.document.commit("", ("print(42)",))
    project.save()
    project.document.commit("print(42)\n", ())
    write = storage.atomic_write

    def fail_main(destination, text, encoding="utf-8"):
        if destination == path:
            raise OSError("disk full")
        write(destination, text, encoding)

    monkeypatch.setattr(storage, "atomic_write", fail_main)
    with pytest.raises(OSError):
        project.save()
    reopened = Project(path)
    assert "print(42)" in reopened.document.state.scratch
    monkeypatch.setattr(storage, "atomic_write", write)
    project.save()
    assert Project(path).document.state == project.document.state


def test_interrupted_save_preserves_scratch_multiplicity(tmp_path, monkeypatch):
    from little_tinker_rig.core import project as storage

    path = tmp_path / "main.py"
    project = Project(path)
    project.document.commit("x = 1\n", ("same\n", "same\n", "old\n"))
    project.save()
    project.document.commit("x = 2\n", ("new\n", "same\n", "same\n", "same\n"))
    write = storage.atomic_write

    def fail_main(destination, text, encoding="utf-8"):
        if destination == path:
            raise OSError("disk full")
        write(destination, text, encoding)

    monkeypatch.setattr(storage, "atomic_write", fail_main)
    with pytest.raises(OSError):
        project.save()
    assert Project(path).document.state.scratch == (
        "new\n",
        "same\n",
        "same\n",
        "same\n",
        "old\n",
    )
    monkeypatch.setattr(storage, "atomic_write", write)
    project.save()
    assert Project(path).document.state.scratch == project.document.state.scratch


def test_collection_history_upgrade_and_pin(tmp_path):
    collection = tmp_path / "course"
    history = collection / "old_versions" / "1.0.0"
    history.mkdir(parents=True)
    (collection / "collection.toml").write_text(
        '[collection]\nid = "course"\nversion = "1.1.0"\n[[history]]\nversion = "1.0.0"\npath = "old_versions/1.0.0"\n'
    )
    (collection / "actions.py").write_text('def show(x, end="!"):\n    print(x, end)\n')
    (history / "actions.py").write_text(
        'def show(x):\n    print(x)\n    print("done")\n'
    )
    path = tmp_path / "main.py"
    path.write_text('print(42)  # keep this explanation\nprint("done")\n')
    session = Session(path, (collection,))
    session.editor.select(0)
    assert session.selected_match().snippet.historical
    session.upgrade_selected()
    assert "# keep this explanation" in session.document.state.source
    assert 'print(42, "!")' in session.document.state.source
    session.project.pins = {"course": "1.1.0"}
    session.project.save()
    assert Session(path).project.pins == {"course": "1.1.0"}
    session.project.pins = {"course": "1.0.0"}
    session.project.save()
    with pytest.raises(ValueError, match="requires version"):
        Session(path)
