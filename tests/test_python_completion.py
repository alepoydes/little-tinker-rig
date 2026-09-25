"""Python assistance follows static scope and never edits a stale revision."""

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QToolTip

from pyblocks.qt.code import CodeEdit
from pyblocks.qt.completion import Suggestions, analyze
from pyblocks.qt.editor import qt_offset


def wait_for(predicate):
    deadline = time.monotonic() + 15
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(0.005)
    assert predicate()


def at_end(editor, source):
    editor.setPlainText(source)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)


def suggestions(source, mode="complete", path=None):
    lines = source.split("\n")
    return analyze(source, path, len(lines), len(lines[-1]), mode)


def test_pybricks_methods_signature_and_static_local_imports(qt_app, tmp_path):
    source = (
        "from pybricks.pupdevices import Motor\n"
        "from pybricks.parameters import Port\n"
        "motor = Motor(Port.A)\n"
    )
    methods = dict(suggestions(source + "motor.run_").words)
    assert {"run_angle", "run_target", "run_time"} <= methods.keys()
    assert methods["run_angle"] == len("run_")
    hint = suggestions(source + "motor.run_angle(100, ", "help")
    assert "rotation_angle" in hint.parameter
    assert "run_angle(" in hint.signature
    assert "angle" in hint.description
    marker = tmp_path / "must-not-execute"
    (tmp_path / "robot.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        "class Robot:\n    def drive(self, speed):\n        pass\n"
    )
    result = suggestions(
        "from robot import Robot\nrobot = Robot()\nrobot.dr", path=tmp_path / "main.py"
    )
    assert "drive" in dict(result.words)
    assert not marker.exists()
    scope = suggestions("def first():\n    private_value = 1\ndef second():\n    pri")
    assert "private_value" not in dict(scope.words)


def test_completion_replaces_unicode_word_and_is_one_undo_step(qt_app):
    editor = CodeEdit()
    editor.show()
    editor.setFocus()
    qt_app.processEvents()
    try:
        source = 'print("😀"); переменная = 1; пер_ошибка'
        at_end(editor, source)
        cursor = editor.textCursor()
        cursor.setPosition(qt_offset(source, source.index("пер_ошибка") + 3))
        editor.setTextCursor(cursor)
        QTest.keyClick(editor, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
        wait_for(lambda: editor.assist.completer.popup().isVisible())
        assert "переменная" in editor.assist.words
        editor.assist.complete("переменная")
        assert editor.toPlainText() == source.replace("пер_ошибка", "переменная")
        editor.undo()
        assert editor.toPlainText() == source
    finally:
        editor.close()
        editor.assist.queue.pool.waitForDone()
        qt_app.processEvents()


def test_auto_completion_acceptance_signatures_and_escape(qt_app):
    editor = CodeEdit()
    editor.show()
    editor.setFocus()
    qt_app.processEvents()
    try:
        at_end(editor, "items = []\nitems")
        QTest.keyClicks(editor, ".app")
        wait_for(lambda: editor.assist.completer.popup().isVisible())
        assert "append" in editor.assist.words
        QTest.keyClick(editor.assist.completer.popup(), Qt.Key.Key_Tab)
        assert editor.toPlainText().endswith("items.append")
        QTest.keyClicks(editor, "(")
        wait_for(lambda: "append(" in QToolTip.text())
        assert "object" in QToolTip.text()
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        assert editor.assist.request is None
        assert not editor.assist.timer.isActive()
        # Even a worker already running when Escape is pressed may not reopen it.
        QTest.keyClick(editor, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
        request = editor.assist.request
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        editor.assist.receive(
            editor.assist.owner, request, Suggestions((("unexpected", 0),))
        )
        assert not editor.assist.completer.popup().isVisible()
        # Moving the cursor invalidates completed work just like editing does.
        editor.assist.ask("complete")
        request = editor.assist.request
        editor.moveCursor(QTextCursor.MoveOperation.Start)
        editor.assist.receive(
            editor.assist.owner, request, Suggestions((("unexpected", 0),))
        )
        assert not editor.assist.completer.popup().isVisible()
        at_end(editor, "def turn(speed, angle):\n    pass\nturn(100, ")
        QTest.keyClick(
            editor,
            Qt.Key.Key_Space,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        wait_for(lambda: "turn(speed, angle)" in QToolTip.text())
        assert "<b>angle</b>" in QToolTip.text()
    finally:
        editor.close()
        editor.assist.queue.pool.waitForDone()
        qt_app.processEvents()
