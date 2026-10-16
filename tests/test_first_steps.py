"""Walk lessons through the desktop controls, starting from an empty program."""

from time import monotonic

import pytest
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QToolButton,
)

from little_tinker_rig.qt.app import Studio
from little_tinker_rig.qt.device import ConnectDialog
from little_tinker_rig.qt.library import FAMILY, IDENTITY


def wait_until(predicate):
    deadline = monotonic() + 10
    while not predicate():
        assert monotonic() < deadline, "Lesson action did not finish"
        QTest.qWait(20)


def add(window, identity):
    before = window.session.document.state
    library = window.library
    item = next(
        library.topLevelItem(i).child(j)
        for i in range(library.topLevelItemCount())
        for j in range(library.topLevelItem(i).childCount())
        if library.topLevelItem(i).child(j).data(0, FAMILY)
        == library.snippets[identity].catalog_id
    )
    assert not item.isHidden() and not item.parent().isHidden()
    library.expandItem(item.parent())
    QApplication.processEvents()
    library.scrollToItem(item)
    QApplication.processEvents()
    rect = library.visualItemRect(item)
    assert library.viewport().rect().contains(rect.center()), (
        identity,
        rect,
        library.viewport().rect(),
    )
    assert library.itemAt(rect.center()) is item, (
        identity,
        rect,
        library.viewport().rect(),
        item.parent().isExpanded(),
    )
    QTest.mouseClick(library.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    if item.data(0, IDENTITY) != identity:
        menu = library.context_menu(item)
        variants = next(a.menu() for a in menu.actions() if a.menu())
        next(a for a in variants.actions() if a.data() == identity).trigger()
        menu.deleteLater()
    assert item.data(0, IDENTITY) == identity
    assert library.currentItem() is item, (
        identity,
        library.currentItem().data(0, IDENTITY),
    )
    QTest.mouseDClick(library.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    QApplication.processEvents()
    assert window.session.document.state is not before, (
        identity,
        window.console.toPlainText(),
        window.document_page.text,
    )


def field(window, before, after):
    view = window.source
    slot = next(
        s
        for s in view.parameter_slots
        if s.syntax.source[s.span.start : s.span.end] == before
    )
    view.reveal(slot.span.start)
    QApplication.processEvents()
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=view.parameter_rect(slot).center().toPoint(),
    )
    if before == "...":
        popup = view.expression_popup
        QTest.keyClicks(popup.search, after)
        QTest.keyClick(popup.search, Qt.Key.Key_Return)
        QApplication.processEvents()
        return
    editor = view.parameter_editor.line_edit
    editor.selectAll()
    QTest.keyClicks(editor, after)
    QTest.keyClick(editor, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert view.parameter_editor is None or not view.parameter_editor.isVisible()


def select_line(window, text):
    view = window.source
    assert text in view.toPlainText(), view.toPlainText()
    line = next(
        i
        for i, source in enumerate(view.toPlainText().splitlines(), 1)
        if source.strip() == text
    )
    # The painted row is a usable target, including its empty right-hand area.
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=view._rect(line, 4).center().toPoint(),
    )
    QApplication.processEvents()


def connect(window, model="inventor"):
    def choose():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, ConnectDialog)
        dialog.transport.setCurrentIndex(dialog.transport.findData("virtual"))
        dialog.model.setCurrentIndex(dialog.model.findData(model))
        QTest.mouseClick(
            dialog.findChild(QDialogButtonBox).button(
                QDialogButtonBox.StandardButton.Ok
            ),
            Qt.MouseButton.LeftButton,
        )

    QTimer.singleShot(0, choose)
    QTest.mouseClick(window.hub_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: window.hub_info.connected and not window.hub_is_busy)


def run(window):
    button = next(
        b
        for b in window.findChildren(QToolButton)
        if b.defaultAction() is window.run_action
    )
    assert button.isEnabled()
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)


def select_value(window, value):
    view = window.source
    slot = next(
        s
        for s in view.parameter_slots
        if s.syntax.source[s.span.start : s.span.end] == value
    )
    view.reveal(slot.span.start)
    QApplication.processEvents()
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=view.parameter_rect(slot).center().toPoint(),
    )
    QTest.keyClick(view.parameter_editor.line_edit, Qt.Key.Key_Escape)
    QApplication.processEvents()


def test_first_lesson_build_save_run_and_reopen(tmp_path, qt_app, monkeypatch):
    window = Studio(tmp_path / "greeting.py")
    window.confirm_close = lambda *_: True
    window.show()
    qt_app.processEvents()
    try:
        assert window.library.topLevelItem(0).text(0) == "Program"
        add(window, "python/basics/repeat")
        field(window, "10", "3")
        select_line(window, "pass")
        add(window, "python/basics/display")
        field(window, '"Hello!"', '"Hi robot!"')
        source = 'for i in range(3):\n    print("Hi robot!")\n'
        assert window.document_page.text == source
        connect(window)
        run(window)
        wait_until(lambda: window.console.toPlainText().count("Hi robot!") == 3)
        wait_until(lambda: not window.hub_info.running and not window.hub_is_busy)
        assert (tmp_path / "greeting.py").read_text() == source
        page = window.document_page
        window.close_document(window.documents.currentIndex())
        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileNames",
            lambda *a: ([str(tmp_path / "greeting.py")], ""),
        )
        button = next(
            b
            for b in window.findChildren(QToolButton)
            if b.defaultAction() and b.defaultAction().text() == "Open"
        )
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert window.document_page is not page
        window.refresh_recent_files()
        window.recent_menu.actions()[0].trigger()
        assert window.document_page.text == source
        assert not window.document_page.dirty
        assert not window.runtime_panel.problem
    finally:
        window.close()


@pytest.mark.parametrize("model", ["inventor", "boost", "technic"])
def test_motor_lesson_from_blocks_on_each_hub(tmp_path, qt_app, model):
    window = Studio(tmp_path / "motor_lesson.py")
    window.confirm_close = lambda *_: True
    window.show()
    qt_app.processEvents()
    try:
        connect(window, model)
        add(window, "pybricks/motors/create_motor")
        field(window, "motor", "wheel")
        add(window, "python/basics/repeat")
        field(window, "10", "3")
        select_line(window, "pass")
        add(window, "pybricks/motors/turn_motor")
        field(window, "90", "30")
        field(window, "300", "600")
        assert "    wheel.run_angle(600, 30)" in window.document_page.text
        assert not window.session.analysis.diagnostics()
        run(window)
        wait_until(lambda: window.hub_info.ports["A"]["angle"] == 90)
        wait_until(lambda: not window.hub_info.running and not window.hub_is_busy)
        assert window.hub_info.ports["A"]["speed"] == 0
        assert not window.runtime_panel.problem
        window.level_filter.select("intermediate")
        select_line(window, "for i in range(3):")
        add(window, "python/basics/forever")
        select_line(window, "pass")
        add(window, "pybricks/sensors/wait_ms")
        field(window, "1000", "20")
        run(window)
        wait_until(
            lambda: window.hub_info.ports["A"]["angle"] == 180
            and window.hub_info.running
        )
        stop = next(
            b
            for b in window.findChildren(QToolButton)
            if b.defaultAction() is window.stop_action
        )
        QTest.mouseClick(stop, Qt.MouseButton.LeftButton)
        wait_until(lambda: not window.hub_info.running and not window.hub_is_busy)
        assert not window.runtime_panel.problem
    finally:
        window.close()


def test_route_lesson_lists_iteration_and_measured_results(tmp_path, qt_app):
    window = Studio(tmp_path / "route.py")
    window.confirm_close = lambda *_: True
    window.show()
    qt_app.processEvents()
    try:
        connect(window)
        window.level_filter.select("advanced")
        add(window, "pybricks/drive/create_robot")
        add(window, "python/data/make_list")
        add(window, "python/flow/for_each")
        select_line(window, "pass")
        add(window, "pybricks/drive/straight")
        field(window, "200", "item")
        QTest.keyClick(window.source, Qt.Key.Key_Escape)
        add(window, "pybricks/drive/turn")
        select_line(window, "for item in values:")
        add(window, "python/basics/display")
        select_value(window, '"Hello!"')
        add(window, "pybricks/drive/drive_distance")
        QTest.keyClick(window.source, Qt.Key.Key_Escape)
        add(window, "python/basics/display")
        select_value(window, '"Hello!"')
        add(window, "pybricks/drive/drive_angle")
        assert (
            "    drive.straight(item)\n    drive.turn(90)" in window.document_page.text
        )
        assert not window.session.analysis.diagnostics()
        run(window)
        wait_until(lambda: not window.hub_is_busy and not window.hub_info.running)
        # Simulated motor completion has a one-degree tolerance, as on the hub.
        # Connection and upload messages precede the program's two results.
        assert [
            float(s) for s in window.console.toPlainText().splitlines()[-2:]
        ] == pytest.approx([60, 270], abs=2)
        assert not window.runtime_panel.problem
    finally:
        window.close()


def test_mouse_drag_first_block_scratch_return_and_undo(tmp_path, qt_app):
    from little_tinker_rig.qt.drag import cancel_drag

    window = Studio(tmp_path / "drag_lesson.py")
    window.confirm_close = lambda *_: True
    window.show()
    qt_app.processEvents()

    def drag(source, start, destination, end):
        QTest.mousePress(source, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(source, start + QPoint(25, 0), 30)
        target = source.mapFromGlobal(destination.mapToGlobal(end))
        QTest.mouseMove(source, target, 30)
        QTest.mouseRelease(source, Qt.MouseButton.LeftButton, pos=target)
        qt_app.processEvents()

    try:
        library = window.library
        item = library.topLevelItem(0).child(0)
        assert item.data(0, IDENTITY) == "python/basics/display"
        drag(
            library.viewport(),
            library.visualItemRect(item).center(),
            window.source.viewport(),
            QPoint(100, 40),
        )
        assert window.document_page.text == 'print("Hello!")\n'
        before = window.session.document.state
        drag(
            window.source.viewport(),
            window.source.note_rect(1, 0).center().toPoint(),
            window.scratch.viewport(),
            QPoint(60, 60),
        )
        assert not window.document_page.text, window.console.toPlainText()
        assert window.session.document.state.scratch == (before.source,)
        window.undo_action.trigger()
        assert window.session.document.state is before
        window.redo_action.trigger()
        cell = window.scratch.cells[0]
        drag(
            cell.source.viewport(),
            cell.source.note_rect(1, 0).center().toPoint(),
            window.source.viewport(),
            QPoint(100, 40),
        )
        assert window.document_page.text == before.source
        assert not window.session.document.state.scratch
        window.save()
        assert (tmp_path / "drag_lesson.py").read_text() == before.source
    finally:
        cancel_drag()
        window.close()


def test_open_example_save_variation_run_and_correct_python_error(
    tmp_path, qt_app, monkeypatch
):
    from pathlib import Path

    from PySide6.QtGui import QTextCursor

    from little_tinker_rig.examples import examples_directory

    original = examples_directory() / "first.py"
    before = original.read_bytes()
    destination = tmp_path / "my_greeting.py"
    window = Studio()
    window.confirm_close = lambda *_: True
    window.show()
    qt_app.processEvents()
    try:
        window.refresh_examples()
        action = next(
            a for a in window.examples_menu.actions() if a.data() == str(original)
        )
        action.trigger()
        assert window.session.project.path == original.resolve()
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *a: (str(destination), "")
        )
        assert window.save_as()
        field(window, '"Hello from LittleTinker Rig!"', '"My greeting"')
        connect(window)
        run(window)
        wait_until(lambda: window.console.toPlainText().count("My greeting") == 3)
        window.document_page.mode_actions[1].trigger()
        window.code.moveCursor(QTextCursor.MoveOperation.End)
        QTest.keyClicks(window.code, "print(1 / 0)")
        run(window)
        wait_until(lambda: window.runtime_panel.problem is not None)
        assert window.runtime_panel.problem.kind == "ZeroDivisionError"
        QTest.mouseClick(window.runtime_panel.locate, Qt.MouseButton.LeftButton)
        assert (
            window.code.textCursor().blockNumber() + 1
            == window.runtime_panel.problem.line
        )
        window.document_page.mode_actions[0].trigger()
        assert not window.code_active
        assert any(
            note.error for notes in window.source.notes.values() for note in notes
        )
        # Correct the offending block through its ordinary parameter field.
        field(window, "0", "2")
        run(window)
        wait_until(lambda: "0.5\n" in window.console.toPlainText())
        assert not window.runtime_panel.problem
        assert original.read_bytes() == before
        assert "print(1 / 2)" in destination.read_text()
        assert window.session.project.path == Path(destination)
    finally:
        window.close()


def test_sensor_condition_built_from_library_and_changed_live(tmp_path, qt_app):
    window = Studio(tmp_path / "color_alarm.py")
    window.confirm_close = lambda *_: True
    window.show()
    qt_app.processEvents()
    try:
        connect(window)
        window.level_filter.select("intermediate")
        add(window, "pybricks/sensors/create_color_sensor")
        add(window, "python/basics/condition_else")
        slot = next(
            s
            for s in window.source.parameter_slots
            if s.syntax.source[s.span.start : s.span.end] == "True"
        )
        QTest.mouseClick(
            window.source.viewport(),
            Qt.MouseButton.LeftButton,
            pos=window.source.parameter_rect(slot).center().toPoint(),
        )
        QTest.keyClick(window.source.parameter_editor.line_edit, Qt.Key.Key_Escape)
        add(window, "pybricks/sensors/reflection_below")
        select_line(window, "pass")
        add(window, "python/basics/display")
        field(window, '"Hello!"', '"dark"')
        select_line(window, "pass")
        add(window, "python/basics/display")
        field(window, '"Hello!"', '"light"')
        assert "if sensor.reflection() < 30:" in window.document_page.text
        assert not window.session.analysis.diagnostics()
        _, _, slider = window.device_panel.rows["C"]
        slider.setValue(10)
        wait_until(lambda: window.hub_info.ports["C"]["reflection"] == 10)
        run(window)
        wait_until(lambda: "dark\n" in window.console.toPlainText())
        wait_until(lambda: not window.hub_info.running and not window.hub_is_busy)
        slider.setValue(80)
        wait_until(lambda: window.hub_info.ports["C"]["reflection"] == 80)
        run(window)
        wait_until(lambda: "light\n" in window.console.toPlainText())
        assert not window.runtime_panel.problem
    finally:
        window.close()


def test_function_lesson_add_parameter_body_calls_and_rename(tmp_path, qt_app):
    window = Studio(tmp_path / "functions.py")
    window.confirm_close = lambda *_: True
    window.show()
    qt_app.processEvents()
    try:
        connect(window)
        window.level_filter.select("intermediate")
        add(window, "python/basics/define_function")
        field(window, "action", "greet")
        select_line(window, "def greet():")
        bar = window.source.structure_bar
        assert bar.isVisible() and bar.current().kind == "parameters"

        def enter_parameter():
            dialog = QApplication.activeModalWidget()
            assert isinstance(dialog, QInputDialog)
            dialog.setTextValue("times")
            QTest.mouseClick(
                dialog.findChild(QDialogButtonBox).button(
                    QDialogButtonBox.StandardButton.Ok
                ),
                Qt.MouseButton.LeftButton,
            )

        QTimer.singleShot(0, enter_parameter)
        QTest.mouseClick(bar.buttons["insert"], Qt.MouseButton.LeftButton)
        select_line(window, "pass")
        add(window, "python/basics/repeat")
        field(window, "10", "times")
        select_line(window, "pass")
        add(window, "python/basics/display")
        select_line(window, "def greet(times):")
        add(window, "document/functions/greet")
        field(window, "...", "3")
        QTest.keyClick(window.source, Qt.Key.Key_Escape)
        add(window, "document/functions/greet")
        field(window, "...", "2")
        field(window, "greet", "welcome")
        assert "def welcome(times):" in window.document_page.text
        assert "welcome(3)\nwelcome(2)" in window.document_page.text
        assert not window.session.analysis.diagnostics()
        run(window)
        wait_until(lambda: window.console.toPlainText().count("Hello!") == 5)
        assert not window.runtime_panel.problem
    finally:
        window.close()


def test_new_document_asks_for_name_and_cancel_does_not_run_or_close(
    tmp_path, qt_app, monkeypatch
):
    window = Studio()
    window.show()
    qt_app.processEvents()
    try:
        page = window.document_page
        assert page.unnamed and not page.text
        original_path = page.session.project.path
        add(window, "python/basics/display")
        before = page.session.document.state
        checkpoint = page.checkpoint()
        assert checkpoint["unnamed"]
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: ("", ""))
        assert not window.save()
        window.run_hub()
        window.upload_hub()
        assert window.robot is None and not original_path.exists()
        monkeypatch.setattr(
            QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Save
        )
        assert not window.confirm_close(page)
        assert page.session.document.state is before
        destination = tmp_path / "my_first_program.py"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *a: (str(destination), "")
        )
        assert window.save()
        assert not page.unnamed and not page.dirty
        assert destination.read_text() == before.source
        assert page.session.document.state is before
        assert page.session.document.can_undo
        assert not original_path.exists()
        window.new_file()
        assert window.document_page.unnamed
        assert window.session.project.path.parent == tmp_path
        window.document_page.restore(checkpoint)
        assert window.document_page.unnamed
    finally:
        window.confirm_close = lambda *_: True
        window.close()


@pytest.mark.parametrize("language", ["en", "ru"])
def test_small_screen_navigation_keeps_every_workspace_accessible(
    tmp_path, qt_app, language
):
    window = Studio(tmp_path / "small_screen.py")
    window.resize(1280, 720)
    window.show()
    qt_app.processEvents()
    try:
        from little_tinker_rig.core.lessons import lessons_directory

        window.lessons.open(lessons_directory() / "first_drive")
        window.change_language(language)
        window.console_dock.show()
        qt_app.processEvents()
        modes = window.modes
        for index in range(modes.count()):
            item = modes.item(index)
            assert not item.isHidden()
            assert modes.viewport().rect().contains(modes.visualItemRect(item))
            assert item.toolTip() == item.text()
            assert not item.icon().isNull()
        QTest.mouseClick(
            modes.viewport(),
            Qt.MouseButton.LeftButton,
            pos=modes.visualItemRect(modes.item(3)).center(),
        )
        assert window.pages.currentIndex() == 3
        QTest.mouseClick(
            modes.viewport(),
            Qt.MouseButton.LeftButton,
            pos=modes.visualItemRect(modes.item(0)).center(),
        )
        assert window.pages.currentIndex() == 0
    finally:
        window.confirm_close = lambda *_: True
        window.close()
        window.deleteLater()
        QTest.qWait(1)
