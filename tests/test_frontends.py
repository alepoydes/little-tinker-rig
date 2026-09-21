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
    assert window.help_page.isVisible()
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


def test_qt_python_draft_save_format_undo_and_native_cut(tmp_path, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest

    from pyblocks.qt.app import Studio

    path = tmp_path / "draft.py"
    path.write_text("value =\n")
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    assert window.code_active and window.code.toPlainText() == "value =\n"
    with pytest.raises(SyntaxError):
        window.save()
    assert path.read_text() == "value =\n"
    assert window.session.document.state.source == ""
    window.code.setPlainText("value=  42\nprint(value)")
    window.save()
    assert path.read_text() == "value = 42\nprint(value)\n"
    window.code.undo()
    assert window.code.toPlainText() == "value=  42\nprint(value)"
    window.code.redo()
    cursor = window.code.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    cursor.select(QTextCursor.SelectionType.LineUnderCursor)
    window.code.setTextCursor(cursor)
    selected = cursor.selectedText()
    QTest.keyClick(window.code, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
    assert selected not in window.code.toPlainText()
    assert not window.session.document.state.scratch
    window.code.undo()
    window.editor_tabs.setCurrentIndex(0)
    assert not window.code_active
    assert window.session.project.draft is None
    window.close()


def test_qt_hidden_console_help_links_and_library_colors(tmp_path, qt_app):
    from PySide6.QtCore import QUrl

    from pyblocks.core.presentation import PALETTE, snippet_role
    from pyblocks.qt.app import Studio
    from pyblocks.qt.library import COLOR, IDENTITY, PREVIEW

    path = tmp_path / "program.py"
    path.write_text("print(42)\n")
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    assert not window.console_dock.isVisible()
    window.append_output("Привет, робот!")
    assert window.unread == 1
    assert not window.console_dock.isVisible()
    window.console_button.click()
    assert window.unread == 0
    assert window.console.toPlainText() == "Привет, робот!"
    window.help_page.show_page("INSTALL.md")
    window.help_page.follow_link(QUrl("tutorial/first.md"))
    assert window.help_page.current == "tutorial/first.md"
    window.help_page.back()
    assert window.help_page.current == "INSTALL.md"
    snippets = {s.identity: s for s in window.session.snippets if not s.historical}
    for index in range(window.library.topLevelItemCount()):
        group = window.library.topLevelItem(index)
        for child in range(group.childCount()):
            card = group.child(child)
            snippet = snippets[card.data(0, IDENTITY)]
            assert card.data(0, COLOR) == PALETTE[snippet_role(snippet)]
            assert ast.parse(card.data(0, PREVIEW))
    window.close()


def qt_wait(predicate):
    import time

    from PySide6.QtTest import QTest

    deadline = time.monotonic() + 6
    while not predicate():
        assert time.monotonic() < deadline, "GUI did not reach expected state"
        QTest.qWait(20)


@pytest.mark.parametrize(
    "model, ports", [("inventor", "ABCDEF"), ("boost", "ABCD"), ("technic", "ABCD")]
)
def test_qt_virtual_hub_manual_controls_and_disconnect(tmp_path, qt_app, model, ports):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from pyblocks.qt.app import Studio

    path = tmp_path / "robot.py"
    path.write_text('print("ready")\n')
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    try:
        robot = window._robot()
        robot.connect_hub(transport="virtual", model=model)
        qt_wait(lambda: window.hub_info.monitoring and not window.hub_is_busy)
        assert set(window.hub_info.ports) == set(ports)
        window.set_mode(1)
        a_source, _, a_scale, _, _ = window.controls.rows["A"]
        a_source.setCurrentIndex(a_source.findData("left_y"))
        a_scale.setValue(200)
        b_source, b_mode, _, _, _ = window.controls.rows["B"]
        b_source.setCurrentIndex(b_source.findData("right_trigger"))
        b_mode.setCurrentIndex(b_mode.findData("servo"))
        window.controls.armed.setChecked(True)
        stick = window.controls.controller.left
        stick.setFocus()
        QTest.keyPress(stick, Qt.Key.Key_W)
        window.controls.controller.triggers[1].setValue(100)
        qt_wait(
            lambda: window.hub_info.ports["A"]["angle"] > 10
            and window.hub_info.ports["B"]["angle"] == 90
        )
        QTest.keyRelease(stick, Qt.Key.Key_W)
        qt_wait(lambda: window.hub_info.ports["A"]["speed"] == 0)
        window.set_mode(2)
        assert not window.controls.armed.isChecked()
        assert window.controls.controller.state().right_trigger == 0
        process = robot.connection.process
        window.disconnect_hub()
        qt_wait(lambda: not window.hub_info.connected and not window.hub_is_busy)
        assert process.returncode is not None
    finally:
        window.close()
    assert not robot.thread.is_alive()


def test_qt_controller_mirrors_physical_state_and_stops_on_disconnect(qt_app):
    from pyblocks.pybricks.control import ControlState
    from pyblocks.pybricks.devices import HubInfo
    from pyblocks.qt.controls import ControlsPage

    class Gamepad:
        attached = True
        closed = False

        def read(self):
            if not self.attached:
                raise ValueError("Controller disconnected")
            return ControlState(0.5, -1, buttons=5, left_trigger=0.25, right_trigger=1)

        def close(self):
            self.closed = True

    page = ControlsPage()
    gamepad = Gamepad()
    page.gamepad = gamepad
    # Checking the already-provided physical input must not initialize SDL.
    page.physical.blockSignals(True)
    page.physical.setChecked(True)
    page.physical.blockSignals(False)
    page.update_info(
        HubInfo(connected=True, monitoring=True, ports={"A": {"type": "motor"}})
    )
    source = page.rows["A"][0]
    source.setCurrentIndex(source.findData("left_y"))
    commands = []
    page.drive_requested.connect(commands.append)
    page.armed.setChecked(True)
    page.sample()
    assert page.controller.state() == gamepad.read()
    assert commands[-1] == (("A", "speed", -500),)
    gamepad.attached = False
    page.sample()
    assert not page.armed.isChecked() and not page.physical.isChecked()
    assert gamepad.closed
    assert commands[-1] == ()
    assert page.controller.state() == ControlState()
    page.close()


def test_qt_interrupts_pending_connection_before_disconnect(qt_app, monkeypatch):
    import asyncio
    from threading import Event

    from pyblocks.qt.robot import Robot

    entered, released = Event(), Event()

    class Connection:
        connected = False

        def __init__(self, *args, **kwargs):
            pass

        async def connect(self, *args):
            entered.set()
            try:
                await asyncio.sleep(30)
                self.connected = True
            finally:
                released.set()

        async def disconnect(self):
            assert released.is_set()
            self.connected = False

    monkeypatch.setattr("pyblocks.qt.robot.VirtualConnection", Connection)
    robot = Robot()
    try:
        future = robot.connect_hub()
        qt_wait(entered.is_set)
        disconnected = robot.disconnect_hub()
        qt_wait(disconnected.done)
        disconnected.result()
        assert future.cancelled()
        assert released.is_set() and not robot.connection.connected
    finally:
        robot.close()
    assert not robot.thread.is_alive()
