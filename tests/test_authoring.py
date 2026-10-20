"""Definition edits remain static, recoverable and independent of program text."""

import ast
import json
from unittest.mock import patch

import pytest

from little_tinker_rig.core.authoring import (
    DefinitionDraft,
    selection_imports,
    template_from_source,
    user_collection,
)
from little_tinker_rig.core.block_metadata import change_property
from little_tinker_rig.core.session import Session
from little_tinker_rig.core.snippets import (
    builtin_snippets,
    instantiate,
    load_collection,
)

SOURCE = '@inline_block(level="intermediate", icon="▶", color="action")\ndef show(value=1):\n    """Show a value."""\n    print(value)\n'


@pytest.mark.parametrize(
    "source, selected, argument, expected",
    [
        (
            "def root(x):\n    return sqrt(x)\nfrom math import sqrt\n",
            "def root(x):\n    return sqrt(x)\n",
            9,
            3.0,
        ),
        (
            "from math import sqrt as calculate\ndef root(x):\n    return calculate(x)\nfrom cmath import sqrt as calculate\n",
            "def root(x):\n    return calculate(x)\n",
            -1,
            1j,
        ),
        (
            "from math import sqrt\nclass C:\n    from cmath import sqrt\n    def root(x):\n        return sqrt(x)\n",
            "def root(x):\n        return sqrt(x)\n",
            9,
            3.0,
        ),
    ],
)
def test_captured_functions_keep_deferred_imports(
    tmp_path, source, selected, argument, expected
):
    from little_tinker_rig.core.snippets import load_module
    from little_tinker_rig.core.syntax import Syntax

    imports = selection_imports(selected, Syntax(source), source.index(selected))
    snippet = load_module(
        template_from_source(selected, imports), "review/custom", "1"
    )[0]
    target = Session(tmp_path / "new.py")
    target.insert_snippet(snippet, {})
    namespace = {}
    exec(target.document.state.source, namespace)
    result = namespace["root"](argument)
    assert result == expected and type(result) is type(expected)


@pytest.mark.parametrize(
    "source, selected, expected",
    [
        (
            "from math import sqrt, sin\nresult = sqrt(4)\nfrom cmath import sqrt\n",
            "result = sqrt(4)",
            ("from math import sqrt",),
        ),
        (
            "from math import sqrt\ndef f(sqrt):\n    return sqrt(4)\n",
            "return sqrt(4)",
            (),
        ),
        (
            "from math import sqrt\ndef f():\n    from cmath import sqrt\n    result = sqrt(-1)\n",
            "result = sqrt(-1)",
            ("from cmath import sqrt",),
        ),
        (
            "from math import sqrt\nsqrt = print\nresult = sqrt(4)\n",
            "result = sqrt(4)",
            (),
        ),
        (
            'from robot import Motor\ndef move(motor: "Motor"):\n    pass\n',
            'def move(motor: "Motor"):\n    pass\n',
            ("from robot import Motor",),
        ),
    ],
)
def test_selection_imports_follow_scope_and_selection_boundary(
    source, selected, expected
):
    from little_tinker_rig.core.syntax import Syntax

    assert (
        selection_imports(selected, Syntax(source), source.index(selected)) == expected
    )


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
    reopened.source = change_property(reopened.source, "show", "level", "beginner")
    reopened.save()
    assert not reopened.dirty
    assert not reopened.draft_path.exists()
    assert load_collection(reopened.root)[0].level == "beginner"
    reopened.source = change_property(reopened.source, "show", "level", "advanced")
    assert reopened.dirty


def test_template_validation_is_static_and_locates_errors(tmp_path):
    draft = definition(
        tmp_path,
        '@inline_block\ndef run(motor: "Motor" = motor, speed=300):\n    """Run."""\n    motor.run(speed)\n',
    )
    _, snippets = draft.inspect()
    assert instantiate(snippets[0], {}).source == "motor.run(300)"
    draft.source = '@inline_block\ndef run(value=__import__("pathlib").Path("DO_NOT_CREATE").touch()):\n    print(value)\n'
    with patch("pathlib.Path.touch", side_effect=AssertionError("executed")):
        draft.inspect()
        draft.save()
    draft.source = "@inline_block\ndef ok():\n    print(1)\n\n@inline_block\ndef invalid(*args):\n    print(args)\n"
    with pytest.raises(SyntaxError) as error:
        draft.inspect()
    assert error.value.lineno == 6
    draft.source = "import math\n" + SOURCE
    assert draft.inspect()[1]
    draft.source = 'print("must not execute")\n' + SOURCE
    with pytest.raises(SyntaxError, match="only"):
        draft.inspect()


def test_save_validates_whole_collection_and_preserves_other_modules(tmp_path):
    first = definition(tmp_path)
    second = DefinitionDraft(first.root / "numbers.py")
    second.source = (
        '@inline_block(level="advanced")\ndef double(value=1):\n    return value * 2\n'
    )
    second.save()
    first.source = SOURCE.replace("show", "display")
    first.source = change_property(first.source, "display", "level", "beginner")
    first.save()
    saved = first.source
    snippets = load_collection(first.root)
    assert {s.identity: s.level for s in snippets} == {
        "my_blocks/actions/display": "beginner",
        "my_blocks/numbers/double": "advanced",
    }
    first.source = SOURCE + SOURCE
    with pytest.raises(ValueError, match="Duplicate"):
        first.save()
    assert first.path.read_text() == saved


def test_save_refuses_external_edits_and_rolls_back_manifest_failure(tmp_path):
    draft = definition(tmp_path)
    draft.source = SOURCE.replace("1", "2")
    draft.path.write_text(SOURCE.replace("1", "3"))
    with pytest.raises(ValueError, match="outside"):
        draft.save()
    assert draft.path.read_text().endswith("print(value)\n")
    # Migrating an old module is the one operation that also updates its manifest.
    (draft.root / "collection.toml").write_text(
        '[collection]\nid="my_blocks"\nversion="1"\n[levels]\n"actions/show"="beginner"\n'
    )
    draft.path.write_text(SOURCE.split("\n", 1)[1])
    draft = DefinitionDraft(draft.path)
    original = draft.saved_source
    from little_tinker_rig.core.project import atomic_write

    def fail_manifest(path, text):
        if path.name == "collection.toml":
            raise OSError("unavailable")
        atomic_write(path, text)

    with patch("little_tinker_rig.core.authoring.atomic_write", fail_manifest):
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
    from little_tinker_rig.core.snippets import load_module

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

    from little_tinker_rig.qt.authoring import BlockEditor

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
            + '\n\n# between functions\n\n@inline_block\ndef other(value=2):\n    """Other."""\n    print(value + 2)\n'
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

    from little_tinker_rig.qt.app import Studio

    program = tmp_path / "main.py"
    program.write_text("print(1)\n")
    window = Studio(program)
    window.confirm_close = lambda page: True
    try:
        window.help_page.follow_link(
            QUrl("little-tinker-rig-definition:python/basics/show")
        )
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
        assert Session(program).project.collections == []
        assert Session(program).collection_paths == (root,)
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
    from little_tinker_rig.core.snippets import load_module

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

    from little_tinker_rig.qt.app import Studio

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
        sizes = page.preview_splitter.sizes()
        page.code.insertPlainText("\n# Another comment\n")
        page.check()
        qt_app.processEvents()
        assert page.preview_splitter.sizes() == sizes
        window.change_language("ru")
        assert window.modes.item(3).text() == "Редактор блоков"
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


def test_definition_search_reports_misses_and_restores_tree_after_escape(
    tmp_path, qt_app
):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QToolButton

    from little_tinker_rig.i18n import set_language
    from little_tinker_rig.qt.authoring import BlockEditor

    root = user_collection(tmp_path)
    page = BlockEditor(lambda: root, lambda *_: None)
    page.resize(868, 477)
    page.show()
    try:
        page.configure(builtin_snippets(), (root,))
        module = next(
            item for path, item in page.module_items.items() if path.name == "motors.py"
        )
        assert not module.isExpanded()
        cursor = page.code.textCursor().position()
        page.search.setText("run_motor")
        assert module.isExpanded()
        assert not page.search_status.isVisible()

        set_language("ru")
        page.retranslate()
        page.search.setText("there_is_no_such_definition")
        assert page.search_status.isVisible()
        assert page.search_status.text() == "Определения не найдены"
        assert page.code.textCursor().position() == cursor
        clear = page.search.findChild(QToolButton)
        assert clear.toolTip() == clear.accessibleName() == "Очистить поиск определений"

        page.search.setFocus()
        QTest.keyClick(page.search, Qt.Key.Key_Escape)
        qt_app.processEvents()
        assert not page.search.text()
        assert page.tree.hasFocus()
        module = next(
            item for path, item in page.module_items.items() if path.name == "motors.py"
        )
        assert not module.isExpanded()
        assert not page.search_status.isVisible()

        page.search.setText("run_motor")
        assert module.isExpanded()
        QTest.mouseClick(clear, Qt.MouseButton.LeftButton)
        assert not page.search.text()
        assert not module.isExpanded()
    finally:
        set_language("en")
        page.close()


def test_narrow_definition_editor_keeps_python_readable_with_console(
    tmp_path, qt_app
):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "main.py")
    window.confirm_close = lambda *_: True
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.show()
    try:
        window.change_language("ru")
        window.set_mode(3)
        window.console_dock.show()
        QTest.qWait(90)
        page = window.block_editor
        source = page.code.toPlainText()
        assert window.width() == 800
        assert not page.browser_pane.isVisible()
        assert page.preview_splitter.orientation() == Qt.Orientation.Horizontal
        assert page.code.viewport().width() >= 350
        assert page.browser_button.toolTip() == "Показать определения"
        assert page.browser_button.accessibleName() == page.browser_button.toolTip()
        window.resize(930, 620)
        QTest.qWait(50)
        assert page.browser_pane.isVisible()
        window.resize(800, 620)
        QTest.qWait(50)
        assert not page.browser_pane.isVisible()

        QTest.mouseClick(page.browser_button, Qt.MouseButton.LeftButton)
        QTest.qWait(50)
        assert window.width() == 800
        assert page.browser_pane.isVisible()
        assert not page.level.isVisible()
        assert page.browser_button.toolTip() == "Скрыть определения"
        assert page.code.toPlainText() == source

        QTest.mouseClick(page.browser_button, Qt.MouseButton.LeftButton)
        assert not page.browser_pane.isVisible()
        assert page.level.isVisible()
        assert page.code.toPlainText() == source
        window.resize(930, 620)
        QTest.qWait(50)
        assert not page.browser_pane.isVisible()
        assert page.level.isVisible()

        QTest.mouseClick(page.browser_button, Qt.MouseButton.LeftButton)
        assert page.browser_pane.isVisible()
        window.resize(800, 620)
        QTest.qWait(50)
        assert page.browser_pane.isVisible()
        assert not page.level.isVisible()
        window.resize(930, 620)
        QTest.qWait(50)
        assert page.browser_pane.isVisible()
        assert page.level.isVisible()
        motor = next(
            snippet
            for snippet in window.session.available_snippets
            if snippet.identity.endswith("/motor_target")
        )
        page.open_definition(motor)
        QTest.qWait(50)
        assert window.width() == 930
        assert page.icon.width() >= (
            page.icon.fontMetrics().horizontalAdvance(page.icon.currentText()) + 30
        )
    finally:
        window.close()
        window.deleteLater()


def test_compact_definition_find_reveals_search_field(tmp_path, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "main.py")
    window.confirm_close = lambda *_: True
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.show()
    try:
        window.set_mode(3)
        QTest.qWait(50)
        page = window.block_editor
        assert not page.browser_pane.isVisible()
        page.code.setFocus()
        QTest.keyClick(page.code, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        QTest.qWait(30)
        assert page.browser_pane.isVisible()
        assert page.search.hasFocus()
    finally:
        window.close()
        window.deleteLater()


def test_metadata_controls_are_source_edits_with_undo_and_no_manifest_changes(
    tmp_path, qt_app
):
    from little_tinker_rig.qt.authoring import BlockEditor

    root = user_collection(tmp_path)
    manifest = (root / "collection.toml").read_bytes()
    page = BlockEditor(lambda: root, lambda *_: None)
    try:
        page.create(SOURCE)
        original = page.code.toPlainText()
        page.level.setCurrentIndex(page.level.findData("expert"))
        assert page.preview_snippet.level == "expert"
        assert "expert" in page.code.toPlainText()
        page.code.undo()
        page.check()
        assert page.code.toPlainText() == original
        assert page.preview_snippet.level == "intermediate"
        page.icon.setEditText("↪")
        page.icon.lineEdit().editingFinished.emit()
        page.color.setEditText("#88bbcc")
        page.color.lineEdit().editingFinished.emit()
        page.save()
        saved = load_collection(root)[0]
        assert (saved.icon, saved.color) == ("↪", "#88bbcc")
        assert (root / "collection.toml").read_bytes() == manifest
        page.code.undo()
        page.check()
        assert page.preview_snippet.color == "action"
        assert page.preview_snippet.icon == "↪"
    finally:
        page.flush()
        page.close()


def test_shared_helpers_preview_copy_and_rename_together(tmp_path, qt_app):
    from little_tinker_rig.qt.authoring import BlockEditor

    root = user_collection(tmp_path)
    source = '''"""Measurements"""
from math import sqrt

def magnitude(value):
    return sqrt(value * value)

@block(level="beginner", color="value", icon="＝")
def measure(value=-3) -> "number":
    """Measure a value."""
    return magnitude(value)
'''
    path = root / "measurements.py"
    path.write_text(source)
    page = BlockEditor(lambda: root, lambda *_: None)
    try:
        page.configure(load_collection(root), (root,))
        page.open_path(path, "measure")
        assert page.preview_snippet.identity.endswith("/measure")
        assert len(page.preview_snippet.helpers) == 2
        page.copy_block()
        page.copy_block()
        page.save()
        snippets = [s for s in load_collection(root) if "/custom/" in s.identity]
        assert len(snippets) == 2
        for snippet in snippets:
            expanded = instantiate(snippet, {})
            namespace = {}
            exec("\n".join((*expanded.imports, *expanded.helpers)), namespace)
            assert eval(expanded.source, namespace) == 3
        assert "magnitude_2" in page.code.toPlainText()
    finally:
        page.flush()
        page.close()


def test_copy_checks_import_collisions_before_changing_module(tmp_path, qt_app):
    from little_tinker_rig.qt.authoring import BlockEditor

    root = user_collection(tmp_path)
    page = BlockEditor(lambda: root, lambda *_: None)
    try:
        page.create(
            "from math import sqrt as show\n@block\ndef calculate(value=4):\n    return show(value)\n"
        )
        page.create(SOURCE)
        assert "def show_2(" in page.code.toPlainText()
        previous = page.code.toPlainText()
        with pytest.raises(ValueError, match="Import names conflict"):
            page.create("from math import cos as show\n" + SOURCE)
        assert page.code.toPlainText() == previous
        page.save()
        for snippet in load_collection(root):
            expanded = instantiate(snippet, {})
            namespace = {}
            exec("\n".join((*expanded.imports, *expanded.helpers)), namespace)
            if snippet.expression:
                assert eval(expanded.source, namespace) == 2
    finally:
        page.flush()
        page.close()


def test_created_name_preview_navigates_to_its_typed_declaration(tmp_path, qt_app):
    from little_tinker_rig.qt.authoring import BlockEditor

    root = user_collection(tmp_path)
    page = BlockEditor(lambda: root, lambda *_: None)
    try:
        page.create(
            '@inline_block(names=("counter",))\ndef create():\n    counter: "int" = 0\n'
        )
        field = next(
            slot
            for slot in page.preview.parameter_slots
            if slot.parameter.name == "counter"
        )
        assert field.match is not None
        page.preview.parameter_clicked.emit(field.parameter.name)
        assert page.code.textCursor().selectedText() == "counter"
        assert page.code.textCursor().blockNumber() == 2
        assert page.code.references
    finally:
        page.close()


def test_invalid_default_and_result_types_are_located_without_execution(tmp_path):
    draft = definition(
        tmp_path, '@block\ndef duration(value: "int[ms]" = 0.5):\n    print(value)\n'
    )
    with pytest.raises(SyntaxError, match="Default") as failure:
        draft.inspect()
    assert failure.value.lineno == 2
    draft.source = '@block\ndef duration() -> "int[ms]":\n    return "wrong"\n'
    with pytest.raises(SyntaxError, match="Expected") as failure:
        draft.inspect()
    assert failure.value.lineno == 3


def test_legacy_draft_levels_migrate_without_losing_invalid_text(tmp_path):
    root = tmp_path / "blocks"
    root.mkdir()
    (root / "collection.toml").write_text(
        '[collection]\nid="old"\nversion="1"\n[levels]\n"actions/show"="standard"\n'
    )
    path = root / "actions.py"
    legacy_source = SOURCE.split("\n", 1)[1]
    path.write_text(legacy_source)
    drafts = root / ".drafts"
    drafts.mkdir()
    (drafts / "actions.py.json").write_text(
        json.dumps(
            {
                "source": "def show(\n",
                "base_source": legacy_source,
                "levels": {"actions/show": "beginner"},
                "base_levels": {"actions/show": "standard"},
            }
        )
    )
    draft = DefinitionDraft(path)
    assert draft.source == "def show(\n"
    draft.persist()
    draft = DefinitionDraft(path)
    draft.source = legacy_source
    draft.save()
    assert load_collection(root)[0].level == "beginner"
    assert "[levels]" not in (root / "collection.toml").read_text()
    assert not draft.draft_path.exists()
