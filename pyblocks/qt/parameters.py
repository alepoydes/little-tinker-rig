"""An editable combo lives over its source field; only its choices form a popup."""

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QToolTip

from pyblocks.core.parameters import change_parameter, choices
from pyblocks.i18n import tr


def unit_text(annotation):
    return {
        "deg": "°",
        "deg/s": tr("°/s"),
        "mm": tr("mm"),
        "mm/s": tr("mm/s"),
        "ms": tr("ms"),
        "s": tr("s"),
        "%": "%",
        "N": tr("N"),
    }.get(annotation, "")


class ParameterEditor(QComboBox):
    applied = Signal()

    def __init__(self, view, slot):
        super().__init__(view.viewport())
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.session, self.slot = view.session, slot
        self.error = ""
        self.setFont(view.font())
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.addItems(choices(self.session, slot.parameter, slot.span.start))
        self.setCurrentText(
            self.session.document.state.source[slot.span.start : slot.span.end]
        )
        self.setToolTip(slot.parameter.name)
        self.view().setMinimumWidth(230)
        self.unit = QLabel(unit_text(slot.parameter.annotation), self.lineEdit())
        self.unit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.unit.setStyleSheet("color: #68788a; background: transparent; padding: 0")
        self.unit.adjustSize()
        self.lineEdit().setTextMargins(
            1, 0, self.unit.width() + 5 if self.unit.text() else 1, 0
        )
        self.lineEdit().installEventFilter(self)
        self.activated.connect(self.apply)
        self.lineEdit().returnPressed.connect(self.apply)
        self.setStyleSheet(
            "QComboBox { background: white; color: #203040; border: 1px solid #4e8192; border-radius: 3px; padding: 0; } QLineEdit { border: 0; padding: 0; }"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "unit"):
            self.unit.move(
                self.lineEdit().width() - self.unit.width() - 3,
                max(0, (self.lineEdit().height() - self.unit.height()) // 2),
            )

    def begin(self):
        self.show()
        self.setFocus()
        self.lineEdit().selectAll()
        if self.count():
            self.showPopup()

    def apply(self, *_):
        try:
            change_parameter(self.session, self.slot, self.currentText())
        except (ValueError, SyntaxError, OSError) as error:
            self.error = str(error)
            self.setToolTip(self.error)
            QToolTip.showText(
                self.mapToGlobal(self.rect().bottomLeft()), self.error, self
            )
            self.lineEdit().setFocus()
            return
        self.applied.emit()
        self.close()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.hidePopup()
            self.close()
            return True
        if event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(0, self, self.finish_unfocused)
        return super().eventFilter(watched, event)

    def finish_unfocused(self):
        focus = QApplication.focusWidget()
        if (
            not self.view().isVisible()
            and focus is not self
            and not self.isAncestorOf(focus)
        ):
            self.close()
