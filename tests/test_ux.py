import ast
from unittest.mock import patch

import pytest

from pyblocks.core import edit
from pyblocks.core.parameters import change_parameter, default_bindings, slots
from pyblocks.core.session import Session
from pyblocks.i18n import set_language


def discard_window(window):
    from PySide6.QtWidgets import QMessageBox

    with patch.object(
        QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard
    ):
        window.close()


def test_parameter_slots_replace_whole_expressions_and_reject_stale_revision(tmp_path):
    path = tmp_path / "main.py"
    path.write_text("if distance < 120 and ready:\n    move(100 + offset)\n")
    session = Session(path)
    fields = slots(session)
    condition = next(slot for slot in fields if slot.parameter.name == "condition")
    argument = next(slot for slot in fields if slot.parameter.name == "argument 1")
    assert (
        session.document.state.source[argument.span.start : argument.span.end]
        == "100 + offset"
    )
    change_parameter(session, argument, "250 - offset")
    assert (
        ast.unparse(session.document.syntax.tree.body[0].body[0].value.args[0])
        == "250 - offset"
    )
    with pytest.raises(ValueError, match="changed"):
        change_parameter(session, condition, "False")
    before = session.document.state
    with pytest.raises(SyntaxError):
        change_parameter(session, slots(session)[0], "x +")
    assert session.document.state == before


def test_library_defaults_choose_existing_devices_and_fresh_names(tmp_path):
    path = tmp_path / "main.py"
    path.write_text(
        "from pybricks.pupdevices import Motor\nfrom pybricks.parameters import Port\nleft = Motor(Port.A)\nmotor = Motor(Port.B)\n"
    )
    session = Session(path)
    snippet = next(s for s in session.snippets if s.identity.endswith("/run_motor"))
    bindings = default_bindings(session, snippet, len(session.document.state.source))
    assert bindings["motor"] in {"left", "motor"}
    create = next(s for s in session.snippets if s.identity.endswith("/create_motor"))
    assert default_bindings(session, create)["name"] == "motor_2"
    assert all(p.default is not None for s in session.snippets for p in s.parameters)
    drive = next(s for s in session.snippets if s.identity.endswith("/create_drive"))
    bindings = default_bindings(session, drive, len(session.document.state.source))
    assert bindings["left"] == "left" and bindings["right"] == "motor"


def test_documents_and_languages_preserve_text_and_undo(tmp_path, qt_app):
    from pyblocks.qt.app import Studio

    first, second = tmp_path / "one.py", tmp_path / "two.py"
    first.write_text("first = 1\n")
    second.write_text("second = 2\n")
    window = Studio(first)
    window.show()
    try:
        one = window.document_page
        window.change_editor(1)
        window.code.insertPlainText("# черновик\n")
        draft = window.code.toPlainText()
        window.open_document(second)
        two = window.document_page
        assert one is not two and window.documents.count() == 2
        window.open_document(first)
        assert window.document_page is one and window.documents.count() == 2
        set_language("en")
        window.retranslate()
        assert window.modes.item(0).text() == "Program"
        assert window.run_action.text() == "Run"
        assert window.code.toPlainText() == draft
        assert window.code_active
        window.undo_action.trigger()
        assert window.code.toPlainText() == "first = 1\n"
        window.documents.setCurrentWidget(two)
        window.session.editor.commit("second = 10")
        window.refresh_views()
        window.undo_action.trigger()
        assert window.session.document.state.source == "second = 2\n"
        set_language("ru")
        window.retranslate()
        assert window.run_action.text() == "Запустить"
        assert window.documents.tabText(0) == "one.py"
    finally:
        set_language("ru")
        discard_window(window)


def test_short_mode_list_scrolls_without_switching_and_keeps_named_icons(qt_app):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

    from pyblocks.qt.localization import localize
    from pyblocks.qt.navigation import ModeList

    modes = ModeList()
    modes.add_mode("lesson", "Lesson")
    modes.add_mode("assembly", "Assembly")
    width = modes.sizeHint().width()
    font = modes.font()
    font.setPointSize(18)
    modes.setFont(font)
    set_language("ru")
    localize(modes)
    assert modes.sizeHint().width() == width
    modes.resize(modes.sizeHint().width(), 140)
    modes.show()
    qt_app.processEvents()
    try:
        before = modes.currentRow()
        point = modes.viewport().rect().center()
        wheel = QWheelEvent(
            QPointF(point),
            QPointF(modes.viewport().mapToGlobal(point)),
            QPoint(),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        qt_app.sendEvent(modes.viewport(), wheel)
        assert modes.verticalScrollBar().value() > 0
        assert modes.currentRow() == before
        for row in range(modes.count()):
            item = modes.item(row)
            modes.scrollToItem(item)
            qt_app.processEvents()
            rect = modes.visualItemRect(item)
            assert modes.viewport().rect().contains(rect)
            QTest.mouseClick(
                modes.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
            )
            assert modes.currentRow() == row
            option = QStyleOptionViewItem()
            option.initFrom(modes)
            option.rect = rect
            option.decorationSize = modes.iconSize()
            option.state |= QStyle.StateFlag.State_Selected
            modes.itemDelegate().initStyleOption(option, modes.model().index(row, 0))
            icon_rect = modes.style().subElementRect(
                QStyle.SubElement.SE_ItemViewItemDecoration, option, modes
            )
            assert rect.contains(icon_rect)
            assert not option.text
            assert item.toolTip() == item.text()
        modes.set_mode_visible(4, False)
        modes.set_mode_visible(5, False)
        modes.setCurrentRow(0)
        qt_app.processEvents()
        QTest.keyClick(modes, Qt.Key.Key_End)
        assert modes.currentRow() == 3
    finally:
        modes.close()
        modes.deleteLater()


def test_library_drop_has_preview_and_inserts_defaults_without_dialog(tmp_path, qt_app):
    from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
    from PySide6.QtWidgets import QApplication

    from pyblocks.qt.app import Studio

    path = tmp_path / "drop.py"
    path.write_text("i = 5\n")
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    try:
        view = window.source
        data = QMimeData()
        data.setData("application/x-pyblocks-snippet", b"python/basics/repeat")
        point = QPoint(40, 55)
        enter = QDragEnterEvent(
            point,
            Qt.DropAction.CopyAction,
            data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(view.viewport(), enter)
        move = QDragMoveEvent(
            point,
            Qt.DropAction.CopyAction,
            data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(view.viewport(), move)
        assert move.isAccepted() and view.drop_target is not None
        assert ast.parse(view.drop_preview()).body[0].iter.args[0].value == 10
        assert ast.parse(view.drop_preview()).body[0].target.id == "i_2"
        expected = ast.parse(
            edit.insert(
                window.session.document.syntax, view.drop_target, view.drop_preview()
            )
        )
        drop = QDropEvent(
            QPointF(point),
            Qt.DropAction.CopyAction,
            data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(view.viewport(), drop)
        assert drop.isAccepted()
        assert QApplication.activeModalWidget() is None
        assert ast.dump(window.session.document.syntax.tree) == ast.dump(expected)
        assert view.drop_target is None
        window.session.editor.undo()
        window.refresh_views()
    finally:
        discard_window(window)


def test_parameter_combo_opens_in_place_and_validates_before_commit(tmp_path, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from pyblocks.qt.app import Studio

    path = tmp_path / "motor.py"
    path.write_text(
        "from pybricks.pupdevices import Motor\nfrom pybricks.parameters import Port\nmotor = Motor(Port.A)\nmotor.run(500)\n"
    )
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    try:
        slot = next(
            slot
            for slot in window.source.parameter_slots
            if slot.parameter.name == "speed"
        )
        rect = window.source.parameter_rect(slot)
        QTest.mouseClick(
            window.source.viewport(),
            Qt.MouseButton.LeftButton,
            pos=rect.center().toPoint(),
        )
        qt_app.processEvents()
        popup = window.source.parameter_editor
        assert popup.isVisible() and QApplication.activeModalWidget() is None
        assert popup.parent() is window.source.viewport()
        assert popup.completer.popup().isVisible()
        assert popup.unit.text() == "°/s"
        assert popup.line_edit.text() == "500"
        popup.line_edit.setText("300 +")
        popup.apply()
        assert popup.isVisible() and popup.error
        assert window.session.document.state.source.endswith("motor.run(500)\n")
        popup.line_edit.setText("300")
        QTest.keyClick(popup.line_edit, Qt.Key.Key_Return)
        qt_app.processEvents()
        assert window.session.document.state.source.endswith("motor.run(300)\n")
        assert window.source.expression_popup is None
        assert (
            window.session.document.syntax.text(window.session.editor.selection)
            == "300"
        )
        assert window.whole_blocks.isVisible()
        QTest.mouseClick(window.whole_blocks, Qt.MouseButton.LeftButton)
        assert not isinstance(window.session.editor.selection, ast.expr)
        assert not window.whole_blocks.isVisible()
        assert window.source.viewport().cursor().shape() != Qt.CursorShape.IBeamCursor
        QTest.keyClick(window.source, Qt.Key.Key_Delete)
        assert "motor.run" not in window.session.document.state.source
        window.session.editor.undo()
        assert window.session.document.state.source.endswith("motor.run(300)\n")
        window.session.editor.undo()
        window.refresh_views()
    finally:
        discard_window(window)


def test_parameter_replacements_preserve_grouping_and_all_occurrences(tmp_path):
    from pyblocks.core.snippets import load_module

    path = tmp_path / "formula.py"
    path.write_text("result = 2 * 2\n")
    session = Session(path)
    session.snippets = load_module(
        "def square(value=2):\n    return value * value\n", "math", "1.0"
    )
    fields = [slot for slot in slots(session) if slot.parameter.name == "value"]
    assert len(fields) == 2
    change_parameter(session, fields[0], "3 + 4")
    namespace = {}
    exec(session.document.state.source, namespace)
    assert namespace["result"] == 49
    session.editor.undo()
    assert session.document.state.source == "result = 2 * 2\n"


def test_insertion_destinations_respect_declarations_and_loop_context():
    from pyblocks.core.syntax import Syntax

    syntax = Syntax("def update():\n    global value\n    print(value)\n")
    function = syntax.tree.body[0]
    candidates = tuple(edit.insertion_targets(syntax, "print(value)"))
    assert [t.index for t in candidates if t.suite.owner is function] == [1, 2]
    assert not tuple(edit.insertion_targets(syntax, "break"))


@pytest.mark.parametrize(
    "encoding, cookie, text, existing",
    [
        ("latin-1", "latin-1", "café", False),
        ("cp1251", "cp1251", "Привет", True),
        ("utf-8-sig", "utf-8", "Привет", False),
    ],
)
def test_save_as_preserves_source_encoding(
    tmp_path, qt_app, monkeypatch, encoding, cookie, text, existing
):
    from PySide6.QtWidgets import QFileDialog

    from pyblocks.core.project import Project
    from pyblocks.qt.app import Studio

    path, destination = tmp_path / "original.py", tmp_path / "copy.py"
    source = f'# coding: {cookie}\nmessage = "{text}"\n'
    original = source.encode(encoding)
    path.write_bytes(original)
    if existing:
        destination.write_bytes(
            '# coding: latin-1\nmessage = "old"\n'.encode("latin-1")
        )
    window = Studio(path)
    try:
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *args: (str(destination), "")
        )
        assert window.save_as()
        assert destination.read_bytes() == original
        assert Project(destination).document.state.source == source
        assert path.read_bytes() == original
        # The newly selected file also retains its encoding on subsequent saves.
        window.session.editor.commit(source.replace(text, text + "!"))
        window.save()
        assert Project(destination).document.state.source == source.replace(
            text, text + "!"
        )
    finally:
        discard_window(window)


def test_closing_invalid_draft_and_save_as_preserve_other_documents(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from pyblocks.qt.app import Studio

    first, second = tmp_path / "one.py", tmp_path / "two.py"
    first.write_text("value = 1\n")
    second.write_text("value = 2\n")
    window = Studio(first)
    try:
        one = window.document_page
        window.open_document(second)
        two = window.document_page
        window.change_editor(1)
        window.code.setPlainText("value =")
        window.editor_actions[0].trigger()
        assert window.code_active and window.editor_actions[1].isChecked()
        assert two.mode_actions[1].isChecked()
        for answer in (QMessageBox.StandardButton.Cancel,):
            monkeypatch.setattr(
                QMessageBox, "question", lambda *args, answer=answer: answer
            )
            window.close_document(1)
            assert window.documents.count() == 2
            assert window.code.toPlainText() == "value ="
            assert second.read_text() == "value = 2\n"
        monkeypatch.setattr(
            QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Discard
        )
        window.close_document(1)
        assert window.document_page is one
        window.open_document(second)
        window.session.editor.commit("value = 3\n")
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *args: (str(first), "Python (*.py)")
        )
        with pytest.raises(ValueError):
            window.save_as()
        assert first.read_text() == "value = 1\n"
        assert second.read_text() == "value = 2\n"
        window.new_file()
        assert not window.document_page.dirty
    finally:
        discard_window(window)


def test_selection_pulses_across_the_block_and_never_exposes_text_cursor(
    tmp_path, qt_app
):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest

    from pyblocks.qt.app import Studio

    path = tmp_path / "block.py"
    path.write_text("print(42)\nif True:\n    if True:\n        print(12)\n")
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    try:
        view = window.source
        view.pulse.pause()
        point = QPoint(view.viewport().width() - 50, view.cursorRect().center().y())
        QTest.mouseMove(view.viewport(), point)
        assert view.viewport().cursor().shape() != Qt.CursorShape.IBeamCursor
        assert view.cursorWidth() == 0
        colors = []
        for time in (0, 1400):
            view.pulse.setCurrentTime(time)
            colors.append(view.viewport().grab().toImage().pixelColor(point))
        assert sum(colors[1].getRgb()[:3]) < sum(colors[0].getRgb()[:3])
        assert view.toPlainText() == window.session.document.state.source
        window.session.editor.selection = window.session.document.syntax.tree
        view.hover = None
        view.refresh_source()
        background = view.viewport().grab().toImage()
        nested = QTextCursor(view.document().findBlockByNumber(3))
        tail = QPoint(point.x(), view.cursorRect(nested).center().y())
        assert background.pixelColor(point) == background.pixelColor(tail)
    finally:
        discard_window(window)


def test_translated_help_and_device_panel_keep_port_values(tmp_path, qt_app):
    from PySide6.QtWidgets import QDialogButtonBox

    from pyblocks.pybricks.devices import HubInfo
    from pyblocks.qt.app import Studio
    from pyblocks.qt.device import ConnectDialog

    path = tmp_path / "robot.py"
    path.write_text('print("Привет")\n')
    window = Studio(path)
    try:
        window.update_hub(
            HubInfo(
                connected=True,
                transport="virtual",
                monitoring=True,
                ports={"C": {"type": "color", "reflection": 37}},
            )
        )
        window.help_page.show_page("robotics.md")
        for language, title, label in (
            ("en", "Robots and controls", "Reflection:"),
            ("ru", "Робот и органы управления", "Отражение:"),
        ):
            set_language(language)
            window.retranslate()
            assert title in window.help_page.browser.toPlainText()
            assert label in window.device_panel.rows["C"][1].text()
            assert "37" in window.device_panel.rows["C"][1].text()
            dialog = ConnectDialog(window)
            cancel = dialog.findChild(QDialogButtonBox).button(
                QDialogButtonBox.StandardButton.Cancel
            )
            assert cancel.text() == ("Cancel" if language == "en" else "Отмена")
            dialog.close()
        assert window.session.document.state.source == 'print("Привет")\n'
    finally:
        set_language("ru")
        discard_window(window)
