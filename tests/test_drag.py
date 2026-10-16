import ast
from unittest.mock import patch

import pytest

from little_tinker_rig.core import edit
from little_tinker_rig.core.session import Session
from little_tinker_rig.core.snippets import builtin_snippets
from little_tinker_rig.core.transfer import Transfer


def view_for(qt_app, source):
    from little_tinker_rig.qt.editor import SourceView

    view = SourceView(Session.fragment(source, builtin_snippets()))
    view.resize(900, 650)
    view.show()
    qt_app.processEvents()
    return view


def enter(view, name="python/basics/display"):
    from PySide6.QtCore import QMimeData, QPoint, Qt
    from PySide6.QtGui import QDragEnterEvent

    data = QMimeData()
    data.setData("application/x-little-tinker-rig-snippet", name.encode())
    args = (
        Qt.DropAction.CopyAction,
        data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    event = QDragEnterEvent(QPoint(300, 50), *args)
    view.dragEnterEvent(event)
    assert event.isAccepted()
    return args


def hover(qt_app, view, args, point):
    from PySide6.QtGui import QDragMoveEvent

    event = QDragMoveEvent(point, *args)
    view.dragMoveEvent(event)
    qt_app.processEvents()
    return event


@pytest.mark.parametrize("count", [0, 150])
def test_insert_rows_preserve_pointer_anchor_at_both_halves_and_document_edges(
    qt_app, count
):
    from PySide6.QtCore import QPoint

    view = view_for(
        qt_app, "print(1)\nwhile True:\n    print(2)\nprint(3)\n" + "print(4)\n" * count
    )
    try:
        args = enter(view)
        tree = view.session.document.syntax.tree
        original = view.session.document.state
        for line, half in ((2, 1), (2, -1), (3, 1), (1, -1), (4, -1)):
            rect = view._rect(line, 0)
            point = QPoint(500, round(rect.center().y()) + half)
            expected = view.pointer_target(point)
            assert expected is not None
            for _ in range(3):
                assert hover(qt_app, view, args, point).isAccepted()
                assert view.drop_target == expected
                assert view._rect(line, 0).y() == rect.y()
                assert view.target_coordinates(point)[0] == line
            if line == 2 and half == 1:
                assert expected.suite.owner is tree.body[1] and expected.index == 0
        assert view.session.document.state is original
        assert not view.session.document.can_undo
    finally:
        view.dragLeaveEvent(None)
        view.close()


def test_escape_removes_projection_and_held_pointer_cannot_restart_or_commit(
    tmp_path, qt_app
):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt import drag

    view = view_for(qt_app, "while True:\n    print(1)\n    print(2)\nprint(3)\n")
    try:
        original = view.session.document.state
        point = view._rect(1, 0).center().toPoint()
        QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseMove(view.viewport(), point + QPoint(25, 3))
        qt_app.processEvents()
        assert drag._active is not None
        assert view.origin_span is not None
        assert not view.document().findBlockByNumber(1).isVisible()
        assert not view.document().findBlockByNumber(2).isVisible()
        assert view.document().findBlockByNumber(0).isVisible()
        assert view.session.document.state is original
        assert drag._active.preview.height() <= (view.fontMetrics().height() + 3) * 4
        QTest.keyClick(view, Qt.Key.Key_Escape)
        QTest.mouseMove(view.viewport(), point + QPoint(25, 100))
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert drag._active is None and view.origin_span is None
        assert view.session.document.state is original
        assert not view.session.document.can_undo
        assert all(view.document().findBlockByNumber(i).isVisible() for i in range(4))
    finally:
        drag.cancel_drag()
        view.close()


def test_return_to_origin_has_no_undo_and_drop_commits_once(qt_app):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QCursor

    from little_tinker_rig.qt.drag import drag_block

    view = view_for(qt_app, "print(1)\nwhile True:\n    print(2)\nprint(3)\n")
    try:
        original = view.session.document.state
        view.session.editor.selection = view.session.document.syntax.tree.body[0]
        QCursor.setPos(view.viewport().mapToGlobal(view._rect(1, 0).center().toPoint()))
        gesture = drag_block(view, Transfer.capture(view.session))
        gesture.move(view.viewport().mapToGlobal(view.origin_rect().center().toPoint()))
        assert gesture.accepted and view.drop_origin
        gesture.finish(True)
        assert (
            view.session.document.state is original
            and not view.session.document.can_undo
        )
        gesture = drag_block(view, Transfer.capture(view.session))
        rect = view._rect(2, 0)
        gesture.move(
            view.viewport().mapToGlobal(QPoint(500, round(rect.center().y()) + 2))
        )
        assert gesture.accepted
        gesture.finish(True)
        assert view.session.document.state.source.startswith(
            "while True:\n    print(1)\n    print(2)"
        )
        view.session.editor.undo()
        assert (
            view.session.document.state is original
            and not view.session.document.can_undo
        )
    finally:
        from little_tinker_rig.qt.drag import cancel_drag

        cancel_drag()
        view.close()


@pytest.mark.parametrize("scratch", [False, True])
@pytest.mark.parametrize(
    "source",
    [
        "while True:\n    print(2)\n",
        "while True:\n    if True:\n        print(1)\n        print(2)\n",
        "for i in range(2):\n    print(1)\nelse:\n    print(2)\n",
    ],
)
def test_drag_below_final_compound_leaves_its_body_and_undo_restores_it(
    tmp_path, qt_app, source, scratch
):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QCursor

    from little_tinker_rig.qt.drag import cancel_drag, drag_block
    from little_tinker_rig.qt.scratch import ScratchPane

    owner = Session(tmp_path / "main.py")
    if scratch:
        owner.set_scratch(None, source)
        widget = ScratchPane()
        widget.refresh(owner)
        view = widget.cells[0].source
    else:
        widget = view = view_for(qt_app, source)
        owner = view.session
    widget.resize(900, 650)
    widget.show()
    qt_app.processEvents()
    try:
        original = owner.document.state
        had_undo = owner.document.can_undo
        syntax = view.session.document.syntax
        node = next(
            n
            for n in ast.walk(syntax.tree)
            if isinstance(n, ast.Expr) and ast.unparse(n) == "print(2)"
        )
        view.session.editor.selection = node
        transfer = (
            Transfer.capture(owner, index=0, fragment=view.session)
            if scratch
            else Transfer.capture(owner)
        )
        QCursor.setPos(
            view.viewport().mapToGlobal(view._rect(node.lineno, 0).center().toPoint())
        )
        gesture = drag_block(view, transfer)
        # The empty tail belongs to the program even when the pointer is far
        # to the right of every indentation band. No synthetic sibling is needed.
        tail = view._rect(len(syntax.lines) + 1, 0)
        point = view.viewport().mapToGlobal(QPoint(500, round(tail.center().y())))
        for _ in range(3):
            gesture.move(point)
            assert gesture.accepted
            assert view.drop_target.suite.owner is syntax.tree
            assert view.drop_target.index == len(syntax.tree.body)
            assert owner.document.state is original
        gesture.finish(True)
        result = (
            owner.document.state.scratch[0] if scratch else owner.document.state.source
        )
        tree = ast.parse(result)
        assert len(tree.body) == 2 and ast.unparse(tree.body[-1]) == "print(2)"
        assert not any(
            isinstance(n, ast.Expr) and ast.unparse(n) == "print(2)"
            for n in ast.walk(tree.body[0])
        )
        assert owner.editor.undo()
        assert owner.document.state is original
        assert owner.document.can_undo == had_undo
    finally:
        cancel_drag()
        widget.close()


def test_incompatible_drop_is_not_offered_and_filled_parameter_is_preserved(
    tmp_path, qt_app
):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QDragEnterEvent

    from little_tinker_rig.qt.drag import BlockMime

    view = view_for(qt_app, "print(1)\nif ...:\n    pass\n")
    try:
        # break is valid only in a loop, never at the closest top-level boundary.
        path = tmp_path / "main.py"
        path.write_text(view.session.document.state.source)
        view.session = Session(path)
        view.session.set_scratch(None, "break\n")
        view.refresh_source()
        data = BlockMime(Transfer.capture(view.session, index=0))
        args = (
            Qt.DropAction.MoveAction,
            data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        view.dragEnterEvent(QDragEnterEvent(QPoint(500, 40), *args))
        point = QPoint(500, round(view._rect(1, 0).center().y()) + 1)
        assert not hover(qt_app, view, args, point).isAccepted()
        assert view.drop_target is None and view.drop_gap is None
        view.dragLeaveEvent(None)
        args = enter(view, "python/basics/equal")
        occupied = next(
            s
            for s in view.parameter_slots
            if view.session.document.syntax.source[s.span.start : s.span.end] == "1"
        )
        assert not hover(
            qt_app, view, args, view.parameter_rect(occupied).center().toPoint()
        ).isAccepted()
        empty = next(
            s
            for s in view.parameter_slots
            if view.session.document.syntax.source[s.span.start : s.span.end] == "..."
        )
        assert hover(
            qt_app, view, args, view.parameter_rect(empty).center().toPoint()
        ).isAccepted()
        assert isinstance(view.drop_target, ast.Constant)
    finally:
        view.dragLeaveEvent(None)
        view.close()


def test_expression_and_same_fragment_moves_are_one_atomic_edit(tmp_path):
    owner = Session(tmp_path / "main.py")
    owner.set_scratch(None, "print(1 + 2)\nprint(None)\n")
    fragment = Session.fragment(owner.document.state.scratch[0], owner.snippets)
    syntax = fragment.document.syntax
    value, empty = (node.value.args[0] for node in syntax.tree.body)
    original = owner.document.state
    transfer = Transfer.capture(owner, index=0, fragment=fragment, node=value)
    transfer.to_fragment(0, fragment, empty)
    assert owner.document.state.scratch == ("print(...)\nprint(1 + 2)\n",)
    owner.editor.undo()
    assert owner.document.state is original
    syntax = owner.document.syntax
    target = edit.Target(syntax.suites[0], 0)
    owner.set_scratch(None, "print(3)\n")
    with pytest.raises(ValueError, match="changed"):
        transfer.to_program(target)


def test_standalone_expression_transfers_the_whole_match_with_comments(tmp_path):
    from little_tinker_rig.core.snippets import load_module

    snippets = load_module(
        "@inline_block\ndef total(left=1, right=2):\n    return left + right\n",
        "test",
        "1",
    )
    owner = Session(tmp_path / "main.py")
    owner.set_snippets(snippets)
    owner.editor.commit("print(0)\n# addition\n1 + 2  # details\nresult = 3 * None\n")
    original = owner.document.state
    syntax = owner.document.syntax
    # The block title selects the complete expression; operands are separate inputs.
    owner.editor.selection = syntax.tree.body[1].value
    transfer = Transfer.capture(owner)
    assert isinstance(transfer.nodes, ast.BinOp)
    assert "1 + 2" in transfer.text and "# addition" in transfer.text
    transfer.to_scratch(0)
    assert owner.document.state.source == "print(0)\nresult = 3 * None\n"
    assert owner.document.state.scratch == ("# addition\n1 + 2  # details\n",)
    owner.editor.undo()
    assert owner.document.state is original
    syntax = owner.document.syntax
    owner.editor.selection = syntax.tree.body[1].value
    transfer = Transfer.capture(owner)
    transfer.to_program(syntax.tree.body[-1].value.right)
    assert ast.dump(owner.document.syntax.tree) == ast.dump(
        ast.parse("print(0)\nresult = 3 * (1 + 2)\n")
    )
    assert "# addition" in owner.document.state.source
    assert "# details" in owner.document.state.source
    owner.editor.undo()
    assert owner.document.state is original


def test_old_parenthesized_none_can_be_deleted(tmp_path):
    owner = Session(tmp_path / "main.py")
    owner.editor.commit("(None)\n")
    owner.editor.selection = owner.document.syntax.tree.body[0].value
    owner.editor.commit(owner.extract_selection()[1])
    assert owner.document.state.source == ""


def test_level_filter_combines_search_and_groups_and_persists(tmp_path, qt_app):
    from PySide6.QtWidgets import QMessageBox

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.library import LEVEL

    window = Studio(tmp_path / "main.py")
    try:
        window.level_filter.select("advanced")
        window.search.setText("follow")
        items = window.library.rows.values()
        visible = [item for item in items if not item.isHidden()]
        assert {item.data(0, LEVEL) for item in visible[:2]} == {"beginner", "advanced"}
        assert all(item.data(0, LEVEL) != "expert" for item in visible)
        assert window.settings.value("blockLevel") == "advanced"
        window.search.setText("no such block")
        assert all(
            window.library.topLevelItem(i).isHidden()
            for i in range(window.library.topLevelItemCount())
        )
    finally:
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard
        ):
            window.close()


def test_scratch_insert_marker_preserves_global_pointer_and_cell_geometry(
    tmp_path, qt_app
):
    from PySide6.QtCore import QPoint

    from little_tinker_rig.qt.scratch import ScratchPane

    owner = Session(tmp_path / "main.py")
    owner.set_scratch(None, "print(1)\nwhile True:\n    print(2)\nprint(3)\n")
    pane = ScratchPane()
    pane.refresh(owner)
    pane.resize(700, 750)
    pane.show()
    qt_app.processEvents()
    view = pane.cells[0].source
    try:
        args = enter(view)
        for line, half in ((2, 1), (2, -1), (3, 1), (1, -1), (4, -1)):
            rect = view._rect(line, 0)
            point = view.viewport().mapToGlobal(
                QPoint(500, round(rect.center().y()) + half)
            )
            y = view.viewport().mapToGlobal(rect.topLeft().toPoint()).y()
            expected = view.pointer_target(view.viewport().mapFromGlobal(point))
            for _ in range(3):
                assert hover(
                    qt_app, view, args, view.viewport().mapFromGlobal(point)
                ).isAccepted()
                assert view.drop_target == expected
                assert (
                    view.viewport()
                    .mapToGlobal(view._rect(line, 0).topLeft().toPoint())
                    .y()
                    == y
                )
        view.dragLeaveEvent(None)
        args = enter(pane)
        point = QPoint(3, 20)
        cell_y = pane.cells[0].mapTo(pane.viewport(), QPoint()).y()
        for _ in range(3):
            assert hover(qt_app, pane, args, point).isAccepted()
            assert pane.drop_position == 0
            assert pane.cells[0].mapTo(pane.viewport(), QPoint()).y() == cell_y
        assert len(owner.document.state.scratch) == 1
    finally:
        view.dragLeaveEvent(None)
        pane.dragLeaveEvent(None)
        pane.close()


def test_nested_note_keeps_parent_color_bands_and_comment_prefix(qt_app):
    view = view_for(qt_app, "while True:\n    if True:\n        print(1)\n")
    try:
        view.intensity = 1
        view.hover = None
        view.session.editor.selection = view.session.document.syntax.tree
        image = view.viewport().grab().toImage().scaled(view.viewport().size())
        rect = view.note_rect(3, 0)
        y = round(rect.top()) + 2
        loop = view._rect(3, 0)
        condition = view._rect(3, 4)
        code_y = round(view._rect(3, 0).bottom()) - 2
        for band in (loop, condition):
            x = round(band.left()) + 2
            assert image.pixelColor(x, y) == image.pixelColor(x, code_y)
        assert image.pixelColor(round(rect.right()) - 50, y) == image.pixelColor(
            round(rect.right()) - 50, code_y
        )
        # The comment starts with a visible hash before the enlarged symbol.
        strip = image.copy(
            round(rect.left()), round(rect.top()), 21, round(rect.height())
        )
        assert any(
            strip.pixelColor(x, y).lightness() < 150
            for x in range(strip.width())
            for y in range(strip.height())
        )
    finally:
        view.close()


def test_escape_from_library_does_not_restart_until_a_new_press(qt_app):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt import drag
    from little_tinker_rig.qt.library import Library

    library = Library(builtin_snippets())
    library.topLevelItem(0).setExpanded(True)
    library.resize(450, 600)
    library.show()
    qt_app.processEvents()
    try:
        item = library.topLevelItem(0).child(0)
        point = library.visualItemRect(item).center()
        QTest.mousePress(library.viewport(), Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseMove(library.viewport(), point + QPoint(25, 4))
        qt_app.processEvents()
        assert drag._active is not None
        QTest.keyClick(library, Qt.Key.Key_Escape)
        QTest.mouseMove(library.viewport(), point + QPoint(35, 25))
        QTest.mouseRelease(library.viewport(), Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert drag._active is None
    finally:
        drag.cancel_drag()
        library.close()


def test_whole_unfinished_scratch_cell_is_replaced_by_one_origin_marker(
    tmp_path, qt_app
):
    from PySide6.QtCore import QPoint

    from little_tinker_rig.qt.drag import drag_block
    from little_tinker_rig.qt.scratch import ScratchPane

    owner = Session(tmp_path / "main.py")
    owner.set_scratch(None, "value =\n" * 10)
    original = owner.document.state
    pane = ScratchPane()
    pane.refresh(owner)
    pane.resize(700, 700)
    pane.show()
    qt_app.processEvents()
    try:
        cell = pane.cells[0]
        height = cell.height()
        assert cell.code_active
        gesture = drag_block(cell, Transfer.capture(owner, index=0))
        qt_app.processEvents()
        assert cell.origin_marker.isVisible()
        assert not cell.code.isVisible() and cell.height() < height
        gesture.move(cell.origin_marker.mapToGlobal(QPoint(20, 15)))
        assert gesture.accepted
        gesture.finish(True)
        qt_app.processEvents()
        assert cell.code.isVisible() and not cell.origin_marker.isVisible()
        assert cell.code.toPlainText() == original.scratch[0]
        assert owner.document.state is original
    finally:
        from little_tinker_rig.qt.drag import cancel_drag

        cancel_drag()
        pane.close()


@pytest.mark.parametrize(
    "source, header",
    [
        ("if True:\n    print(1)\nelse:\n    print(2)\n", 3),
        ("if True:\n    print(1)\nelif False:\n    print(2)\n", 3),
        ("try:\n    print(1)\nexcept Exception:\n    print(2)\n", 3),
        ("try:\n    print(1)\nfinally:\n    print(2)\n", 3),
    ],
)
def test_clause_headers_choose_adjacent_body_instead_of_whole_construct(
    qt_app, source, header
):
    from PySide6.QtCore import QPoint

    view = view_for(qt_app, source)
    try:
        args = enter(view)
        for half, existing in ((-1, 1), (1, 2)):
            point = QPoint(500, round(view._rect(header, 0).center().y()) + half)
            assert hover(qt_app, view, args, point).isAccepted()
            target = view.drop_target
            assert ast.unparse(target.suite.statements[0]) == f"print({existing})"
            result = edit.insert(view.session.document.syntax, target, "print(99)")
            compile(result, "<drag>", "exec")
    finally:
        view.dragLeaveEvent(None)
        view.close()
