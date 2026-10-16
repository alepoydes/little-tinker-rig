"""Protect edits and command destinations across workspace transitions."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog

from little_tinker_rig.qt.app import Studio

MOTOR = "from pybricks.pupdevices import Motor\nfrom pybricks.parameters import Port\nmotor = Motor(Port.A)\nmotor.run(500)\n"
CTRL = Qt.KeyboardModifier.ControlModifier


@pytest.fixture
def windows(tmp_path, qt_app):
    opened = []

    def create(source="x = 1\n"):
        path = tmp_path / f"program_{len(opened)}.py"
        path.write_text(source, encoding="utf-8")
        window = Studio(path)
        window.confirm_close = lambda *_: True
        window.show()
        qt_app.processEvents()
        opened.append(window)
        return window

    yield create
    for window in opened:
        window.close()
        window.deleteLater()


def parameter(window, name, text, *, view=None):
    view = view or window.source
    slot = next(s for s in view.parameter_slots if s.parameter.name == name)
    view.reveal(slot.span.start)
    QApplication.processEvents()
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=view.parameter_rect(slot).center().toPoint(),
    )
    field = view.parameter_editor.line_edit
    field.selectAll()
    QTest.keyClicks(field, text)
    return field


def test_pending_parameters_commit_before_blur_save_and_run(windows, monkeypatch):
    window = windows(MOTOR)
    parameter(window, "name", "wheel")
    QTest.mouseClick(window.search, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert "wheel.run(500)" in window.document_page.text
    assert "motor.run" not in window.document_page.text
    field = parameter(window, "speed", "900")
    QTest.keyClick(field, Qt.Key.Key_S, CTRL)
    assert "wheel.run(900)" in window.session.project.path.read_text()
    parameter(window, "speed", "700")
    executed = []
    monkeypatch.setattr(
        window,
        "_robot",
        lambda: SimpleNamespace(
            run_file=lambda path: executed.append(path.read_text())
        ),
    )
    window.run_hub()
    assert "wheel.run(700)" in executed[0]
    field = parameter(window, "speed", "700 +")
    QTest.keyClick(field, Qt.Key.Key_S, CTRL)
    window.run_hub()
    window.change_editor(1)
    assert len(executed) == 1
    assert window.source.parameter_editor.error
    assert window.source.parameter_editor.line_edit.text() == "700 +"
    assert not window.code_active
    assert "wheel.run(700)" in window.session.project.path.read_text()
    QTest.keyClick(field, Qt.Key.Key_Escape)


def test_invalid_parameter_blocks_tab_change_without_losing_draft(windows, tmp_path):
    window = windows(MOTOR)
    original = window.document_page
    field = parameter(window, "speed", "1 +")
    other = tmp_path / "other.py"
    other.write_text("other = 1\n")
    window.open_document(other)
    assert window.document_page is original
    assert field.text() == "1 +"
    QTest.keyClick(field, Qt.Key.Key_Escape)
    window.open_document(other)
    assert window.session.project.path == other


def test_python_undo_survives_mode_changes_and_tracks_block_edits(windows):
    window = windows()
    window.change_editor(1)
    window.code.moveCursor(QTextCursor.MoveOperation.End)
    window.code.insertPlainText("y = 2\n")
    assert window.statusBar().currentMessage() == "Python · changes not checked"
    window.change_editor(0)
    assert "warnings: 0" in window.statusBar().currentMessage()
    window.change_editor(1)
    QTest.keyClick(window.code, Qt.Key.Key_Z, CTRL)
    assert window.document_page.text == "x = 1\n"
    QTest.keyClick(window.code, Qt.Key.Key_Z, CTRL | Qt.KeyboardModifier.ShiftModifier)
    assert window.document_page.text == "x = 1\ny = 2\n"
    window.change_editor(0)
    window.session.editor.commit("x = 3\ny = 2\n")
    window.refresh_views()
    window.change_editor(1)
    QTest.keyClick(window.code, Qt.Key.Key_Z, CTRL)
    assert window.document_page.text == "x = 1\ny = 2\n"


def test_scratch_dock_cannot_hide_an_invalid_parameter(windows):
    window = windows()
    window.session.set_scratch(None, MOTOR)
    window.refresh_views()
    window.scratch_dock.show()
    cell = window.scratch.cells[0]
    field = parameter(window, "speed", "1 +", view=cell.source)
    window.scratch_dock.close()
    QApplication.processEvents()
    assert window.scratch_dock.isVisible()
    assert field.isVisible() and field.text() == "1 +"
    QTest.keyClick(field, Qt.Key.Key_Escape)
    window.scratch_dock.close()
    assert not window.scratch_dock.isVisible()


def test_scratch_commands_keep_their_owner_and_help_cannot_undo(windows):
    window = windows()
    window.session.set_scratch(None, "scratch_value=2\n")
    window.refresh_views()
    window.scratch_dock.show()
    cell = window.scratch.cells[0]
    QTest.mouseClick(cell.code_button, Qt.MouseButton.LeftButton)
    cell.code.setFocus()
    QTest.keyClick(cell.code, Qt.Key.Key_L, CTRL | Qt.KeyboardModifier.AltModifier)
    assert cell.text == "scratch_value = 2\n"
    QTest.keyClick(cell.code, Qt.Key.Key_F, CTRL)
    assert cell.finder.isVisible() and not window.document_page.finder.isVisible()
    QTest.keyClicks(cell.find_bar, "scratch_value")
    assert cell.code.textCursor().selectedText() == "scratch_value"
    QTest.keyClick(cell.find_bar, Qt.Key.Key_Escape)
    assert not cell.finder.isVisible()
    cell.code.insertPlainText("unfinished +")
    draft = cell.text
    window.search.setFocus()
    with pytest.raises(ValueError, match="Switch this editor to Blocks"):
        window.insert_snippet("python/basics/display")
    assert cell.text == draft
    cell.code.undo()
    QTest.keyClick(cell.code, Qt.Key.Key_1, CTRL | Qt.KeyboardModifier.AltModifier)
    assert not cell.code_active
    assert window.document_page.text == "x = 1\n"
    before = window.session.document.state
    window.set_mode(2)
    assert not window.undo_action.isEnabled()
    window.undo()
    assert window.session.document.state is before
    window.show_find()
    assert window.help_page.search.hasFocus()


def test_find_preserves_position_on_miss_and_catalog_accepts_enter(windows):
    from little_tinker_rig.qt.library import IDENTITY

    window = windows("print(1)\nprint(2)\n")
    window.change_editor(1)
    window.show_find()
    find = window.document_page.finder
    find.query.setText("print")
    first = window.code.textCursor().selectionStart()
    QTest.keyClick(find.query, Qt.Key.Key_Return)
    assert window.code.textCursor().selectionStart() > first
    QTest.keyClick(find.query, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert window.code.textCursor().selectionStart() == first
    find.query.setText("does_not_exist")
    assert find.status.text() == "Not found"
    assert window.code.textCursor().selectionStart() == first
    QTest.keyClick(find.query, Qt.Key.Key_Escape)
    assert not find.isVisible()
    window.change_editor(0)
    window.search.setText("print")
    row = next(
        r
        for r in window.library.rows.values()
        if r.data(0, IDENTITY) == "python/basics/display"
    )
    window.library.setCurrentItem(row)
    window.library.setFocus()
    QTest.keyClick(window.library, Qt.Key.Key_Return)
    assert window.document_page.text.count("print(") == 3


@pytest.mark.parametrize("choice", ["Reload from disk", "Save a copy…", "Cancel"])
def test_save_conflict_has_explicit_non_overwriting_actions(
    windows, tmp_path, monkeypatch, choice
):
    window = windows()
    page = window.document_page
    path = page.session.project.path
    page.session.editor.commit("edited = 2\n")
    path.write_text("external = 3\n")
    copy = tmp_path / "copy.py"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(copy), ""))

    def answer():
        dialog = QApplication.activeModalWidget()
        button = next(
            b for b in dialog.buttons() if b.text().replace("&", "") == choice
        )
        button.click()

    QTimer.singleShot(0, answer)
    assert window.save_document(page) == (choice == "Save a copy…")
    assert path.read_text() == "external = 3\n"
    if choice == "Reload from disk":
        assert page.text == "external = 3\n" and not page.dirty
    else:
        assert page.text == "edited = 2\n"
        assert copy.exists() == (choice == "Save a copy…")
        if copy.exists():
            assert copy.read_text() == page.text


def test_trigger_release_and_focus_loss_stop_motor_commands(qt_app):
    from little_tinker_rig.pybricks.devices import HubInfo
    from little_tinker_rig.qt.controls import ControlsPage

    controls = ControlsPage()
    controls.update_info(
        HubInfo(connected=True, monitoring=True, ports={"A": {"type": "motor"}})
    )
    controls.show()
    qt_app.processEvents()
    commands = []
    controls.drive_requested.connect(commands.append)
    binding = controls.rows["A"][0]
    binding.setCurrentIndex(binding.findData("left_trigger"))
    controls.armed.setChecked(True)
    trigger = controls.controller.triggers[0]
    try:
        trigger.setFocus()
        qt_app.processEvents()
        assert trigger.hasFocus()
        QTest.keyPress(trigger, Qt.Key.Key_PageUp)
        controls.sample()
        assert commands[-1] == (("A", "speed", 50.0),)
        QTest.keyRelease(trigger, Qt.Key.Key_PageUp)
        controls.sample()
        assert commands[-1] == (("A", "speed", 0.0),)
        QTest.keyPress(trigger, Qt.Key.Key_PageUp)
        controls.target.setFocus()
        qt_app.processEvents()
        controls.sample()
        assert commands[-1] == (("A", "speed", 0.0),)
    finally:
        controls.close()
        controls.deleteLater()
