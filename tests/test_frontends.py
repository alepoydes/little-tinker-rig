import ast

import pytest


def test_qt_selection_unicode_and_draft_validation(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.dialogs import EditDialog
    from little_tinker_rig.qt.editor import qt_offset, source_offset

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

    from little_tinker_rig.qt.app import Studio

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


def test_qt_python_draft_save_format_undo_and_native_cut(tmp_path, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    path = tmp_path / "draft.py"
    path.write_text("value =\n")
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    assert window.code_active and window.code.toPlainText() == "value =\n"
    window.save()
    assert not window.document_page.dirty
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
    window.change_editor(0)
    assert not window.code_active
    assert window.session.project.draft is None
    window.close()


def test_qt_hidden_console_help_links_and_library_colors(tmp_path, qt_app):
    from PySide6.QtCore import QUrl

    from little_tinker_rig.core.presentation import snippet_role
    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.library import COLOR, IDENTITY, PREVIEW

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
    for card in window.library.rows.values():
        snippet = snippets[card.data(0, IDENTITY)]
        assert card.data(0, COLOR) == snippet_role(snippet)
        assert ast.parse(card.data(0, PREVIEW))
    window.close()


def qt_wait(predicate):
    import time

    from PySide6.QtTest import QTest

    deadline = time.monotonic() + 6
    while not predicate():
        assert time.monotonic() < deadline, "GUI did not reach expected state"
        QTest.qWait(20)


@pytest.mark.parametrize("fail", [False, True])
def test_qt_upload_reports_worker_output_progress_and_failure(
    tmp_path, qt_app, monkeypatch, fail
):
    import asyncio
    import sys
    from threading import Event

    from tqdm import tqdm

    from little_tinker_rig.pybricks.devices import HubInfo
    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.console import capture_output

    entered, release = Event(), Event()

    class Connection:
        def __init__(self, output, changed):
            self.output, self.changed = output, changed

        async def connect(self, *args):
            self.changed(HubInfo(connected=True, transport="ble"))

        async def stop(self):
            pass

        async def upload(self, path):
            print("Compiling", path.name)
            with tqdm(total=10, mininterval=0, ncols=40) as progress:
                progress.update(5)
                entered.set()
                while not release.is_set():
                    await asyncio.sleep(0.01)
                if fail:
                    raise OSError("Transfer interrupted")
                progress.update(5)

        async def run(self):
            self.output(b"Hub: \xe2")
            self.output(b"\x82\xac\n")

        async def disconnect(self):
            pass

    monkeypatch.setattr("little_tinker_rig.pybricks.worker.Connection", Connection)
    path = tmp_path / "main.py"
    path.write_text('print("Hub: €")\n')
    window = Studio(path)
    window.show()
    previous = sys.stdout, sys.stderr
    try:
        with capture_output(window.append_output):
            robot = window._robot()
            future = robot.connect_hub()
            qt_wait(lambda: future.done() and not window.hub_is_busy)
            window.upload_hub()
            qt_wait(lambda: entered.is_set() and "50%" in window.console.toPlainText())
            assert window.console_dock.isVisible()
            assert window.hub_progress.isVisible()
            release.set()
            qt_wait(lambda: robot.operation.done() and not window.hub_is_busy)
            if not fail:
                window.run_stored_hub()
                qt_wait(
                    lambda: "Hub: €" in window.console.toPlainText()
                    and not window.hub_is_busy
                )
            assert not window.hub_progress.isVisible()
        assert (sys.stdout, sys.stderr) == previous
        text = window.console.toPlainText()
        assert "Compiling main.py" in text
        assert "Uploading main.py" in text
        assert "\r" not in text and "  0%" not in text
        assert ("Transfer interrupted" if fail else "Program uploaded.") in text
        # A progress redraw split between writes must replace the whole old line.
        window.append_output("long progress line\r")
        window.append_output("done\r\n")
        assert window.console.toPlainText().endswith("done\n")
        assert "long progress line" not in window.console.toPlainText()
    finally:
        release.set()
        window.close()


@pytest.mark.parametrize(
    "model, ports", [("inventor", "ABCDEF"), ("boost", "ABCD"), ("technic", "ABCD")]
)
def test_qt_virtual_hub_manual_controls_and_disconnect(tmp_path, qt_app, model, ports):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

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
    from little_tinker_rig.pybricks.control import ControlState
    from little_tinker_rig.pybricks.devices import HubInfo
    from little_tinker_rig.qt.controls import ControlsPage

    class Gamepad:
        attached = True
        closed = False

        def read(self):
            if not self.attached:
                raise ValueError("Controller disconnected")
            return ControlState(0.5, -1, buttons=5, left_trigger=0.25, right_trigger=1)

        def read_samples(self):
            return (self.read(),)

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

    from little_tinker_rig.qt.robot import Robot

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

    monkeypatch.setattr(
        "little_tinker_rig.pybricks.worker.VirtualConnection", Connection
    )
    robot = Robot()
    try:
        future = robot.connect_hub(transport="virtual")
        qt_wait(entered.is_set)
        transport = robot.connection
        disconnected = robot.disconnect_hub()
        qt_wait(disconnected.done)
        disconnected.result()
        assert future.cancelled()
        assert released.is_set() and not transport.connected
        assert robot.connection is None
    finally:
        robot.close()
    assert not robot.thread.is_alive()


def test_console_line_and_immediate_keyboard_input(qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence, QShortcut
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.console import HubInput

    widget = HubInput()
    received, cancelled = [], []
    widget.sent.connect(received.append)
    shortcut = QShortcut(QKeySequence("Escape"), widget)
    shortcut.activated.connect(lambda: cancelled.append(True))
    widget.show()
    widget.activateWindow()
    widget.field.setFocus()
    qt_app.processEvents()
    try:
        widget.field.setText("hello")
        QTest.keyClick(widget.field, Qt.Key.Key_Return)
        assert received == [b"hello\r"]
        assert not widget.field.text()
        widget.immediate.setChecked(True)
        QTest.keyClicks(widget.field, "qa")
        QTest.keyClick(widget.field, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert received == [b"hello\r", b"q", b"a", b"\x03"]
        QTest.keyClick(widget.field, Qt.Key.Key_Escape)
        assert not widget.immediate.isChecked()
        assert not cancelled
        assert not widget.field.text()
    finally:
        widget.close()


def test_hub_button_cancels_connection_then_disconnects_instead_of_opening_monitor(
    tmp_path, qt_app, monkeypatch
):
    import asyncio
    from threading import Event

    from little_tinker_rig.pybricks.devices import HubInfo
    from little_tinker_rig.qt.app import Studio

    entered, released = Event(), Event()

    class Connection:
        def __init__(self, output, changed, **kwargs):
            self.changed = changed

        async def connect(self, *args):
            entered.set()
            try:
                await asyncio.sleep(30)
            finally:
                # A late transport callback must not resurrect a cancelled link.
                self.changed(HubInfo(connected=True, name="Late"))
                await asyncio.sleep(0.05)
                released.set()

        async def disconnect(self):
            pass

    monkeypatch.setattr(
        "little_tinker_rig.pybricks.worker.VirtualConnection", Connection
    )
    path = tmp_path / "main.py"
    path.write_text("print(1)\n")
    window = Studio(path)
    try:
        robot = window._robot()
        future = robot.connect_hub(transport="virtual")
        qt_wait(entered.is_set)
        qt_app.processEvents()
        assert window.hub_button.isEnabled()
        assert window.hub_button.text() == "Cancel connection"
        assert window.device_panel.disconnect.isEnabled()
        window.hub_button.click()
        assert not window.hub_button.isEnabled()
        qt_wait(
            lambda: not window.hub_info.connection_action and not window.hub_is_busy
        )
        assert future.cancelled() and released.is_set()
        assert not window.hub_info.connected
        assert window.hub_button.isEnabled() and not window.hub_is_busy
        disconnected = []
        monkeypatch.setattr(robot, "disconnect_hub", lambda: disconnected.append(True))
        window.update_hub(HubInfo(connected=True, name="Classroom"))
        window.hub_button.click()
        assert disconnected == [True]
    finally:
        robot.worker.close()
        window.robot = None
        window.close()


def test_hub_error_can_be_copied_and_opens_offline_usb_help(tmp_path, qt_app):
    from PySide6.QtWidgets import QDialogButtonBox

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.device import ConnectDialog

    path = tmp_path / "main.py"
    path.write_text("print(1)\n")
    window = Studio(path)
    window.show()
    robot = window._robot()
    message = "Could not open USB serial port /dev/ttyACM0.\n\nDetails and command"
    try:
        robot.failed.emit(message)
        assert message in window.console.toPlainText()
        assert window.statusBar().currentMessage() == message.splitlines()[0]
        assert window.copy_error.isVisible()
        assert window.connection_help.isVisible()
        window.copy_error.click()
        assert qt_app.clipboard().text() == message
        window.connection_help.click()
        assert window.help_page.current == "usb.md"
        assert window.help_page.isVisible()
        assert "usermod" in window.help_page.browser.toPlainText()

        # Help is also reachable before attempting a connection.
        window.set_mode(0)
        dialog = ConnectDialog(window)
        dialog.show()
        assert dialog.help_button.isHidden()
        dialog.transport.setCurrentIndex(dialog.transport.findData("usb"))
        assert dialog.help_button.isVisible()
        buttons = dialog.findChild(QDialogButtonBox)
        help_button = next(
            button
            for button in buttons.buttons()
            if buttons.buttonRole(button) == QDialogButtonBox.ButtonRole.HelpRole
        )
        help_button.click()
        assert not dialog.isVisible()
        assert window.help_page.isVisible()
    finally:
        robot.close()
        window.robot = None
        window.close()


def test_connection_dialog_keeps_primary_action_after_language_switch(tmp_path, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog, QPushButton

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.device import ConnectDialog

    window = Studio(tmp_path / "main.py")
    window.confirm_close = lambda *_: True
    window.show()
    try:
        for code, expected in (("en", "Connect"), ("ru", "Подключить")):
            window.change_language(code)
            dialog = ConnectDialog(window, preferred_transport="virtual")
            dialog.show()
            QTest.qWait(60)
            assert dialog.findChild(QPushButton, "dialogPrimary").text() == expected
            assert not dialog.name.isVisible()
            assert dialog.model.isVisible()
            assert dialog.help_button.isHidden()
            dialog.transport.setCurrentIndex(dialog.transport.findData("ble"))
            assert dialog.name.isVisible()
            assert not dialog.model.isVisible()
            assert dialog.name_label.text() == (
                "Bluetooth hub name" if code == "en" else "Имя Bluetooth-хаба"
            )
            assert dialog.name.accessibleName() == dialog.name_label.text()
            assert dialog.name.placeholderText() == (
                "Empty — first available hub"
                if code == "en"
                else "Пусто — первый найденный хаб"
            )
            assert dialog.help_button.isHidden()
            dialog.transport.setCurrentIndex(dialog.transport.findData("usb"))
            assert dialog.name_label.text() == (
                "USB serial port" if code == "en" else "Последовательный USB-порт"
            )
            assert dialog.name.accessibleName() == dialog.name_label.text()
            assert dialog.name.placeholderText() == (
                "Empty — detect a single USB hub"
                if code == "en"
                else "Пусто — найти единственный USB-хаб"
            )
            assert (
                "only one Pybricks USB hub" if code == "en" else "только один USB-хаб"
            ) in dialog.name.toolTip()
            assert dialog.help_button.isVisible()
            dialog.close()
            dialog.deleteLater()
        keyboard_dialog = ConnectDialog(window, preferred_transport="virtual")
        keyboard_dialog.show()
        QTest.keyClick(keyboard_dialog, Qt.Key.Key_Return)
        assert keyboard_dialog.result() == QDialog.DialogCode.Accepted

        window.change_language("en")
        live_dialog = ConnectDialog(window, preferred_transport="usb")
        live_dialog.show()
        window.change_language("ru")
        assert live_dialog.name_label.text() == "Последовательный USB-порт"
        assert live_dialog.name.accessibleName() == live_dialog.name_label.text()
        assert (
            live_dialog.name.placeholderText() == "Пусто — найти единственный USB-хаб"
        )
        live_dialog.transport.setCurrentIndex(live_dialog.transport.findData("ble"))
        assert live_dialog.name_label.text() == "Имя Bluetooth-хаба"
        window.change_language("en")
        assert live_dialog.name_label.text() == "Bluetooth hub name"
        assert live_dialog.name.placeholderText() == "Empty — first available hub"
        live_dialog.close()
    finally:
        window.change_language("en")
        window.close()


def test_connection_dialog_remembers_successful_transport_and_virtual_model(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QDialog

    from little_tinker_rig.pybricks.devices import HubInfo
    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.device import ConnectDialog

    choices = []

    def inspect(dialog):
        choices.append((dialog.transport.currentData(), dialog.model.currentData()))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(ConnectDialog, "exec", inspect)
    window = Studio(tmp_path / "main.py")
    window.show()
    try:
        window.open_hub_connection()
        window.update_hub(
            HubInfo(connected=True, transport="usb", connection_action="connecting")
        )
        window.update_hub(HubInfo())
        window.open_hub_connection()
        window.update_hub(HubInfo(connected=True, transport="virtual", model="boost"))
        window.update_hub(HubInfo())
        window.open_hub_connection()
        window.update_hub(HubInfo(connected=True, transport="ble"))
        window.update_hub(HubInfo())
        window.open_hub_connection()
        window.open_hub_connection("virtual")
        assert choices == [
            ("virtual", "inventor"),
            ("virtual", "inventor"),
            ("virtual", "boost"),
            ("ble", "boost"),
            ("virtual", "inventor"),
        ]
    finally:
        window.close()


def test_unlabeled_editor_and_hub_fields_have_localized_accessible_names(
    tmp_path, qt_app
):
    from PySide6.QtWidgets import QComboBox, QLineEdit

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.device import ConnectDialog

    window = Studio(tmp_path / "main.py")
    window.show()
    try:
        window.session.set_scratch(None, "value = 1\n")
        window.scratch.refresh(window.session)
        window.confirm_close = lambda page: True
        for code, names in (
            (
                "en",
                (
                    "Find a block…",
                    "Control target",
                    "Port A: Input",
                    "Port A: Device",
                    "New block type",
                    "Preview view",
                    "Connection",
                    "Program blocks",
                    "Program Python source",
                    "Help document",
                    "Block preview",
                    "Block definition",
                    "Scratch blocks",
                    "Scratch Python source",
                ),
            ),
            (
                "ru",
                (
                    "Найти блок…",
                    "Цель управления",
                    "Порт A: Вход",
                    "Порт A: Устройство",
                    "Тип нового блока",
                    "Вид предпросмотра",
                    "Подключение",
                    "Блоки программы",
                    "Исходный код программы на Python",
                    "Документ справки",
                    "Предпросмотр блока",
                    "Определение блока",
                    "Блоки в черновике",
                    "Исходный код Python в черновике",
                ),
            ),
        ):
            window.change_language(code)
            dialog = ConnectDialog(window)
            try:
                assert (
                    window.search.accessibleName(),
                    window.controls.target.accessibleName(),
                    window.controls.rows["A"][0].accessibleName(),
                    window.device_panel.rows["A"][0].accessibleName(),
                    window.block_editor.starters.accessibleName(),
                    window.block_editor.preview_mode.accessibleName(),
                    dialog.transport.accessibleName(),
                    window.source.accessibleName(),
                    window.code.accessibleName(),
                    window.help_page.browser.accessibleName(),
                    window.block_editor.preview.accessibleName(),
                    window.block_editor.code.accessibleName(),
                    window.scratch.cells[0].source.accessibleName(),
                    window.scratch.cells[0].code.accessibleName(),
                ) == names
                assert window.block_editor.icon.lineEdit().accessibleName() == (
                    "Block icon · stored in the decorator"
                    if code == "en"
                    else "Значок блока · хранится в декораторе"
                )
                assert window.block_editor.color.lineEdit().accessibleName()
                assert dialog.name.accessibleName()
                assert dialog.model.accessibleName()
                assert window.controls.rows["A"][0].itemText(0) == (
                    "Unassigned" if code == "en" else "Не назначен"
                )
                assert window.device_panel.rows["A"][0].itemText(0) == (
                    "Empty" if code == "en" else "Пусто"
                )
                for mode in (0, 1, 2, 3, 5):
                    window.set_mode(mode)
                    unnamed = [
                        widget
                        for kind in (QComboBox, QLineEdit)
                        for widget in window.findChildren(kind)
                        if widget.isVisible() and not widget.accessibleName()
                    ]
                    assert not unnamed, (code, mode, unnamed)
            finally:
                dialog.close()
                dialog.deleteLater()
    finally:
        window.close()
