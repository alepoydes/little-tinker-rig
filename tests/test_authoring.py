"""Definition edits remain static, recoverable and independent of program text."""

import ast
import json
from unittest.mock import patch

import pytest

from pyblocks.core.authoring import (
    DefinitionDraft,
    template_from_source,
    user_collection,
)
from pyblocks.core.session import Session
from pyblocks.core.snippets import builtin_snippets, instantiate, load_collection

SOURCE = 'def show(value=1):\n    """Show a value."""\n    print(value)\n'


def definition(tmp_path, source=SOURCE):
    root = user_collection(tmp_path)
    path = root / "actions.py"
    path.write_text(source, encoding="utf-8")
    return DefinitionDraft(path)


def test_drafts_recover_invalid_source_without_touching_library(tmp_path):
    draft = definition(tmp_path)
    draft.source = "def show(\n"
    draft.persist()
    with pytest.raises(SyntaxError):
        draft.save()
    assert draft.path.read_text() == SOURCE
    assert instantiate(load_collection(draft.root)[0], {}).source == "print(1)"
    reopened = DefinitionDraft(draft.path)
    assert reopened.source == draft.source
    assert reopened.dirty
    reopened.source = SOURCE.replace("print(value)", "print(value + 1)")
    reopened.levels["actions/show"] = "beginner"
    reopened.save()
    assert not reopened.dirty
    assert not reopened.draft_path.exists()
    assert load_collection(reopened.root)[0].level == "beginner"
    reopened.levels["actions/show"] = "advanced"
    assert reopened.dirty


def test_template_validation_is_static_and_locates_errors(tmp_path):
    draft = definition(
        tmp_path,
        'def run(motor: "Motor" = motor, speed=300):\n    """Run."""\n    motor.run(speed)\n',
    )
    _, snippets = draft.inspect()
    assert instantiate(snippets[0], {}).source == "motor.run(300)"
    draft.source = 'def run(value=__import__("pathlib").Path("DO_NOT_CREATE").touch()):\n    print(value)\n'
    with patch("pathlib.Path.touch", side_effect=AssertionError("executed")):
        draft.inspect()
        draft.save()
    draft.source = "def ok():\n    print(1)\n\ndef invalid(*args):\n    print(args)\n"
    with pytest.raises(SyntaxError) as error:
        draft.inspect()
    assert error.value.lineno == 4
    draft.source = "import math\n" + SOURCE
    with pytest.raises(SyntaxError, match="inside template functions"):
        draft.inspect()


def test_save_validates_whole_collection_and_preserves_other_modules(tmp_path):
    first = definition(tmp_path)
    second = DefinitionDraft(first.root / "numbers.py")
    second.source = "def double(value=1):\n    return value * 2\n"
    second.levels["numbers/double"] = "advanced"
    second.save()
    first.source = SOURCE.replace("show", "display")
    first.levels["actions/display"] = "beginner"
    first.save()
    snippets = load_collection(first.root)
    assert {s.identity: s.level for s in snippets} == {
        "my_blocks/actions/display": "beginner",
        "my_blocks/numbers/double": "advanced",
    }
    first.source = SOURCE + SOURCE
    with pytest.raises(ValueError, match="Duplicate"):
        first.save()
    assert first.path.read_text() == SOURCE.replace("show", "display")


def test_save_refuses_external_edits_and_rolls_back_manifest_failure(tmp_path):
    draft = definition(tmp_path)
    draft.source = SOURCE.replace("1", "2")
    draft.path.write_text(SOURCE.replace("1", "3"))
    with pytest.raises(ValueError, match="outside"):
        draft.save()
    assert draft.path.read_text().endswith("print(value)\n")
    draft = DefinitionDraft(draft.path)
    original = draft.saved_source
    draft.source = SOURCE
    from pyblocks.core.project import atomic_write

    def fail_manifest(path, text):
        if path.name == "collection.toml":
            raise OSError("unavailable")
        atomic_write(path, text)

    with patch("pyblocks.core.authoring.atomic_write", fail_manifest):
        with pytest.raises(OSError, match="unavailable"):
            draft.save()
    assert draft.path.read_text() == original
    assert draft.draft_path.exists()


def test_reloading_templates_never_changes_source_scratch_or_undo(tmp_path):
    draft = definition(tmp_path)
    program = tmp_path / "main.py"
    program.write_text("print(1)\n")
    session = Session(program, (draft.root,))
    session.editor.commit("print(2)\n", ("print(3)",))
    before = session.document.state
    assert any(m.snippet.identity == "my_blocks/actions/show" for m in session.matches)
    draft.source = SOURCE.replace("print(value)", "print(value + 1)")
    draft.save()
    session.set_snippets(session.load_snippets())
    assert session.document.state is before
    assert not any(
        m.snippet.identity == "my_blocks/actions/show" for m in session.matches
    )
    session.editor.undo()
    assert session.document.state.source == "print(1)\n"
    session.project.save_collections()
    assert program.read_text() == "print(1)\n"
    assert json.loads(session.project.workspace_path.read_text())["collections"] == [
        "blocks"
    ]
    assert Session(program).project.collections == [draft.root]


def test_builtins_have_readonly_origins_and_all_preview_statically():
    for path in {s.source_path for s in builtin_snippets()}:
        draft = DefinitionDraft(path)
        assert draft.read_only
        assert draft.inspect()[1]
        with pytest.raises(ValueError, match="read-only"):
            draft.save()


def test_selection_becomes_a_template_without_executing_it():
    source = template_from_source(
        "motor.run(300)\nwait(500)\nmotor.brake()", ("from pybricks.tools import wait",)
    )
    from pyblocks.core.snippets import load_module

    snippet = load_module(source, "test", "1")[0]
    expansion = instantiate(snippet, {})
    assert ast.dump(ast.parse(expansion.source)) == ast.dump(
        ast.parse("motor.run(300)\nwait(500)\nmotor.brake()")
    )
    assert expansion.imports == ("from pybricks.tools import wait",)


def test_editor_preview_navigation_drafts_and_test_values(tmp_path, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest

    from pyblocks.qt.authoring import BlockEditor

    root = user_collection(tmp_path)
    page = BlockEditor(lambda: root, lambda root, snippets: None)
    page.resize(1200, 800)
    page.show()
    try:
        snippets = builtin_snippets()
        page.configure(snippets, (root,))
        page.open_definition(
            next(s for s in snippets if s.identity == "pybricks/motors/run_motor")
        )
        original = page.code.toPlainText()
        QTest.keyClick(page.code, Qt.Key.Key_Return)
        QTest.keyClick(page.code, Qt.Key.Key_Tab)
        assert page.code.toPlainText() == original
        page.copy_block()
        assert not page.code.isReadOnly()
        page.code.setPlainText(
            SOURCE
            + '\n\n# between functions\n\ndef other(value=2):\n    """Other."""\n    print(value + 2)\n'
        )
        page.check()
        page.code.moveCursor(QTextCursor.MoveOperation.Start)
        page.check()
        assert page.preview.toPlainText().strip() == "print(1)"
        original = page.code.toPlainText()
        page.test_value("value", "42")
        assert page.preview.toPlainText().strip() == "print(42)"
        assert page.code.toPlainText() == original
        slot = next(
            p for p in page.preview.parameter_slots if p.parameter.name == "value"
        )
        qt_app.processEvents()
        QTest.mouseClick(
            page.preview.viewport(),
            Qt.MouseButton.LeftButton,
            pos=page.preview.parameter_rect(slot).center().toPoint(),
        )
        assert page.code.textCursor().selectedText() == "value"
        assert page.code.references
        code = page.code
        cursor = QTextCursor(code.document().findBlockByNumber(6))
        code.setTextCursor(cursor)
        assert page.preview_snippet.identity.endswith("/show")
        code.moveCursor(QTextCursor.MoveOperation.End)
        code.moveCursor(QTextCursor.MoveOperation.PreviousBlock)
        assert page.preview_snippet.identity.endswith("/other")
        previous = page.preview.toPlainText()
        code.moveCursor(QTextCursor.MoveOperation.End)
        code.insertPlainText("\ndef broken(\n")
        page.check()
        assert code.problem
        assert page.preview.toPlainText() == previous
        assert "last valid" in page.status.text()
        saved_path = code.draft.path
        page.open_definition(snippets[0])
        page.open_path(saved_path)
        assert page.code is code
        assert page.code.document().isUndoAvailable()
        assert page.code.problem
        assert page.preview.toPlainText() == previous
        page.code.undo()
        page.check()
        assert page.code.problem is None
        page.create(
            'def many():\n    """Several lines."""\n'
            + "".join(f"    print({i})\n" for i in range(8))
        )
        assert not page.preview.document().findBlockByNumber(4).isVisible()
        page.expand.setChecked(True)
        assert page.preview.document().findBlockByNumber(4).isVisible()
    finally:
        page.flush()
        page.close()
        page.deleteLater()


def test_studio_applies_definitions_without_committing_program_drafts(tmp_path, qt_app):
    from PySide6.QtCore import QUrl

    from pyblocks.qt.app import Studio

    program = tmp_path / "main.py"
    program.write_text("print(1)\n")
    window = Studio(program)
    window.confirm_close = lambda page: True
    try:
        window.help_page.follow_link(QUrl("pyblocks-definition:python/basics/show"))
        # Open through the actual library signal with an existing template.
        snippet = window.session.snippets[0]
        window.library.definition_requested.emit(snippet.identity)
        assert window.pages.currentIndex() == 3
        assert window.block_editor.code.isReadOnly()
        window.block_editor.create(SOURCE)
        root = window.block_editor.code.draft.root
        state = window.session.document.state
        window.block_editor.save()
        assert window.session.document.state is state
        assert any(
            s.identity == "my_blocks/custom/show" for s in window.session.snippets
        )
        assert Session(program).project.collections == [root]
        window.set_mode(0)
        window.session.editor.commit("print(1)\n", ("print(2)",))
        window.refresh_views()
        window.change_editor(1)
        window.code.setPlainText("def unfinished(\n")
        before = window.session.document.state
        window.set_mode(3)
        window.block_editor.code.setPlainText(
            SOURCE.replace("print(value)", "print(value + 3)")
        )
        window.save()
        assert window.code.toPlainText() == "def unfinished(\n"
        assert window.session.document.state is before
        assert (
            window.scratch.cells[0].source.session.snippets is window.session.snippets
        )
        assert not any(
            m.snippet.identity.startswith("my_blocks/") for m in window.session.matches
        )
        path = window.block_editor.code.draft.path
        window.block_editor.code.setPlainText("def unfinished(\n")
        window.block_editor.check()
        window.block_editor.flush()
        recovered = DefinitionDraft(path)
        assert recovered.source == "def unfinished(\n"
        assert "print(value + 3)" in recovered.preview_source
    finally:
        window.close()
        window.deleteLater()


def test_selection_preserves_multiline_literals_and_expression_kind():
    from pyblocks.core.snippets import load_module

    source = '    message = """first\n  exact spaces\nlast"""\n    print(message)\n'
    snippet = load_module(template_from_source(source), "test", "1")[0]
    expansion = instantiate(snippet, {})
    literal = next(
        n.value
        for n in ast.walk(ast.parse(expansion.source))
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    )
    assert literal == "first\n  exact spaces\nlast"
    snippet = load_module(
        template_from_source("# explanation\nleft + right", expression=True),
        "test",
        "1",
    )[0]
    assert snippet.expression
    assert instantiate(snippet, {}).source == "left + right"
    snippet = load_module(template_from_source("print(1)"), "test", "1")[0]
    assert not snippet.expression


def test_editor_groups_copies_and_language_changes_keep_edits(tmp_path, qt_app):
    from PySide6.QtGui import QTextCursor

    from pyblocks.qt.app import Studio

    window = Studio(tmp_path / "main.py")
    window.confirm_close = lambda page: True
    window.show()
    try:
        window.set_mode(3)
        page = window.block_editor
        page.module_name.setText("robots/motors")
        page.create(SOURCE)
        page.create(SOURCE)
        assert page.code.draft.module == "robots/motors"
        assert {s.identity.rsplit("/", 1)[1] for s in page.code.snippets} == {
            "show",
            "show_2",
        }
        assert page.preview_snippet.identity.endswith("/show_2")
        page.save()
        assert {
            s.identity.rsplit("/", 1)[0] for s in load_collection(page.code.draft.root)
        } == {"my_blocks/robots/motors"}
        page.code.moveCursor(QTextCursor.MoveOperation.End)
        page.code.insertPlainText("\n# Draft comment\n")
        source = page.code.toPlainText()
        page.check()
        qt_app.processEvents()
        sizes = page.vertical.sizes()
        page.code.insertPlainText("\n# Another comment\n")
        page.check()
        qt_app.processEvents()
        assert page.vertical.sizes() == sizes
        window.change_language("ru")
        assert window.mode_tabs.tabText(3) == "Редактор блоков"
        assert page.save_button.text() == "Сохранить и применить"
        assert window.help_page.root.name == "ru"
        page.code.undo()
        assert page.code.toPlainText() == source
        window.change_language("en")
        assert page.save_button.text() == "Save and apply"
        assert page.test_fields["value"].toolTip().startswith("Preview value only")
    finally:
        window.close()
        window.deleteLater()
