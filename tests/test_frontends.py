import ast
import os

import pytest


@pytest.mark.asyncio
async def test_tui_edit_validation_and_library(tmp_path):
    pytest.importorskip("textual")
    from textual.widgets import TextArea

    from pyblocks.tui.app import EditDialog, Studio

    app = Studio(tmp_path / "main.py")
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.query_one("#library").option_count >= 10
        await pilot.press("f2")
        assert isinstance(app.screen, EditDialog)
        app.screen.query_one("#text", TextArea).load_text("x =")
        app.screen.action_apply()
        assert isinstance(app.screen, EditDialog)
        assert app.session.document.state.source == ""
        app.screen.query_one("#text", TextArea).load_text("value = 3")
        app.screen.action_apply()
        await pilot.pause()
        assert app.session.document.state.source == "value = 3\n"
        app.action_undo()
        assert app.session.document.state.source == ""


@pytest.fixture(scope="module")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_qt_selection_unicode_and_draft_validation(tmp_path, qt_app):
    from pyblocks.qt.app import Studio
    from pyblocks.qt.dialogs import EditDialog
    from pyblocks.qt.editor import qt_offset, source_offset

    app = qt_app
    path = tmp_path / "main.py"
    path.write_text('name = "😀ёж"\nprint(name)\n')
    window = Studio(path)
    window.show()
    app.processEvents()
    source = window.session.document.state.source
    for offset in range(len(source) + 1):
        assert source_offset(source, qt_offset(source, offset)) == offset
    dialog = EditDialog(window, "Edit", window.session.edit_python, text="x =")
    before = window.session.document.state
    dialog.apply()
    assert dialog.error.text()
    assert window.session.document.state == before
    window.show_help()
    app.processEvents()
    assert window.help_dock.isVisible()
    window.hide()


def test_qt_drag_uses_core_move_and_fold_is_reversible(tmp_path, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest

    from pyblocks.qt.app import Studio

    path = tmp_path / "main.py"
    path.write_text('print("first")\nx = 1\nprint("last")\n')
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    view = window.source
    first = QTextCursor(view.document().firstBlock())
    last = QTextCursor(view.document().lastBlock())
    start, end = view.cursorRect(first).center(), view.cursorRect(last).center()
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(view.viewport(), end, 40)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    qt_app.processEvents()
    assert (
        window.session.document.state.source == 'x = 1\nprint("last")\nprint("first")\n'
    )
    window.session.editor.selection = window.session.document.syntax.tree
    view.fold_selection()
    QTest.qWait(180)
    assert not view.document().findBlockByNumber(1).isVisible()
    view.fold_selection()
    QTest.qWait(180)
    assert view.document().findBlockByNumber(1).isVisible()
    window.hide()


@pytest.mark.asyncio
async def test_tui_refresh_keeps_selection_and_can_discard_on_quit(tmp_path):
    pytest.importorskip("textual")
    from pyblocks.tui.app import QuitDialog, Studio

    path = tmp_path / "main.py"
    path.write_text("first = 1\nsecond = 2\n")
    app = Studio(path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("down")
        selected = app.session.editor.selection
        app.refresh_views()
        await pilot.pause()
        assert app.session.editor.selection is selected
        app.session.editor.commit("changed = 3\n")
        await pilot.press("ctrl+q")
        assert isinstance(app.screen, QuitDialog)
        await pilot.click("#discard")
    assert path.read_text() == "first = 1\nsecond = 2\n"


@pytest.mark.asyncio
async def test_tui_keyboard_can_edit_a_second_operand(tmp_path):
    pytest.importorskip("textual")
    from textual.widgets import TextArea

    from pyblocks.tui.app import Studio

    path = tmp_path / "main.py"
    path.write_text("print(2 + 3)\n")
    app = Studio(path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+e", "alt+down", "alt+right", "alt+down", "f2")
        field = app.screen.query_one("#text", TextArea)
        assert field.text == "3"
        field.load_text("10")
        app.screen.action_apply()
        assert ast.dump(ast.parse(app.session.document.state.source)) == ast.dump(
            ast.parse("print(2 + 10)")
        )
