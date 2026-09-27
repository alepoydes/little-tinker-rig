"""Inline expression editors: a text field, with a choice list when useful."""

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCompleter,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QToolTip,
    QWidget,
)

from little_tinker_rig.core.expressions import navigate
from little_tinker_rig.core.parameters import change_parameter, choices
from little_tinker_rig.core.types import known_type
from little_tinker_rig.i18n import tr


def unit_text(annotation):
    value = known_type(annotation)
    return {
        "deg": "°",
        "deg/s": tr("°/s"),
        "deg/s²": tr("°/s²"),
        "mm": tr("mm"),
        "mm/s": tr("mm/s"),
        "ms": tr("ms"),
        "s": tr("s"),
        "%": "%",
        "N": tr("N"),
        "Hz": tr("Hz"),
    }.get(value.unit if value else None, "")


class ParameterEditor(QWidget):
    applied = Signal()

    def __init__(self, view, slot):
        super().__init__(view.viewport())
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.session, self.slot = view.session, slot
        self.view = view
        self.error = ""
        options = (
            choices(self.session, slot.parameter, slot.span.start)
            if view.parameter_choices[slot.span]
            else ()
        )
        text = self.session.document.state.source[slot.span.start : slot.span.end]
        self.field = self.line_edit = QLineEdit(text, self)
        self.completer = None
        self.arrow = None
        if options:
            self.completer = QCompleter(options, self)
            self.completer.setCompletionMode(
                QCompleter.CompletionMode.UnfilteredPopupCompletion
            )
            self.completer.popup().setMinimumWidth(230)
            self.line_edit.setCompleter(self.completer)
            self.completer.activated[str].connect(self.choose)
            self.arrow = QToolButton(self)
            self.arrow.setArrowType(Qt.ArrowType.DownArrow)
            self.arrow.setFixedWidth(18)
            self.arrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.arrow.clicked.connect(self.show_choices)
        self.field.setFont(view.font())
        self.setFocusProxy(self.line_edit)
        self.setToolTip(view.parameter_tip(slot))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.field)
        if self.arrow:
            layout.addWidget(self.arrow)
        self.unit = QLabel(unit_text(slot.parameter.annotation), self.line_edit)
        self.unit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.unit.setStyleSheet("color: #68788a; background: transparent; padding: 0")
        self.unit.adjustSize()
        self.line_edit.setTextMargins(
            1, 0, self.unit.width() + 5 if self.unit.text() else 1, 0
        )
        self.line_edit.installEventFilter(self)
        self.setStyleSheet(
            "ParameterEditor { background: white; color: #203040; border: 1px solid #4e8192; border-radius: 3px; padding: 0; } QLineEdit, QToolButton { border: 0; padding: 0; background: white; color: #203040; }"
        )

    def begin(self):
        self.show()
        self.line_edit.setFocus()
        self.line_edit.selectAll()
        if self.completer:
            self.show_choices()

    def show_choices(self):
        # A completion list opens below the field; it never overlays the click
        # with the current enum row, as native menu-style combo popups can do.
        self.completer.setCompletionPrefix(self.line_edit.text())
        self.completer.complete()

    def choose(self, text):
        self.line_edit.setText(text)
        self.apply()

    def apply(self, *_):
        try:
            change_parameter(self.session, self.slot, self.line_edit.text())
        except (ValueError, SyntaxError, OSError) as error:
            self.error = str(error)
            self.setToolTip(self.error)
            QToolTip.showText(
                self.mapToGlobal(self.rect().bottomLeft()), self.error, self
            )
            self.line_edit.setFocus()
            return False
        self.applied.emit()
        self.close()
        self.view.setFocus()
        return True

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            # Closing the field during Return must not forward the same key to
            # the source view, where it would open the expression chooser.
            self.apply()
            return True
        if event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
        ):
            previous = event.key() == Qt.Key.Key_Backtab
            if self.apply():
                navigate(self.session, "previous" if previous else "next")
                self.view.setFocus()
                self.view.reveal_selection()
            return True
        if event.type() == QEvent.Type.Resize:
            self.unit.move(
                self.line_edit.width() - self.unit.width() - 3,
                max(0, (self.line_edit.height() - self.unit.height()) // 2),
            )
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.close()
            return True
        if event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(0, self, self.finish_unfocused)
        return super().eventFilter(watched, event)

    def finish_unfocused(self):
        focus = QApplication.focusWidget()
        popup = self.completer and self.completer.popup().isVisible()
        if not popup and focus is not self and not self.isAncestorOf(focus):
            self.close()

    def closeEvent(self, event):
        if self.completer:
            self.completer.popup().hide()
        super().closeEvent(event)
        self.view.viewport().update()
