"""Presentation must preserve source, comment ownership and editing coordinates."""

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from pyblocks.core.display import Display
from pyblocks.core.helpers import END, START
from pyblocks.core.parameters import change_parameter
from pyblocks.core.session import Session
from pyblocks.core.snippets import instantiate, load_module
from pyblocks.core.syntax import Syntax
from pyblocks.core.transfer import Transfer
from pyblocks.qt.editor import SourceView
from pyblocks.qt.structure import block_menu

DEFINITION = '''@inline_block(level="beginner", icon="▶", color="action")
def pair(value=3):
    """Show two successive values."""
    # First value.
    print(value)

    # Next value.
    print(value + 1)
'''


def make_session(source=None):
    snippets = load_module(DEFINITION, "test", "1")
    return Session.fragment(
        source or instantiate(snippets[0], {}).source + "\n", snippets
    )


def hover(view, point):
    QApplication.sendEvent(
        view.viewport(),
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(point),
            QPointF(view.viewport().mapToGlobal(point)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )


def test_auto_uses_owned_comments_not_blank_lines_and_never_rewrites_source():
    owner = make_session("print(3)\n\n\nprint(3 + 1)\n")
    state = owner.document.state
    display = Display(owner)
    assert display.blocks[0].effective == "definition"
    assert display.text == "# First value.\nprint(3)\n\n# Next value.\nprint(3 + 1)\n"
    assert owner.document.state is state
    for comment in (
        "# My explanation.\n\nprint(3)\nprint(3 + 1)\n",
        "print(3)  # My explanation.\nprint(3 + 1)\n",
    ):
        owner = make_session(comment)
        display = Display(owner)
        assert display.blocks[0].effective == "source"
        assert display.text == comment
        block = display.blocks[0]
        modes = {(block.match.span.start, block.match.snippet.identity): "definition"}
        assert "My explanation" not in Display(owner, modes.items()).text
        assert owner.document.state.source == comment


def test_comment_ownership_includes_docstrings_trailing_comments_and_blank_lines():
    source = '''# Class explanation.

class Robot:
    """Robot documentation."""
    # Method explanation.
    def run(self):
        """Method documentation."""
        # Action explanation.

        print(1)  # Action result.
        # End of method.

print(2)
'''
    syntax = Syntax(source)
    cls, method = syntax.tree.body[0], syntax.tree.body[0].body[1]
    action = method.body[1]
    owners = {
        source[s.start : s.end]: node for s, node in syntax.comment_owners.items()
    }
    assert owners["# Class explanation."] is cls
    assert owners['"""Robot documentation."""'] is cls
    assert owners["# Method explanation."] is method
    assert owners['"""Method documentation."""'] is method
    assert owners["# Action explanation."] is action
    assert owners["# Action result."] is action
    assert owners["# End of method."] is method
    assert syntax.at(source.index("# Action explanation.")) is action


def test_function_definition_keeps_comments_and_does_not_inline_runtime():
    (snippet,) = load_module(DEFINITION.replace("@inline_block", "@block"), "test", "1")
    expansion = instantiate(snippet, {"value": "next(values)"})
    assert "#" not in expansion.source
    assert "# First value." in expansion.helpers[0]
    assert '"""Show two successive values."""' in expansion.helpers[0]
    namespace = {"values": iter([5, 100]), "print": lambda value: output.append(value)}
    output = []
    exec("\n".join((*expansion.helpers, expansion.source)), namespace)
    assert output == [5, 6]
    assert next(namespace["values"]) == 100
    owner = Session.fragment(expansion.source + "\n", (snippet,))
    display = Display(owner)
    assert display.text == expansion.source + "\n"
    assert owner.document.state.source == expansion.source + "\n"


def test_instances_choose_independently_and_function_bodies_stay_in_managed_source():
    owner = make_session(
        "# My pair.\nprint(3)\nprint(3 + 1)\nprint(8)\n\nprint(8 + 1)\n"
    )
    display = Display(owner)
    assert [b.effective for b in display.blocks] == ["source", "definition"]
    assert display.text.count("# My pair.") == 1
    assert display.text.count("# First value.") == 1
    (snippet,) = load_module(DEFINITION.replace("@inline_block", "@block"), "test", "1")
    expansion = instantiate(snippet, {})
    saved = expansion.helpers[0].replace("# First value.", "# Saved explanation.")
    source = START + "\n" + saved + "\n" + END + "\n" + expansion.source + "\n"
    owner = Session.fragment(source, (snippet,))
    display = Display(owner)
    assert display.text == "pair(3)\n"
    assert "# First value." not in display.text
    assert "def pair(" not in display.text
    assert owner.document.state.source == source


def test_expression_function_shows_the_real_call_with_editable_arguments(qt_app):
    (snippet,) = load_module(
        '''@block
def double(value=3):
    """Double a value."""
    # Calculate a result without changing the caller.
    return value * 2
''',
        "test",
        "1",
    )
    call = instantiate(snippet, {}).source
    owner = Session.fragment("result = " + call + "\nprint(result)\n", (snippet,))
    view = SourceView(owner)
    view.resize(1000, 600)
    view.show()
    qt_app.processEvents()
    try:
        block = view.display.blocks[0]
        assert block.preview is None
        assert view.mode_rect(block) is None
        assert (
            view.toPlainText()
            == owner.document.state.source
            == "result = double(3)\nprint(result)\n"
        )
        slot = next(p for p in view.parameter_slots if p.parameter.name == "value")
        point = view.parameter_rect(slot).center().toPoint()
        assert view.parameter_at(point) is slot
        hover(view, point)
        assert view.hover == block.match.span
        opened = []
        view.definition_requested.connect(opened.append)
        menu = block_menu(view, point)
        next(a for a in menu.actions() if a.text() == "Open definition").trigger()
        assert opened == [snippet]
        menu.deleteLater()
        change_parameter(owner, slot, "8")
        view.refresh_source()
        assert (
            view.toPlainText()
            == owner.document.state.source
            == "result = double(8)\nprint(result)\n"
        )
    finally:
        view.close()


@pytest.mark.parametrize("mode", ["auto", "source", "definition"])
def test_function_calls_preserve_source_comments_and_layout_in_every_mode(mode):
    (snippet,) = load_module(DEFINITION.replace("@inline_block", "@block"), "test", "1")
    source = "# My action.\npair(\n    3,  # chosen value\n)\n\npair(8)\n"
    owner = Session.fragment(source, (snippet,))
    state = owner.document.state
    modes = {(m.span.start, m.snippet.identity): mode for m in owner.matches}
    display = Display(owner, modes.items())
    assert len(display.blocks) == 2
    assert display.text == source
    assert owner.document.state is state
    assert all(b.preview is None for b in display.blocks)


def test_function_call_retains_enclosing_indentation_colors(qt_app):
    (snippet,) = load_module(DEFINITION.replace("@inline_block", "@block"), "test", "1")
    call = instantiate(snippet, {}).source
    owner = Session.fragment("while False:\n    " + call + "\n", (snippet,))
    view = SourceView(owner)
    view.resize(900, 650)
    view.show()
    qt_app.processEvents()
    view.pulse.stop()
    view.intensity = 1
    owner.editor.selection = owner.document.syntax.tree
    view.hover = None
    try:
        block = view.display.blocks[0]
        first, _ = view.display.position(block.shown.start)
        last, _ = view.display.position(block.shown.end - 1)
        image = view.viewport().grab().toImage()
        expected = image.pixelColor(8, round(view._rect(1, 0).top()) + 4)
        for row in range(first, last + 1):
            assert (
                image.pixelColor(8, round(view._display_rect(row, 0).top()) + 4)
                == expected
            )
    finally:
        view.close()


def test_switching_and_parameter_edits_preserve_modes_and_highlight_whole_block(qt_app):
    owner = make_session("print(3)\nprint(3 + 1)\nprint(99)\n")
    view = SourceView(owner)
    view.resize(900, 650)
    view.show()
    qt_app.processEvents()
    view.pulse.stop()
    try:
        state = owner.document.state
        block = view.display.blocks[0]
        menu = view.display_menu(block)
        assert [a.text() for a in menu.actions()] == ["Auto", "Source", "Definition"]
        menu.actions()[1].trigger()
        assert view.toPlainText() == state.source
        assert owner.document.state is state
        assert view.mode_rect(view.display.blocks[0]) is not None
        menu.deleteLater()
        view.set_display_mode(view.display.blocks[0], "definition")
        slot = view.parameter_slots[0]
        point = view.parameter_rect(slot).center().toPoint()
        assert view.parameter_at(point) is slot
        change_parameter(owner, slot, "8")
        view.refresh_source()
        assert view.display.blocks[0].mode == "definition"
        assert "print(8)" in owner.document.state.source
        assert "# First value." in view.toPlainText()
        assert "#" not in owner.document.state.source
        owner.editor.selection = owner.document.syntax.tree.body[0]
        transfer = Transfer.capture(owner)
        text = view.toPlainText()
        view.show_drag_origin(transfer)
        assert view.origin_rect() is not None
        assert sum(b.isVisible() for b, *_ in view.origin_blocks) == 1
        view.hide_drag_origin()
        assert view.toPlainText() == text
        assert "#" not in transfer.text
        owner.editor.selection = owner.document.syntax.tree
        view.hover = None
        baseline = view.viewport().grab().toImage()
        block = view.display.blocks[0]
        first, _ = view.display.position(block.shown.start)
        last, _ = view.display.position(block.shown.end - 1)
        probe = view._display_rect(first, 0).topLeft().toPoint()
        probe.setX(700)
        probe.setY(probe.y() + 4)
        for row in range(first, last + 1):
            point = view._display_rect(row, 0).center().toPoint()
            hover(view, point)
            assert view.hover == block.match.span
            assert baseline.pixelColor(
                probe
            ) != view.viewport().grab().toImage().pixelColor(probe)
        view.set_display_mode(block, "source")
        owner.editor.selection = owner.document.syntax.at(owner.matches[0].span.start)
        owner.toggle_expansion()
        view.refresh_source()
        hover(view, view._rect(2, 0).center().toPoint())
        assert (
            view.hover
            == owner.document.syntax.spans[owner.document.syntax.tree.body[1]]
        )
    finally:
        view.close()
