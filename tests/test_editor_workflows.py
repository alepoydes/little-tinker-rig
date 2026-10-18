from pathlib import Path
from unittest.mock import patch

import pytest

from little_tinker_rig.core import edit
from little_tinker_rig.core.presentation import PALETTE
from little_tinker_rig.core.syntax import Syntax


def close_window(window):
    from PySide6.QtWidgets import QMessageBox

    with patch.object(
        QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard
    ):
        window.close()


def test_recent_files_persist_deduplicate_and_preserve_open_drafts(tmp_path, qt_app):
    from PySide6.QtCore import QSettings

    from little_tinker_rig.qt.app import Studio

    first, second = tmp_path / "first.py", tmp_path / "second.py"
    first.write_text("print(1)\n")
    second.write_text("print(2)\n")
    window = Studio(first)
    try:
        page = window.document_page
        page.change_mode(1)
        page.code.setPlainText("unfinished =")
        window.open_document(second)
        window.refresh_recent_files()
        assert [a.data() for a in window.recent_menu.actions() if a.data()] == [
            str(second),
            str(first),
        ]
        window.recent_menu.actions()[1].trigger()
        assert window.document_page is page
        assert page.code.toPlainText() == "unfinished ="
        assert window.documents.count() == 2
        window.settings.sync()
        stored = QSettings(window.settings.fileName(), QSettings.Format.IniFormat)
        assert stored.value("recentFiles") == [str(first), str(second)]
        window.new_file()
        assert window.settings.value("recentFiles") == [str(first), str(second)]
        second.unlink()
        window.refresh_recent_files()
        assert not window.recent_menu.actions()[1].isEnabled()
        window.recent_menu.actions()[-1].trigger()
        window.refresh_recent_files()
        assert len(window.recent_menu.actions()) == 1
        assert not window.recent_menu.actions()[0].isEnabled()
    finally:
        close_window(window)


def test_window_buttons_and_title_double_click_work(tmp_path, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "main.py")
    window.show()
    qt_app.processEvents()
    try:
        title = window.title_bar
        assert all(
            button.isVisible()
            for button in (title.minimize, title.maximize, title.close_button)
        )
        QTest.mouseClick(title.maximize, Qt.MouseButton.LeftButton)
        assert window.isMaximized()
        QTest.mouseClick(title.maximize, Qt.MouseButton.LeftButton)
        assert not window.isMaximized()
        QTest.mouseDClick(title, Qt.MouseButton.LeftButton)
        assert window.isMaximized()
        QTest.mouseClick(title.minimize, Qt.MouseButton.LeftButton)
        assert window.isMinimized()
        window.showNormal()
        QTest.mouseClick(title.close_button, Qt.MouseButton.LeftButton)
        assert not window.isVisible()
    finally:
        window.close()


def test_courier_ports_names_and_plain_fields_accept_real_clicks(tmp_path, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit

    from little_tinker_rig.qt.app import Studio

    path = tmp_path / "courier.py"
    path.write_text(Path("examples/courier.py").read_text())
    window = Studio(path)
    window.resize(1500, 980)
    window.show()
    qt_app.processEvents()
    view = window.source

    def open_field(value):
        slot = next(
            slot
            for slot in view.parameter_slots
            if slot.syntax.source[slot.span.start : slot.span.end] == value
        )
        view.reveal(slot.span.start)
        qt_app.processEvents()
        QTest.mouseClick(
            view.viewport(),
            Qt.MouseButton.LeftButton,
            pos=view.parameter_rect(slot).center().toPoint(),
        )
        qt_app.processEvents()
        field = view.parameter_editor
        assert field is not None and field.isVisible(), value
        return field

    try:
        original = window.session.document.state
        for value in ("Port.A", "Port.B", "Port.C", "Port.D", "Port.E", "Port.F"):
            field = open_field(value)
            assert field.arrow.isVisible() and field.completer.popup().isVisible()
            assert field.line_edit.text() == value
            assert window.session.document.state is original
            QTest.keyClick(field.line_edit, Qt.Key.Key_Escape)
            qt_app.processEvents()
        for value in ("left", "right", "30000"):
            field = open_field(value)
            assert isinstance(field.field, QLineEdit)
            assert field.arrow is None and field.completer is None
            QTest.keyClick(field.line_edit, Qt.Key.Key_Escape)
            qt_app.processEvents()
        field = open_field("Port.B")
        popup = field.completer.popup()
        index = next(
            popup.model().index(i, 0)
            for i in range(popup.model().rowCount())
            if popup.model().index(i, 0).data() == "Port.C"
        )
        QTest.mouseClick(
            popup.viewport(),
            Qt.MouseButton.LeftButton,
            pos=popup.visualRect(index).center(),
        )
        qt_app.processEvents()
        assert "right = Motor(Port.C)" in window.session.document.state.source
        window.session.editor.undo()
        window.refresh_views()
        assert window.session.document.state is original
        field = open_field("right")
        field.line_edit.selectAll()
        QTest.keyClicks(field.line_edit, "right_motor")
        QTest.keyClick(field.line_edit, Qt.Key.Key_Return)
        assert "right_motor = Motor(Port.B)" in window.session.document.state.source
    finally:
        close_window(window)


@pytest.mark.parametrize(
    "state", ["normal", "maximized", "fullscreen", "minimized", "maximized_minimized"]
)
def test_window_geometry_and_state_survive_reopening(tmp_path, qt_app, state):
    from PySide6.QtCore import QSettings

    from little_tinker_rig.qt.app import Studio

    path = tmp_path / "main.py"
    path.write_text("print(1)\n")
    window = Studio(path)
    window.resize(1100, 760)
    window.move(45, 60)
    window.show()
    qt_app.processEvents()
    normal = window.geometry()
    if state.startswith("maximized"):
        window.showMaximized()
    elif state == "fullscreen":
        window.showFullScreen()
    qt_app.processEvents()
    if state.endswith("minimized"):
        window.showMinimized()
        qt_app.processEvents()
    assert window.close()
    stored = QSettings(window.settings.fileName(), QSettings.Format.IniFormat)
    assert stored.value("windowGeometry")

    restored = Studio(path)
    restored.show()
    qt_app.processEvents()
    try:
        assert not restored.isMinimized()
        assert restored.isMaximized() == state.startswith("maximized")
        assert restored.isFullScreen() == (state == "fullscreen")
        assert restored.title_bar.isVisible()
        assert restored.title_bar.menu.isVisible()
        restored.showNormal()
        qt_app.processEvents()
        assert restored.geometry() == normal
    finally:
        close_window(restored)


def test_cancelled_close_does_not_replace_saved_geometry(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    window = Studio(tmp_path / "main.py")
    window.show()
    qt_app.processEvents()
    saved = window.saveGeometry()
    window.settings.setValue("windowGeometry", saved)
    window.showMaximized()
    try:
        with patch.object(window, "confirm_close", return_value=False):
            assert not window.close()
        assert window.isVisible()
        assert window.settings.value("windowGeometry") == saved
    finally:
        close_window(window)


def test_notes_have_owned_colors_rows_and_drop_boundary(tmp_path, qt_app):
    from PySide6.QtGui import QColor

    from little_tinker_rig.qt.app import Studio

    path = tmp_path / "robot.py"
    path.write_text(
        "from pybricks.parameters import Port\nfrom pybricks.pupdevices import Motor, UltrasonicSensor\nmotor = Motor(Port.A)\ndistance = UltrasonicSensor(Port.D)\nif distance.distance() < 100:\n    # Slow approach\n    motor.run(120)\n"
    )
    window = Studio(path)
    window.resize(1500, 1000)
    window.show()
    qt_app.processEvents()
    view = window.source
    try:
        original = window.session.document.state.source
        syntax = window.session.document.syntax
        condition = syntax.tree.body[-1]
        line = syntax.position(syntax.spans[condition].start)[0]
        assert [note.role for note in view.notes[line]] == ["control", "value"]
        parent, child = view.note_rect(line, 0), view.note_rect(line, 1)
        assert parent.bottom() <= child.top()
        target = edit.Target(syntax.statement_suite[condition], 4)
        assert view.target_rect(target).top() <= parent.top()
        view.intensity = 1
        window.session.editor.selection = syntax.tree
        view.hover = None
        image = view.viewport().grab().toImage().scaled(view.viewport().size())
        for rect, role in ((parent, "control"), (child, "value")):
            color = QColor(PALETTE[role])
            base = QColor("#fafbfc")
            expected = QColor(
                *(
                    round(a * b / 255)
                    for a, b in zip(color.getRgb()[:3], base.getRgb()[:3], strict=True)
                )
            )
            assert (
                image.pixelColor(int(rect.left()) + 2, int(rect.top()) + 2) == expected
            )
            assert (
                image.pixelColor(int(rect.right()) - 70, int(rect.top()) + 2)
                == expected
            )
        motor = condition.body[0]
        region = next(r for r in view.presentation if r.span == syntax.spans[motor])
        assert region.line == syntax.position(original.index("# Slow approach"))[0]
        assert region.role == "action"
        assert window.session.document.state.source == original
    finally:
        close_window(window)


def test_wide_syntax_hit_testing_keeps_comments_and_unicode_owners():
    source = 'items = {"😀": 1, "ёж": 2}\n' + "".join(
        f"# item {i}\nx_{i} = {i}\n" for i in range(200)
    )
    syntax = Syntax(source)
    for offset in range(0, len(source), 7):
        expected = syntax.tree
        while child := next(
            (
                node
                for node in syntax.children[expected]
                if syntax.owned_spans[node].contains(offset)
            ),
            None,
        ):
            expected = child
        assert syntax.at(offset) is expected
    old = 'print("unchanged")\n' * 10000
    inserted = "import math\n" + old[:5000] + "# new\n" + old[5000:]
    for offset in (0, 2500, 5000, len(old) - 1):
        moved = edit.map_offset(old, inserted, offset)
        assert inserted[moved] == old[offset]
        assert moved == offset + len("import math\n") + (
            len("# new\n") if offset >= 5000 else 0
        )


def test_qt_positions_round_trip_mixed_unicode(qt_app):
    from little_tinker_rig.qt.editor import qt_offset, source_offset

    source = 'имя = "😀🚀"\nprint("🦊", имя)\n'
    for offset in range(len(source) + 1):
        expected = len(source[:offset].encode("utf-16-le")) // 2
        assert qt_offset(source, offset) == expected
        assert source_offset(source, expected) == offset
