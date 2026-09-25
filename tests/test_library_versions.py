"""Personal libraries and future snapshots preserve programs and published code."""

import tomllib

import pytest

from pyblocks.core.authoring import DefinitionDraft, user_collection
from pyblocks.core.paths import personal_collection
from pyblocks.core.session import Session
from pyblocks.core.snippets import (
    instantiate,
    load_collection,
    load_module,
    recognize,
    snippet_groups,
    upgrade,
)
from pyblocks.core.syntax import Syntax
from pyblocks.core.versions import next_version

SOURCE = '@block(level="beginner", color="action", icon="▶")\ndef show(value: "number" = 3):\n    print(value + 1)\n'


def test_personal_library_is_lazy_global_and_not_a_project_path(tmp_path):
    first = Session(tmp_path / "examples" / "one.py")
    assert not personal_collection().exists()
    assert not (tmp_path / "examples" / "blocks").exists()
    root = user_collection()
    draft = DefinitionDraft(root / "custom.py")
    draft.source = SOURCE
    draft.save()
    first.set_snippets(first.load_snippets())
    second = Session(tmp_path / "two.py", (root,))
    assert first.collection_paths == second.collection_paths == (root,)
    assert not first.project.collections
    assert (
        len([s for s in second.snippets if s.identity == "my_blocks/custom/show"]) == 1
    )
    assert {s.identity for s in first.snippets} == {s.identity for s in second.snippets}
    first.project.path.parent.mkdir()
    first.project.save()
    assert not first.project.workspace_path.exists()


def test_snapshots_and_helper_upgrades_preserve_other_calls_and_undo(tmp_path):
    root = user_collection(tmp_path)
    path = root / "custom.py"
    path.write_text(SOURCE)
    session = Session(tmp_path / "main.py", (root,))
    old = load_collection(root)[0]
    expansion = instantiate(old, {})
    session.editor.commit(
        expansion.source + "\n# Keep this comment\n" + expansion.source
    )
    before = session.document.state
    next_version(root, "1.1.0")
    archived = root / "history/1.0.0/custom.py"
    assert archived.read_text() == SOURCE
    assert DefinitionDraft(archived).read_only
    assert (root / "history/1.0.0/snapshot.toml").is_file()
    path.write_text(SOURCE.replace("value + 1", "value + 2"))
    session.set_snippets(session.load_snippets())
    assert session.document.state is before
    assert (
        len(
            [
                s
                for group in snippet_groups(session.available_snippets).values()
                for s in group
                if s.identity == old.identity
            ]
        )
        == 1
    )
    matches = [m for m in session.matches if m.snippet.identity == old.identity]
    assert len(matches) == 2 and all(m.snippet.historical for m in matches)
    session.editor.select(matches[-1].span.start)
    candidate = session.upgraded_source()
    assert session.document.state is before
    assert "# Keep this comment" in candidate
    output = []
    exec(candidate, {"print": output.append})
    assert output == [4, 5]
    session.upgrade_selected()
    assert session.document.state.source == candidate
    session.editor.undo()
    assert session.document.state is before
    next_version(root, "1.2.0")
    assert not (root / "history/1.1.0/history").exists()
    assert archived.read_text() == SOURCE
    assert {s.version for s in load_collection(root)} == {"1.0.0", "1.1.0", "1.2.0"}


def test_version_failures_leave_manifest_modules_and_history_unchanged(
    tmp_path, monkeypatch
):
    root = user_collection(tmp_path)
    (root / "custom.py").write_text(SOURCE)
    manifest = (root / "collection.toml").read_bytes()
    draft = DefinitionDraft(root / "custom.py")
    draft.source += "\n# unfinished work"
    draft.persist()
    with pytest.raises(ValueError, match="drafts"):
        next_version(root, "1.1.0")
    draft.draft_path.unlink()
    with pytest.raises(ValueError, match="greater"):
        next_version(root, "1.0.0")

    def fail(*_):
        raise OSError("injected manifest write failure")

    monkeypatch.setattr("pyblocks.core.versions.atomic_write", fail)
    with pytest.raises(OSError):
        next_version(root, "1.1.0")
    assert (root / "collection.toml").read_bytes() == manifest
    assert (root / "custom.py").read_text() == SOURCE
    assert not (root / "history/1.0.0").exists()
    # A crash before registering an archive must not expose its modules as current.
    orphan = root / "history/orphan"
    orphan.mkdir(parents=True)
    (orphan / "custom.py").write_text(SOURCE)
    assert len(load_collection(root)) == 1


def test_upgrade_rejects_changed_units():
    source = '@inline_block\ndef show(value: "number[mm]" = 3):\n    print(value)\n'
    old = load_module(source, "test", "1.0.0", historical=True)[0]
    new = load_module(source.replace("[mm]", "[deg]"), "test", "1.1.0")[0]
    match = recognize(Syntax("print(7)\n"), (old,))[0]
    with pytest.raises(ValueError, match="types or units"):
        upgrade(match, new)


def test_start_version_refreshes_definition_editor_without_editing_program(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QInputDialog

    from pyblocks.qt.app import Studio

    window = Studio(tmp_path / "main.py")
    window.confirm_close = lambda page: True
    try:
        window.block_editor.create(SOURCE)
        window.block_editor.save()
        source = window.block_editor.code.toPlainText()
        original = window.session.document.state
        root = window.block_editor.code.draft.root
        monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("1.1.0", True))
        window.block_editor.start_version()
        assert window.block_editor.code.toPlainText() == source
        assert window.block_editor.code.draft.version == "1.1.0"
        assert window.session.document.state is original
        assert (
            tomllib.loads((root / "collection.toml").read_text())["history"][0][
                "version"
            ]
            == "1.0.0"
        )
        window.block_editor.save()
    finally:
        window.close()


def test_appearance_choices_use_source_values_across_languages(tmp_path, qt_app):
    from pyblocks.i18n import set_language
    from pyblocks.qt.authoring import BlockEditor

    root = user_collection(tmp_path)
    page = BlockEditor(lambda: root, lambda *_: None)
    try:
        page.create(SOURCE)
        original = page.code.toPlainText()
        index = page.color.findData("loop")
        page.color.setCurrentIndex(index)
        page.color.activated.emit(index)
        assert page.preview_snippet.color == "loop"
        modified = page.code.toPlainText()
        set_language("ru")
        page.retranslate()
        assert page.color.value() == "loop"
        assert page.code.toPlainText() == modified
        page.code.undo()
        page.check()
        assert page.code.toPlainText() == original
        assert page.color.value() == "action"
        page.icon.setEditText("🛞")
        page.icon.lineEdit().editingFinished.emit()
        page.save()
        assert load_collection(root)[0].icon == "🛞"
    finally:
        page.close()


def test_upgrade_dialog_reviews_exact_changes_and_cancel_keeps_source(tmp_path, qt_app):
    from PySide6.QtCore import QTimer

    from pyblocks.qt.app import Studio
    from pyblocks.qt.dialogs import EditDialog

    root = user_collection()
    path = root / "custom.py"
    path.write_text(SOURCE)
    session = Session(tmp_path / "main.py")
    expansion = instantiate(load_collection(root)[0], {})
    session.editor.commit(expansion.source)
    session.project.save()
    next_version(root, "1.1.0")
    path.write_text(SOURCE.replace("value + 1", "value + 2"))
    window = Studio(session.project.path)
    window.confirm_close = lambda page: True
    try:
        match = next(m for m in window.session.matches if m.snippet.historical)
        window.session.editor.select(match.span.start)
        original = window.session.document.state
        checked = []

        def review(accept):
            dialog = next(d for d in window.findChildren(EditDialog) if d.isVisible())
            checked.append(dialog.text.toPlainText())
            assert dialog.text.isReadOnly()
            if accept:
                dialog.apply()
            else:
                dialog.reject()

        QTimer.singleShot(0, lambda: review(False))
        window.upgrade_block()
        assert window.session.document.state is original
        QTimer.singleShot(0, lambda: review(True))
        window.upgrade_block()
        assert checked[0] == checked[1]
        assert "value + 2" in checked[0]
        assert window.session.document.state is not original
        window.session.editor.undo()
        assert window.session.document.state is original
    finally:
        window.close()
