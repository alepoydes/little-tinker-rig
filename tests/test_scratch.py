import ast
from unittest.mock import patch

import pytest

from pyblocks.core import edit
from pyblocks.core.parameters import choices, slots
from pyblocks.core.presentation import regions, snippet_role
from pyblocks.core.session import Session
from pyblocks.core.snippets import Parameter, instantiate
from pyblocks.core.transfer import Transfer


def snippet(session, name):
    return next(s for s in session.snippets if s.identity.endswith("/" + name))


def test_transfer_is_atomic_context_checked_and_undoable(tmp_path):
    path = tmp_path / "main.py"
    path.write_text("while True:\n    print(1)\n    break\n")
    session = Session(path)
    original = session.document.state
    session.editor.selection = session.document.syntax.tree.body[0].body[-1]
    transfer = Transfer.capture(session)
    assert session.document.state is original
    transfer.to_scratch(0)
    detached = session.document.state
    assert detached.scratch == ("break\n",)
    fragment = Session.fragment(detached.scratch[0], session.snippets)
    assert isinstance(fragment.document.syntax.tree.body[0], ast.Break)
    destination = edit.Target(session.document.syntax.suites[0], 1)
    with pytest.raises(SyntaxError):
        Transfer.capture(session, index=0).to_program(destination)
    assert session.document.state is detached
    destination = next(
        t
        for t in edit.insertion_targets(session.document.syntax, "break")
        if isinstance(t.suite.owner, ast.While) and t.index == 1
    )
    Transfer.capture(session, index=0).to_program(destination)
    assert session.document.state == original
    session.editor.undo()
    assert session.document.state is detached
    session.editor.undo()
    assert session.document.state is original
    with pytest.raises(ValueError, match="changed"):
        transfer.to_scratch(0)


def test_fragment_library_imports_partial_transfer_and_reorder(tmp_path):
    session = Session(tmp_path / "main.py")
    fragment = Session.fragment("", session.snippets)
    fragment.insert_snippet(snippet(session, "create_ultrasonic_sensor"), {})
    assert "import" not in fragment.document.state.source
    declaration = fragment.document.syntax.tree.body[0]
    assert isinstance(declaration, ast.AnnAssign)
    assert declaration.annotation.value == "UltrasonicSensor"
    assert ast.unparse(declaration.value) == "UltrasonicSensor(Port.D)"
    session.set_scratch(
        None, fragment.document.state.source + "print(distance.distance())\n"
    )
    session.set_scratch(None, "while True:\n    pass\n")
    fragment = Session.fragment(session.document.state.scratch[0], session.snippets)
    fragment.editor.selection = fragment.document.syntax.tree.body[0]
    Transfer.capture(session, index=0, fragment=fragment).to_program(
        edit.Target(session.document.syntax.suites[0], 0)
    )
    assert "from pybricks.parameters import Port" in session.document.state.source
    assert (
        "from pybricks.pupdevices import UltrasonicSensor"
        in session.document.state.source
    )
    assert not session.analysis.diagnostics()
    assert session.document.state.scratch[0] == "print(distance.distance())\n"
    target = Session.fragment(session.document.state.scratch[1], session.snippets)
    destination = next(
        t
        for t in edit.insertion_targets(
            target.document.syntax, "print(distance.distance())"
        )
        if isinstance(t.suite.owner, ast.While)
    )
    Transfer.capture(session, index=0).to_fragment(1, target, destination)
    assert session.document.state.scratch == (
        "while True:\n    print(distance.distance())\n",
    )
    assert "import" not in session.document.state.scratch[0]
    session.set_scratch(None, "unfinished =")
    before = session.document.state
    Transfer.capture(session, index=1).to_scratch(0)
    assert session.document.state.scratch == tuple(reversed(before.scratch))
    session.editor.undo()
    assert session.document.state is before
    with pytest.raises(SyntaxError):
        Transfer.capture(session, index=1).to_program(
            edit.Target(session.document.syntax.suites[0], 0)
        )
    assert session.document.state is before
    assert not session.fragment_imports("Motor = 10\nprint(Motor)\n")


def test_typed_choices_and_coherent_constructor_blocks(tmp_path):
    path = tmp_path / "main.py"
    path.write_text(
        "from pybricks.pupdevices import Motor, ForceSensor, UltrasonicSensor\nfrom pybricks.parameters import Port\nleft = Motor(Port.A)\nbutton = ForceSensor(Port.E)\ndistance = UltrasonicSensor(Port.D)\nready = True\nspeed = 200\nif ready:\n    left.run(speed)\n"
    )
    session = Session(path)
    offset = session.document.state.source.index("if ready")
    boolean = choices(session, Parameter("condition", None, "bool"), offset)
    assert {"ready", "True", "False", "button.pressed()"} <= set(boolean)
    assert not {
        "Exception",
        "BaseException",
        "Motor",
        "left",
        "speed",
        "distance.distance()",
    } & set(boolean)
    assert choices(session, Parameter("motor", None, "Motor"), offset) == ("left",)
    numeric = choices(session, Parameter("speed", None, "deg/s"), offset)
    assert "speed" in numeric
    assert not {"left.angle()", "distance.distance()"} & set(numeric)
    assert "button.pressed()" not in numeric and "ready" not in numeric
    match = next(
        m for m in session.matches if m.snippet.identity.endswith("/create_motor")
    )
    colored = [
        r
        for r in regions(session.document.syntax, session.visible_matches)
        if match.span.start <= r.span.start and r.span.end <= match.span.end
    ]
    assert len(colored) == 1 and colored[0].span == match.span
    assert colored[0].role == snippet_role(match.snippet)
    assert all(
        slot.parameter.name != "condition" or slot.parameter.annotation == "bool"
        for slot in slots(session)
    )


def test_inserted_selection_tracks_imports_and_duplicate_blocks(tmp_path):
    session = Session(tmp_path / "main.py")
    motor = snippet(session, "create_motor")
    session.insert_snippet(motor, {})
    assert session.selected_match().snippet is motor
    assert not session.analysis.diagnostics()
    session.insert_snippet(snippet(session, "run_motor"), {})
    session.insert_snippet(snippet(session, "run_motor"), {})
    selected = session.editor.statement()
    assert selected is session.document.syntax.tree.body[-1]
    assert ast.unparse(selected) == "motor.run(500)"


def send_drop(qt_app, widget, data, point):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

    action = (
        Qt.DropAction.MoveAction
        if data.hasFormat("application/x-pyblocks-fragment")
        else Qt.DropAction.CopyAction
    )
    args = (action, data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    enter, move = QDragEnterEvent(point, *args), QDragMoveEvent(point, *args)
    qt_app.sendEvent(widget, enter)
    qt_app.sendEvent(widget, move)
    assert enter.isAccepted() and move.isAccepted()
    drop = QDropEvent(QPointF(point), *args)
    qt_app.sendEvent(widget, drop)
    qt_app.processEvents()
    assert drop.isAccepted()


def close_window(window):
    from PySide6.QtWidgets import QMessageBox

    with patch.object(
        QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard
    ):
        window.close()


def test_qt_drag_library_scratch_program_undo_and_raw_draft(tmp_path, qt_app):
    from PySide6.QtCore import QMimeData, QPoint

    from pyblocks.qt.app import Studio
    from pyblocks.qt.drag import BlockMime

    window = Studio(tmp_path / "main.py")
    window.show()
    qt_app.processEvents()
    try:
        data = QMimeData()
        data.setData("application/x-pyblocks-snippet", b"pybricks/motors/create_motor")
        send_drop(qt_app, window.scratch.viewport(), data, QPoint(30, 30))
        assert not window.session.document.state.source
        assert len(window.scratch.cells) == 1
        cell = window.scratch.cells[0]
        motor_source = cell.source.toPlainText()
        declaration = ast.parse(motor_source).body[0]
        assert isinstance(declaration, ast.AnnAssign)
        assert declaration.annotation.value == "Motor"
        assert ast.unparse(declaration.value) == "Motor(Port.A)"
        assert cell.source.isVisible() and not cell.code_active
        assert cell.source.notes[1][0].description
        data = BlockMime(Transfer.capture(window.session, index=0))
        send_drop(qt_app, window.source.viewport(), data, QPoint(30, 30))
        assert not window.scratch.cells and not window.session.analysis.diagnostics()
        assert "Motor(Port.A)" in window.source.toPlainText()
        main = window.session.document.state
        window.session.editor.selection = window.session.document.syntax.tree.body[-1]
        data = BlockMime(Transfer.capture(window.session))
        send_drop(qt_app, window.scratch.viewport(), data, QPoint(30, 30))
        cell = window.scratch.cells[0]
        cell.source.setFocus()
        qt_app.processEvents()
        window.undo_action.trigger()
        assert window.session.document.state is main and not window.scratch.cells
        window.redo_action.trigger()
        cell = window.scratch.cells[0]
        cell.change_mode(True)
        cell.code.setFocus()
        cell.code.selectAll()
        cell.code.insertPlainText("motor =")
        assert window.session.document.state.scratch == ("motor =",)
        window.undo_action.trigger()
        assert ast.dump(
            ast.parse(window.session.document.state.scratch[0])
        ) == ast.dump(ast.parse(motor_source))
        window.session.project.save()
        loaded = Session(window.session.project.path)
        assert loaded.document.state == window.session.document.state
    finally:
        close_window(window)


def test_qt_window_controls_scratch_visibility_and_help(tmp_path, qt_app):
    from PySide6.QtCore import Qt

    from pyblocks.qt.app import Studio

    window = Studio(tmp_path / "main.py")
    window.show()
    qt_app.processEvents()
    try:
        for flag in (
            Qt.WindowType.WindowMinimizeButtonHint,
            Qt.WindowType.WindowMaximizeButtonHint,
            Qt.WindowType.WindowCloseButtonHint,
        ):
            assert window.windowFlags() & flag
        window.showMaximized()
        assert window.isMaximized()
        window.showMinimized()
        assert window.isMinimized()
        window.showNormal()
        assert window.scratch_dock.isVisible()
        assert window.device_dock in window.tabifiedDockWidgets(window.scratch_dock)
        window.device_dock.raise_()
        qt_app.processEvents()
        assert window.scratch_visible
        window.set_mode(1)
        assert not window.scratch_dock.isVisible()
        window.set_mode(0)
        assert window.scratch_dock.isVisible()
        window.scratch_dock.hide()
        window.set_mode(1)
        window.set_mode(0)
        assert not window.scratch_dock.isVisible()
        window.show_help()
        window.help_page.show_page("pybricks/motors/create_motor")
        browser = window.help_page.browser
        assert browser.document().defaultFont().pointSize() >= 12
        assert "Connect a motor" in browser.toPlainText()
        assert (
            "Port.A" in browser.toPlainText() or "Motor(port)" in browser.toPlainText()
        )
        assert browser.document().findBlockByNumber(0).blockFormat().headingLevel() == 1
    finally:
        close_window(window)


def test_qt_annotations_keep_source_and_scroll_anchor(tmp_path, qt_app):
    from PySide6.QtGui import QTextCursor

    from pyblocks.qt.editor import SourceView

    path = tmp_path / "main.py"
    path.write_text("\n".join(f"value_{i} = {i}" for i in range(60)))
    session = Session(path)
    view = SourceView(session)
    view.resize(850, 600)
    view.show()
    qt_app.processEvents()
    try:
        block = view.document().findBlockByNumber(25)
        view.setTextCursor(QTextCursor(block))
        view.centerCursor()
        qt_app.processEvents()
        anchor = "value_22"
        cursor = view.document().find(anchor)
        old_y = view.cursorRect(cursor).y()
        session.editor.selection = session.document.syntax.tree.body[26]
        session.insert_snippet(snippet(session, "create_motor"), {})
        view.refresh_source()
        view.reveal(session.document.syntax.spans[session.editor.selection].start)
        qt_app.processEvents()
        assert abs(view.cursorRect(view.document().find(anchor)).y() - old_y) <= 1
        rect = view.cursorRect(view.document().find("motor ="))
        assert 0 <= rect.top() < view.viewport().height()
        assert view.toPlainText() == session.document.state.source
        assert "# Connect" not in session.document.state.source
        session.editor.selection = session.document.syntax.tree.body[-1]
        session.insert_snippet(snippet(session, "wait_ms"), {})
        view.refresh_source()
        view.reveal(session.document.syntax.spans[session.editor.selection].start)
        assert (
            0
            <= view.cursorRect(view.document().find("wait(1000)")).top()
            < view.viewport().height()
        )
    finally:
        view.close()


def test_qt_blank_lines_continue_nested_indentation_bands(qt_app):
    from PySide6.QtGui import QTextCursor

    from pyblocks.qt.editor import SourceView

    session = Session.fragment(
        "def task():\n    while True:\n        print(1)\n\n        print(2)\n", ()
    )
    view = SourceView(session)
    view.resize(650, 420)
    view.show()
    qt_app.processEvents()
    try:
        view.pulse.stop()
        image = view.viewport().grab().toImage()
        blank = view.document().findBlockByNumber(3)
        body = view.document().findBlockByNumber(2)
        y_blank = view.cursorRect(QTextCursor(blank)).center().y()
        y_body = view.cursorRect(QTextCursor(body)).center().y()
        origin = view.cursorRect(QTextCursor(blank)).x()
        space = view.fontMetrics().horizontalAdvance(" ")
        for column in (2, 6):
            x = origin + column * space
            assert image.pixelColor(x, y_blank) == image.pixelColor(x, y_body)
        assert image.pixelColor(origin + 2 * space, y_blank) != image.pixelColor(
            origin + 6 * space, y_blank
        )
    finally:
        view.close()


def test_qt_single_block_can_be_dragged_out_even_without_internal_target(
    tmp_path, qt_app
):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from pyblocks.qt.app import Studio

    path = tmp_path / "main.py"
    path.write_text("motor.run(500)\n")
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    try:
        view = window.source
        rect = view._rect(1, 0)
        start = QPoint(view.viewport().width() - 80, int(rect.center().y()))
        with patch("pyblocks.qt.editor.drag_block") as drag:
            QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
            QTest.mouseMove(view.viewport(), start + QPoint(20, 0), 30)
            QTest.mouseMove(
                view.viewport(), QPoint(view.viewport().width() + 20, start.y()), 30
            )
            QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
            assert drag.call_count == 1
            transfer = drag.call_args.args[1]
            assert transfer.text == "motor.run(500)\n"
            assert window.session.document.state.source == transfer.text
            assert not window.session.document.state.scratch
    finally:
        close_window(window)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model,constructor,reading,expected",
    [
        ("inventor", "create_ultrasonic_sensor", "distance", "500"),
        ("boost", "create_color_distance_sensor", "boost_distance", "50"),
        ("technic", "create_ultrasonic_sensor", "distance", "500"),
    ],
)
async def test_program_built_from_library_runs_on_virtual_hubs(
    tmp_path, model, constructor, reading, expected
):
    from pyblocks.pybricks.virtual import VirtualConnection

    session = Session(tmp_path / "robot.py")
    for name, bindings in (
        ("create_motor", {"name": "left", "port": "Port.A"}),
        ("create_motor", {"name": "right", "port": "Port.B"}),
        ("create_drive", {"left": "left", "right": "right"}),
        (constructor, {"name": "sensor", "port": "Port.D"}),
        ("create_clock", {}),
        ("drive", {"speed": "100"}),
        ("wait_ms", {"duration": "80"}),
        ("brake", {}),
        ("turn_motor", {"motor": "left", "angle": "15", "speed": "300"}),
        (
            "display",
            {
                "value": instantiate(
                    snippet(session, reading), {"sensor": "sensor"}
                ).source
            },
        ),
    ):
        session.editor.selection = session.document.syntax.tree
        session.insert_snippet(snippet(session, name), bindings)
    assert not session.analysis.diagnostics()
    session.project.save()
    output = []
    hub = VirtualConnection(output.append, model=model)
    try:
        await hub.connect()
        await hub.run(session.project.path, wait=True)
        assert expected in b"".join(output).decode()
        assert hub.info.ports["A"]["angle"] > 15
        assert hub.info.ports["A"]["speed"] == hub.info.ports["B"]["speed"] == 0
        assert not hub.info.error
    finally:
        await hub.disconnect()


def test_qt_drop_into_empty_line_uses_pointer_indentation(tmp_path, qt_app):
    from PySide6.QtCore import QMimeData, QPoint

    from pyblocks.qt.app import Studio

    path = tmp_path / "main.py"
    path.write_text("while True:\n    print(1)\n")
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    try:
        view = window.source
        blank = view._rect(view.document().blockCount(), 4)
        data = QMimeData()
        data.setData("application/x-pyblocks-snippet", b"pybricks/sensors/wait_ms")
        send_drop(
            qt_app,
            view.viewport(),
            data,
            QPoint(int(blank.left()), int(blank.center().y())),
        )
        loop = window.session.document.syntax.tree.body[-1]
        assert isinstance(loop, ast.While)
        assert [ast.unparse(node) for node in loop.body] == ["print(1)", "wait(1000)"]
    finally:
        close_window(window)
