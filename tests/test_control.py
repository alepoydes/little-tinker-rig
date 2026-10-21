import importlib.util
import sys
import types
from pathlib import Path

import pytest

from little_tinker_rig.pybricks.control import ControlState


@pytest.mark.parametrize("value", [-1, -0.37, 0, 0.59, 1])
def test_controller_frame_roundtrip(value):
    state = ControlState(value, -value, value, -value, 0x8003, 0.25)
    assert len(state.encode()) == 16
    assert ControlState.decode(state.encode()) == state
    assert b"\x03" not in state.encode()


def test_controller_rejects_nonfinite_and_out_of_range():
    for value in (float("nan"), float("inf"), 1.01):
        with pytest.raises(ValueError):
            ControlState(left_x=value)


def test_hub_parser_handles_partial_frames_and_neutralizes_stale_input(monkeypatch):
    buffer = []
    elapsed = [0]

    class Clock:
        def time(self):
            return elapsed[0]

        def reset(self):
            elapsed[0] = 0

    tools = types.ModuleType("pybricks.tools")
    tools.StopWatch = Clock
    tools.read_input_byte = lambda: buffer.pop(0) if buffer else None
    monkeypatch.setitem(sys.modules, "pybricks.tools", tools)
    path = Path(__file__).parents[1] / "little_tinker_rig/pybricks/hub_controller.py"
    spec = importlib.util.spec_from_file_location("test_hub_controller", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    controller = module.Controller()
    state = ControlState(0.5, -1, buttons=3, left_trigger=0.25, right_trigger=1)
    frame = state.encode()
    buffer.extend(frame[:6])
    controller.update()
    assert controller.left_x == 0
    buffer.extend(frame[6:])
    controller.update()
    assert controller.left_x == state.left_x
    assert controller.left_y == state.left_y
    assert controller.buttons == state.buttons
    assert controller.left_trigger == state.left_trigger
    assert controller.right_trigger == state.right_trigger
    elapsed[0] = 501
    controller.update()
    assert controller.left_x == controller.left_y == controller.buttons == 0
    assert controller.left_trigger == controller.right_trigger == 0
    buffer.extend(ControlState(buttons=1).encode())
    buffer.extend(ControlState().encode())
    controller.update()
    assert controller.buttons == 1
    controller.update()
    assert controller.buttons == 0


def test_short_screen_button_click_and_key_press_emit_both_edges(qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.pybricks.devices import HubInfo
    from little_tinker_rig.qt.controls import ControlsPage

    page = ControlsPage()
    page.show()
    try:
        page.target.setCurrentIndex(1)
        page.update_info(HubInfo(connected=True, running=True))
        frames = []
        page.input_requested.connect(lambda state: frames.append(state.buttons))
        page.armed.setChecked(True)
        button = page.controller.buttons[0]
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert frames[:2] == [1, 0]
        button.setFocus()
        QTest.keyClick(button, Qt.Key.Key_Space)
        assert frames[2:4] == [1, 0]
    finally:
        page.close()
