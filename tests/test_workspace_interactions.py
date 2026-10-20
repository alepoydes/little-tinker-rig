"""Protect edits and command destinations across workspace transitions."""

from time import monotonic
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QAction, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QTabBar,
    QToolButton,
)

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


def test_live_theme_switch_keeps_invalid_draft_and_other_windows(windows):
    first = windows(MOTOR)
    second = windows("value = 3\n")
    original = first.session.document.state
    field = parameter(first, "speed", "700 +")
    editor = first.source.parameter_editor

    first.theme_actions["dark"].trigger()
    assert first.visual_theme == second.visual_theme == "dark"
    assert first.session.document.state is original
    assert first.source.parameter_editor is editor
    assert field.text() == "700 +"
    assert first.main_menu_bar.actions()
    assert first.settings.value("visualTheme") == "dark"

    second.theme_actions["light"].trigger()
    assert first.visual_theme == second.visual_theme == "light"
    assert field.text() == "700 +"
    QTest.keyClick(field, Qt.Key.Key_Escape)


def test_live_theme_switch_updates_open_python_dialog(windows):
    from little_tinker_rig.qt.dialogs import EditDialog
    from little_tinker_rig.qt.theme import DARK, LIGHT

    window = windows()
    dialog = EditDialog(window, "Draft", lambda value: value, text="x = 1\n")
    dialog.show()
    try:
        window.change_visual_theme("dark")
        assert DARK["danger"] in dialog.error.styleSheet()
        assert DARK["canvas"] in dialog.text.styleSheet()
        assert dialog.text.toPlainText() == "x = 1\n"
        window.change_visual_theme("light")
        assert LIGHT["danger"] in dialog.error.styleSheet()
        assert LIGHT["canvas"] in dialog.text.styleSheet()
    finally:
        dialog.reject()


def test_structural_canvas_stays_dark_after_theme_switch(windows):
    window = windows("print(1)\n")
    window.change_visual_theme("dark")
    QApplication.processEvents()
    viewport = window.source.viewport()
    dark = viewport.grab().toImage().pixelColor(
        viewport.width() - 12, viewport.height() - 12
    )
    assert dark.lightness() < 80

    window.change_visual_theme("light")
    QApplication.processEvents()
    light = viewport.grab().toImage().pixelColor(
        viewport.width() - 12, viewport.height() - 12
    )
    assert light.lightness() > 200


def test_header_theme_and_language_keep_brand_readable_and_actions_visible(windows):
    from little_tinker_rig.qt.theme import DARK

    window = windows()
    window.change_visual_theme("dark")
    window.change_language("ru")
    assert DARK["text"] in window.title_bar.brand.text()
    assert window.theme_toggle.accessibleName() == window.theme_toggle.toolTip()
    assert not window.theme_toggle.icon().isNull()
    window.resize(930, 620)
    QApplication.processEvents()
    assert window.run_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.stop_button.isVisible()
    window.resize(1380, 880)
    QApplication.processEvents()
    assert (
        window.run_button.toolButtonStyle()
        == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    )


def test_compact_title_keeps_document_name_and_full_title_available(windows):
    from pathlib import Path

    window = windows()
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.change_language("ru")
    window.lessons.open(Path("lessons/first_python"))
    window.set_mode(0)
    QApplication.processEvents()

    label = window.title_bar.title
    full = window.windowTitle()
    shown = label.fontMetrics().elidedText(
        label.display_text(), Qt.TextElideMode.ElideMiddle, max(0, label.width() - 16)
    )
    assert full.endswith(" — LittleTinker Rig")
    assert label.display_text().endswith(" · main.py")
    assert "LittleTinker Rig" not in shown
    assert shown.endswith("main.py")
    assert label.accessibleName() == window.title_bar.toolTip() == full

    window.set_mode(5)
    assert label.display_text().endswith("Начало")
    assert window.title_bar.toolTip() == window.windowTitle()


def test_compact_toolbar_and_search_icons_remain_named_and_usable(windows):
    window = windows()
    window.resize(930, 620)
    window.change_language("ru")
    QApplication.processEvents()

    for action in (
        window.save_action,
        window.undo_action,
        window.redo_action,
        window.upload_action,
        window.run_action,
        window.stop_action,
    ):
        button = window.main_toolbar.widgetForAction(action)
        assert button.toolTip() and button.accessibleName() == action.text()
    assert window.scratch_button.toolTip() == window.scratch_button.text()
    assert window.scratch_button.accessibleName() == window.scratch_button.text()

    window.search.setText("motor")
    search, clear = (
        next(
            button
            for button in window.search.findChildren(QToolButton)
            if (button.defaultAction() is window.search_action) is leading
        )
        for leading in (True, False)
    )
    assert search.toolTip() == search.accessibleName() == "Найти блок…"
    assert clear.toolTip() == clear.accessibleName() == "Очистить поиск блоков"
    window.source.setFocus()
    QTest.mouseClick(search, Qt.MouseButton.LeftButton)
    assert window.search.hasFocus() and window.search.selectedText() == "motor"
    QTest.mouseClick(clear, Qt.MouseButton.LeftButton)
    assert window.search.text() == ""


def test_compact_catalog_releases_editor_width_without_overriding_manual_split(windows):
    window = windows()
    QApplication.processEvents()
    assert abs(window.library_pane.width() - 320) <= 1

    window.resize(930, 620)
    QApplication.processEvents()
    assert abs(window.library_pane.width() - 270) <= 1
    assert window.documents.width() >= 590

    window.change_editor(1)
    QApplication.processEvents()
    assert not window.library_pane.isVisible()
    window.change_editor(0)
    QApplication.processEvents()
    assert abs(window.library_pane.width() - 270) <= 1

    window.program_page.moveSplitter(340, 1)
    QApplication.processEvents()
    assert window._catalog_width_manual
    assert abs(window.library_pane.width() - 340) <= 1
    window.resize(1380, 880)
    QApplication.processEvents()
    assert abs(window.library_pane.width() - 340) <= 1


def test_closing_window_cancels_queued_catalog_layout(tmp_path, qt_app):
    window = Studio(tmp_path / "plain.py")
    window.confirm_close = lambda *_: True
    assert window.close()
    qt_app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()
    QTest.qWait(10)
    window._fit_catalog_width()


def test_compact_control_keeps_sticks_visible_and_opens_motor_assignments(windows):
    from little_tinker_rig.pybricks.devices import HubInfo

    window = windows()
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.change_language("ru")
    window.set_mode(1)
    window.device_dock.show()
    window.update_hub(
        HubInfo(
            connected=True,
            monitoring=True,
            ports={"A": {"type": "motor"}, "B": {"type": "motor"}},
        )
    )
    deadline = monotonic() + 2
    while not 150 <= window.device_dock.height() <= 190 and monotonic() < deadline:
        QTest.qWait(10)
    assert window.dockWidgetArea(window.device_dock) == (
        Qt.DockWidgetArea.BottomDockWidgetArea
    )
    assert 150 <= window.device_dock.height() <= 190
    assert window.pages.height() >= 300
    assert (
        window.device_panel.monitor.visibleRegion().boundingRect().height()
        == window.device_panel.monitor.height()
    )
    table = window.controls.table
    assert table.isVisible()
    controller = window.controls.controller
    assert controller.visibleRegion().boundingRect().height() == controller.height()
    assert controller.mapToGlobal(controller.rect().topLeft()).y() < (
        table.mapToGlobal(table.rect().topLeft()).y()
    )
    assert window.controls.assignments.isVisible()
    assert window.controls.assignments.text() == "Настроить моторы ↓"
    widths = [table.columnWidth(column) for column in range(6)]
    assert max(widths) - min(widths) <= 2
    assert table.horizontalScrollBar().maximum() == 0
    outer = window.controls.parentWidget().parentWidget()
    assert outer.horizontalScrollBar().maximum() == 0
    assert outer.verticalScrollBar().value() == 0

    window.controls.assignments.click()
    QTest.qWait(50)
    assert outer.verticalScrollBar().value() > 0
    assert table.visibleRegion().boundingRect().height() == table.height()

    window.resize(1380, 880)
    QTest.qWait(90)
    assert window.dockWidgetArea(window.device_dock) == (
        Qt.DockWidgetArea.RightDockWidgetArea
    )
    widths = [table.columnWidth(column) for column in range(6)]
    assert max(widths) - min(widths) <= 2
    window.controls.target.setCurrentIndex(1)
    assert not window.controls.assignments.isVisible()


def test_narrow_toolbar_and_device_panel_keep_program_available(windows):
    from pathlib import Path

    from PySide6.QtCore import QPoint

    window = windows()
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.change_language("ru")
    window.lessons.open(Path("lessons/first_python"))
    window.set_mode(0)
    window.console_dock.show()
    window.device_dock.show()
    window.device_dock.raise_()
    QTest.qWait(90)

    assert window.width() == 800
    assert window.dockWidgetArea(window.device_dock) == (
        Qt.DockWidgetArea.BottomDockWidgetArea
    )
    assert window.source.viewport().width() >= 350
    assert window.source.viewport().height() >= 180
    assert window.hub_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert window.hub_button.accessibleName().startswith("Подключить хаб")
    assert window.lessons.progress_button.isVisible()
    for button in (window.hub_button, window.theme_toggle):
        assert button.isVisible()
        left = button.mapTo(window, QPoint()).x()
        assert left >= 0 and left + button.width() <= window.width()


def test_device_dock_keeps_user_chosen_area_after_resize(windows):
    window = windows()
    window.resize(930, 620)
    window.set_mode(1)
    QTest.qWait(60)
    assert window.dockWidgetArea(window.device_dock) == (
        Qt.DockWidgetArea.BottomDockWidgetArea
    )

    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, window.device_dock)
    QApplication.processEvents()
    assert not window._device_dock_auto
    window.resize(1380, 880)
    QTest.qWait(60)
    assert window.dockWidgetArea(window.device_dock) == (
        Qt.DockWidgetArea.LeftDockWidgetArea
    )


def test_first_console_open_keeps_compact_program_visible(windows):
    from little_tinker_rig.pybricks.devices import HubInfo

    window = windows()
    window.resize(930, 620)
    QApplication.processEvents()
    window.console_dock.show()
    window.console_dock.raise_()
    QTest.qWait(90)
    assert window.console_dock.height() <= 190
    assert window.source.viewport().height() >= 230
    assert not window.console_actions.isVisible()
    window.append_output("Ready\n")
    assert window.console_actions.isVisible()
    window.console_actions.findChild(QPushButton, "consoleClear").click()
    assert not window.console_actions.isVisible()
    assert not window.hub_input.isVisible()
    window.update_hub(HubInfo(connected=True, transport="usb"))
    assert window.hub_input.isVisible()
    window.update_hub(HubInfo())
    assert not window.hub_input.isVisible()


def test_console_request_reveals_tab_behind_device_panel(windows):
    window = windows("print(1)\n")
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.set_mode(1)
    window.set_mode(0)
    QTest.qWait(50)
    assert not window.console_dock.isVisible()
    assert not window.device_dock.visibleRegion().isEmpty()

    QTest.mouseClick(window.console_button, Qt.MouseButton.LeftButton)
    QTest.qWait(30)
    assert not window.console_dock.visibleRegion().isEmpty()
    assert window.device_dock.visibleRegion().isEmpty()

    window.device_dock.raise_()
    QTest.qWait(30)
    window.append_output("Output in the background\n")
    assert window.unread == 1
    window.console_dock.raise_()
    QTest.qWait(30)
    assert window.unread == 0

    window.device_dock.raise_()
    window.append_output("More background output\n")
    assert window.unread == 1
    QTest.mouseClick(window.console_button, Qt.MouseButton.LeftButton)
    QTest.qWait(30)
    assert not window.console_dock.visibleRegion().isEmpty()
    assert window.unread == 0

    window.device_dock.raise_()
    window.error("Failed to run")
    QTest.qWait(30)
    assert not window.console_dock.visibleRegion().isEmpty()


def test_port_monitor_request_reveals_device_tab_behind_console(windows, monkeypatch):
    window = windows()
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.set_mode(1)
    window.show_console()
    QTest.qWait(30)
    assert not window.console_dock.visibleRegion().isEmpty()

    calls = []
    monkeypatch.setattr(
        window, "_robot", lambda: SimpleNamespace(start_monitor=lambda: calls.append(1))
    )
    window.start_monitor()
    QTest.qWait(30)
    assert calls == [1]
    assert not window.device_dock.visibleRegion().isEmpty()


def test_view_menu_reveals_tabbed_panels_in_compact_window(windows):
    window = windows()
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.set_mode(1)
    window.set_mode(0)
    QTest.qWait(30)

    for dock in (window.console_dock, window.scratch_dock, window.device_dock):
        action = next(
            action
            for action in window.view_menu.actions()
            if action.text() == dock.windowTitle()
        )
        window.view_menu.aboutToShow.emit()
        assert not action.isChecked()
        action.trigger()
        QTest.qWait(30)
        assert not dock.visibleRegion().isEmpty()
        window.view_menu.aboutToShow.emit()
        assert action.isChecked()

    window.dock_view_actions[window.device_dock].trigger()
    QTest.qWait(30)
    assert window.device_dock.visibleRegion().isEmpty()

    window.change_language("ru")
    for dock in (window.console_dock, window.scratch_dock, window.device_dock):
        assert window.dock_view_actions[dock].text() == dock.windowTitle()
    window.set_mode(2)
    assert not window.dock_view_actions[window.scratch_dock].isEnabled()
    window.set_mode(0)
    assert window.dock_view_actions[window.scratch_dock].isEnabled()


def test_dock_and_tab_icon_controls_explain_their_actions(windows, tmp_path):
    window = windows()
    window.set_mode(1)
    window.change_language("ru")
    QTest.qWait(30)
    dock = window.device_dock
    floating = dock.findChild(QAbstractButton, "qt_dockwidget_floatbutton")
    close_dock = dock.findChild(QAbstractButton, "qt_dockwidget_closebutton")
    assert floating.toolTip() == "Открепить панель: Хаб и устройства"
    assert floating.accessibleName() == floating.toolTip()
    assert close_dock.toolTip() == "Скрыть панель: Хаб и устройства"
    assert close_dock.accessibleName() == close_dock.toolTip()

    bar = window.documents.tabBar()
    close_tab = bar.tabButton(0, QTabBar.ButtonPosition.RightSide)
    assert close_tab.toolTip() == "Закрыть вкладку: program_0.py"
    assert close_tab.accessibleName() == close_tab.toolTip()

    dock.setFloating(True)
    try:
        QTest.qWait(30)
        assert floating.toolTip() == "Закрепить панель: Хаб и устройства"
        assert floating.accessibleName() == floating.toolTip()
    finally:
        dock.setFloating(False)

    second = tmp_path / "second.py"
    second.write_text("value = 2\n", encoding="utf-8")
    window.open_document(second)
    close_second = bar.tabButton(1, QTabBar.ButtonPosition.RightSide)
    assert close_second.toolTip() == "Закрыть вкладку: second.py"
    window.change_language("en")
    assert floating.toolTip() == "Detach panel: Hub and devices"
    assert close_second.accessibleName() == "Close tab: second.py"
    QTest.mouseClick(close_second, Qt.MouseButton.LeftButton)
    assert window.documents.count() == 1


def test_dock_context_menu_selects_visible_tab_without_empty_task_panel(windows):
    from pathlib import Path

    window = windows()
    window.setMinimumWidth(0)
    window.resize(800, 620)
    window.set_mode(1)
    window.set_mode(0)
    popup = window.createPopupMenu()
    try:
        assert window.lessons.dock.toggleViewAction() not in popup.actions()
        assert window.lessons.guidance not in popup.actions()
        console_action = next(
            action
            for action in popup.actions()
            if action.text() == window.console_dock.windowTitle()
        )
        assert console_action is window.dock_view_actions[window.console_dock]
        console_action.trigger()
        QTest.qWait(30)
        assert not window.console_dock.visibleRegion().isEmpty()
    finally:
        popup.deleteLater()

    window.lessons.open(Path("lessons/first_python"))
    popup = window.createPopupMenu()
    try:
        assert window.lessons.guidance in popup.actions()
        assert window.lessons.dock.toggleViewAction() not in popup.actions()
    finally:
        popup.deleteLater()


def test_sequence_bar_keeps_program_source_clear_of_line_numbers(windows):
    from PySide6.QtCore import QPoint

    window = windows("result = max(1, 2)\n")
    window.resize(930, 620)
    QApplication.processEvents()
    view = window.source

    def clear_of_numbers():
        assert view.viewportMargins().left() == 40
        assert view.gutter.geometry().right() < view.viewport().geometry().left()

    clear_of_numbers()
    rect = view._rect(1, 14)
    view.structure_bar.activate(QPoint(int(rect.left()) + 2, int(rect.center().y())))
    assert view.structure_bar.isVisible()
    clear_of_numbers()
    window.change_visual_theme("dark")
    QApplication.processEvents()
    clear_of_numbers()
    view.structure_bar.hide()
    clear_of_numbers()
    window.change_editor(1)
    window.change_editor(0)
    QApplication.processEvents()
    clear_of_numbers()


def test_console_uses_compact_height_after_hidden_window_resize(windows):
    window = windows()
    window.resize(1380, 880)
    QApplication.processEvents()
    window.console_dock.show()
    QTest.qWait(90)
    assert window.console_dock.height() <= 240
    window.console_dock.hide()

    window.resize(930, 620)
    QApplication.processEvents()
    window.console_dock.show()
    window.console_dock.raise_()
    QTest.qWait(90)
    assert window.console_dock.height() <= 190
    assert window.source.viewport().height() >= 230


def test_console_preserves_a_user_chosen_height(windows):
    window = windows()
    window.resize(1380, 880)
    QApplication.processEvents()
    window.console_dock.show()
    QTest.qWait(90)
    QTest.mousePress(window.console.viewport(), Qt.MouseButton.LeftButton)
    window.resizeDocks([window.console_dock], [300], Qt.Orientation.Vertical)
    QApplication.processEvents()
    QTest.mouseRelease(window.console.viewport(), Qt.MouseButton.LeftButton)
    assert window.console_dock.height() >= 280
    window.console_dock.hide()
    window.resize(930, 620)
    QApplication.processEvents()
    window.console_dock.show()
    QTest.qWait(90)
    assert window.console_dock.height() >= 220


def test_scratch_history_follows_fragments_across_moves_and_removal(windows):
    from little_tinker_rig.core.edit import Target
    from little_tinker_rig.core.transfer import Transfer

    window = windows()
    session = window.session
    for _ in range(2):
        session.set_scratch(None, "value = 1\n")
    window.scratch_dock.show()
    window.refresh_views()
    first, second = window.scratch.cells
    for cell in (first, second):
        cell.change_mode(True)
    Transfer.capture(session, index=0).to_scratch(2)
    window.refresh_views()
    assert window.scratch.cells == [second, first]
    assert session.editor.undo()
    window.refresh_views()
    assert window.scratch.cells == [first, second]
    for cell, text in ((first, "first = 10\n"), (second, "second = 20\n")):
        cell.code.moveCursor(QTextCursor.MoveOperation.End)
        cell.code.insertPlainText(text)
    Transfer.capture(session, index=0).to_program(
        Target(session.document.syntax.suites[0], 1)
    )
    window.refresh_views()
    assert window.scratch.cells == [second]
    assert second.index == second.source.scratch_index == 0
    second.code.undo()
    assert window.scratch.cells == [first, second]
    assert first.code_active and second.code_active
    second.code.undo()
    assert session.document.state.scratch == ("value = 1\nfirst = 10\n", "value = 1\n")
    session.set_scratch(1, "value = 2\n")
    window.refresh_views()
    assert window.scratch.cells == [first, second]
    second.code.undo()
    assert session.document.state.scratch[1] == "value = 1\n"


@pytest.mark.parametrize("to_program", [True, False])
def test_python_undo_restores_whole_transfer_and_survives_save(windows, to_program):
    from little_tinker_rig.core.edit import Target
    from little_tinker_rig.core.session import Session
    from little_tinker_rig.core.transfer import Transfer

    window = windows("main = 1\n" if to_program else "main = 1\nimportant = 42\n")
    session = window.session
    if to_program:
        session.set_scratch(None, "important = 42\n")
    before = session.document.state
    if to_program:
        Transfer.capture(session, index=0).to_program(
            Target(session.document.syntax.suites[0], 1)
        )
    else:
        session.editor.selection = session.document.syntax.tree.body[-1]
        Transfer.capture(session).to_scratch(0)
    after = session.document.state
    window.refresh_views()
    window.source.setFocus()
    window.change_editor(1)
    QTest.keyClick(window.code, Qt.Key.Key_Z, CTRL)
    assert window.document_page.text == before.source
    assert session.document.state.scratch == before.scratch
    window.save()
    reopened = Session(session.project.path)
    assert reopened.document.state.source == before.source
    assert reopened.document.state.scratch == before.scratch
    QTest.keyClick(window.code, Qt.Key.Key_Z, CTRL | Qt.KeyboardModifier.ShiftModifier)
    assert window.document_page.text == after.source
    assert session.document.state.scratch == after.scratch


def test_unfinished_python_and_scratch_share_history(windows):
    window = windows()
    window.change_editor(1)
    window.code.moveCursor(QTextCursor.MoveOperation.End)
    QTest.keyClicks(window.code, "if value:")
    draft = window.document_page.text
    window.session.set_scratch(None, "scratch = 2\n")
    window.refresh_views()
    window.undo_action.trigger()
    assert not window.session.document.state.scratch
    assert window.document_page.text == draft
    window.undo_action.trigger()
    assert window.document_page.text == "x = 1\n"
    window.redo_action.trigger()
    assert window.document_page.text == draft
    window.save()
    assert window.session.project.path.read_text() == draft


def test_modal_variant_dialog_routes_stop_to_its_own_window(windows, monkeypatch):
    from little_tinker_rig.pybricks.devices import HubInfo

    window, other = windows(MOTOR), windows(MOTOR)
    stopped = []
    for owner in (window, other):
        monkeypatch.setattr(
            owner,
            "robot",
            SimpleNamespace(
                stop_program=lambda owner=owner: stopped.append(owner),
                close=lambda: None,
            ),
        )
        owner.update_hub(HubInfo(connected=True, running=True))
    window.activateWindow()
    window.session.editor.select(window.document_page.text.index("motor ="))
    window.source.refresh_source()

    def stop():
        dialog = QApplication.activeModalWidget()
        QTest.keyClick(dialog, Qt.Key.Key_F6)
        dialog.reject()

    QTimer.singleShot(10, stop)
    window.source.edit_variant()
    assert stopped == [window]


def test_scratch_custom_block_keeps_its_own_import_alias(windows, monkeypatch):
    from little_tinker_rig.core.session import Session
    from little_tinker_rig.core.snippets import load_module

    window = windows("from math import sqrt as calculate\nmain = 1\n")
    window.session.set_scratch(
        None, "from cmath import sqrt as calculate\nresult = calculate(-1)\n"
    )
    window.scratch_dock.show()
    window.refresh_views()
    cell = window.scratch.cells[0]
    cell.change_mode(True)
    cursor = cell.code.document().find("result = calculate(-1)")
    cell.code.setTextCursor(cursor)
    captured = []
    monkeypatch.setattr(window.block_editor, "create", captured.append)
    window.create_block_from_selection()
    snippet = load_module(captured[0], "review/custom", "1")[0]
    target = Session(window.session.project.path.with_name("custom.py"))
    target.insert_snippet(snippet, {})
    namespace = {}
    exec(target.document.state.source, namespace)
    assert namespace["result"] == 1j


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
            run_file=lambda path, sources: executed.append(sources[path])
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
    assert "wheel.run(900)" in window.session.project.path.read_text()
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


def test_stop_and_disconnect_bypass_invalid_edits(windows, monkeypatch):
    from PySide6.QtWidgets import QToolBar

    from little_tinker_rig.pybricks.devices import HubInfo

    window = windows(MOTOR)
    calls = []
    robot = SimpleNamespace(
        stop_program=lambda: calls.append("stop"),
        disconnect_hub=lambda: calls.append("disconnect"),
        close=lambda: None,
    )
    monkeypatch.setattr(window, "robot", robot)
    window.update_hub(HubInfo(connected=True, running=True))
    field = parameter(window, "speed", "500 +")
    QTest.keyClick(field, Qt.Key.Key_F6)
    toolbar = window.findChild(QToolBar, "programTools")
    QTest.mouseClick(
        toolbar.widgetForAction(window.stop_action), Qt.MouseButton.LeftButton
    )
    disconnect = next(
        a for a in window.findChildren(QAction) if a.text() == "Disconnect"
    )
    disconnect.trigger()
    assert calls == ["stop", "stop", "disconnect"]
    assert field.text() == "500 +" and field.isVisible()
    assert "motor.run(500)" in window.document_page.text
    QTest.keyClick(field, Qt.Key.Key_Escape)


def test_scratch_retains_editors_across_tabs_and_routes_commands(
    windows, tmp_path, monkeypatch
):
    window = windows("main_value = 1\n")
    owner = window.document_page
    window.change_editor(1)
    window.code.selectAll()
    window.session.set_scratch(None, "scratch_value = 2\n")
    window.refresh_views()
    window.scratch_dock.show()
    cell = window.scratch.cells[0]
    cell.source.setFocus()
    QApplication.processEvents()
    assert window.library_pane.isVisible()
    cell.change_mode(True)
    cell.code.moveCursor(QTextCursor.MoveOperation.End)
    cell.code.insertPlainText("print(missing_name)\n")
    assert not window.library_pane.isVisible()
    other = tmp_path / "other.py"
    other.write_text("other = 3\n", encoding="utf-8")
    window.open_document(other)
    assert not window.scratch.cells
    window.documents.setCurrentWidget(owner)
    assert window.scratch.cells[0] is cell
    assert cell.code_active and cell.code.document().isUndoAvailable()
    cell.code.setFocus()
    window.show_diagnostics()
    assert "missing_name" in window.console.toPlainText()
    assert "No unknown names" not in window.console.toPlainText()
    QTest.keyClick(cell.code, Qt.Key.Key_Z, CTRL)
    assert cell.text == "scratch_value = 2\n"
    cell.code.selectAll()
    definitions = []
    monkeypatch.setattr(window.block_editor, "create", definitions.append)
    window.create_block_action.trigger()
    assert "scratch_value = 2" in definitions[0]
    assert "main_value" not in definitions[0]
    window.set_mode(0)
    window.documents.setCurrentIndex(1)
    assert window.document_page.text == "other = 3\n"


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


def test_compact_scratch_relayout_preserves_invalid_parameter(windows):
    window = windows()
    window.resize(1380, 880)
    window.session.set_scratch(None, MOTOR)
    window.refresh_views()
    window.scratch_dock.show()
    window.scratch_dock.raise_()
    QApplication.processEvents()
    cell = window.scratch.cells[0]
    field = parameter(window, "speed", "1 +", view=cell.source)
    window.resize(930, 620)
    for _ in range(5):
        QApplication.processEvents()
    assert window.dockWidgetArea(window.scratch_dock) == (
        Qt.DockWidgetArea.BottomDockWidgetArea
    )
    assert field.isVisible() and field.text() == "1 +"
    assert cell.source.parameter_editor.line_edit is field
    QTest.keyClick(field, Qt.Key.Key_Escape)


def test_long_block_line_has_visible_horizontal_navigation(windows):
    window = windows('print("' + "x" * 180 + '")\n')
    window.resize(930, 620)
    for _ in range(4):
        QApplication.processEvents()
    page = window.document_page
    scrollbar = page.source.horizontalScrollBar()
    assert scrollbar.maximum() > 0
    assert page.scroll_right.isVisible() and page.scroll_right.isEnabled()
    assert page.scroll_left.isVisible() and not page.scroll_left.isEnabled()
    before = page.session.document.state
    QTest.mouseClick(page.scroll_right, Qt.MouseButton.LeftButton)
    assert scrollbar.value() > 0
    assert page.scroll_left.isEnabled()
    QTest.mouseClick(page.scroll_left, Qt.MouseButton.LeftButton)
    assert scrollbar.value() == 0
    page.scroll_right.setFocus()
    QTest.keyClick(page.scroll_right, Qt.Key.Key_Space)
    assert scrollbar.value() > 0
    assert page.session.document.state is before
    page.change_mode(1)
    assert page.scroll_left.isHidden() and page.scroll_right.isHidden()
    page.change_mode(0)
    assert page.scroll_right.isVisible()
    window.change_language("ru")
    assert page.scroll_right.toolTip() == "Прокрутить программу вправо"


def test_horizontal_navigation_keeps_invalid_parameter_visible(windows):
    window = windows(MOTOR + "# " + "x" * 180 + "\n")
    window.resize(930, 620)
    for _ in range(4):
        QApplication.processEvents()
    field = parameter(window, "speed", "1 +")
    scrollbar = window.source.horizontalScrollBar()
    before = scrollbar.value()
    QTest.mouseClick(window.document_page.scroll_right, Qt.MouseButton.LeftButton)
    assert scrollbar.value() == before
    assert field.isVisible() and field.text() == "1 +"
    QTest.keyClick(field, Qt.Key.Key_Escape)


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
    assert window.help_page.find_field.hasFocus()


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


def test_save_conflict_failed_reload_keeps_editable_document(windows):
    window = windows()
    page = window.document_page
    path = page.session.project.path
    page.session.editor.commit("edited = 2\n")
    path.write_bytes(b"\xff")

    def reload_from_dialog():
        dialog = QApplication.activeModalWidget()
        button = next(
            item
            for item in dialog.buttons()
            if item.text().replace("&", "") == "Reload from disk"
        )
        button.click()

    QTimer.singleShot(0, reload_from_dialog)
    assert window.save_document(page) is False
    assert "utf-8" in window.last_error
    assert page.text == "edited = 2\n" and page.dirty
    assert path.read_bytes() == b"\xff"


def test_save_failure_reports_error_and_keeps_document(windows, monkeypatch):
    window = windows()
    page = window.document_page
    path = page.session.project.path
    page.session.editor.commit("edited = 2\n")

    def fail_save():
        raise OSError("disk full")

    monkeypatch.setattr(page, "save", fail_save)

    assert window.save_document(page) is False
    assert "disk full" in window.last_error
    assert page.text == "edited = 2\n" and page.dirty
    assert path.read_text(encoding="utf-8") == "x = 1\n"
    window.last_error = ""
    window.save_action.trigger()
    assert "disk full" in window.last_error


def test_save_as_failure_reports_error_without_retargeting(
    windows, tmp_path, monkeypatch
):
    from little_tinker_rig.core.project import Project

    window = windows()
    page = window.document_page
    original = page.session.project.path
    destination = tmp_path / "copy.py"
    page.session.editor.commit("edited = 2\n")
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(destination), "")
    )

    def fail_save(_project):
        raise OSError("disk full")

    monkeypatch.setattr(Project, "save", fail_save)

    assert window.save_as(page=page) is False
    assert "disk full" in window.last_error
    assert page.session.project.path == original
    assert page.text == "edited = 2\n" and page.dirty
    assert not destination.exists()


def test_open_file_reports_bad_document_and_opens_remaining_files(
    windows, tmp_path, monkeypatch
):
    window = windows()
    damaged = tmp_path / "damaged.py"
    damaged.write_bytes(b"\xff")
    valid = tmp_path / "valid.py"
    valid.write_text("value = 3\n", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        lambda *a, **k: ([str(damaged), str(valid)], ""),
    )

    window.open_file()
    assert "damaged.py" in window.last_error
    assert window.document_page.session.project.path == valid
    assert window.document_page.text == "value = 3\n"


def test_reload_failure_reports_error_and_preserves_open_document(windows, monkeypatch):
    window = windows()
    page = window.document_page
    page.session.editor.commit("edited = 2\n")
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )

    def fail_reload():
        raise OSError("reload failed")

    monkeypatch.setattr(page, "reload", fail_reload)
    window.reload_document()
    assert "reload failed" in window.last_error
    assert page.text == "edited = 2\n" and page.dirty


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
        trigger.setFocus()
        QTest.mousePress(
            trigger, Qt.MouseButton.LeftButton, pos=trigger.rect().center()
        )
        controls.sample()
        assert commands[-1][0][2] > 0
        QTest.mouseRelease(
            trigger, Qt.MouseButton.LeftButton, pos=trigger.rect().center()
        )
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
