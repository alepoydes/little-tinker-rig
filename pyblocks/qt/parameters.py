"""Nonmodal expression editing at a visible parameter slot."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
)

from pyblocks.core.parameters import change_parameter, choices
from pyblocks.i18n import tr

from .localization import localize


class ParameterPopup(QFrame):
    applied = Signal()

    def __init__(self, view, slot):
        super().__init__(view, Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.session, self.slot = view.session, slot
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        parameter = slot.parameter
        layout.addWidget(
            QLabel(
                parameter.name
                + (f" · {parameter.annotation}" if parameter.annotation else "")
            )
        )
        self.field = QComboBox()
        self.field.setEditable(True)
        self.field.setMinimumWidth(230)
        self.field.addItems(choices(self.session, parameter, slot.span.start))
        self.field.setCurrentText(
            self.session.document.state.source[slot.span.start : slot.span.end]
        )
        self.field.activated.connect(self.apply)
        self.field.lineEdit().returnPressed.connect(self.apply)
        row = QHBoxLayout()
        row.addWidget(self.field, 1)
        button = QToolButton()
        button.setText("✓")
        button.setToolTip("Применить · Enter")
        button.clicked.connect(self.apply)
        row.addWidget(button)
        layout.addLayout(row)
        self.error = QLabel()
        self.error.setStyleSheet("color: #a03333")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        localize(self)

    def apply(self, *_):
        try:
            change_parameter(self.session, self.slot, self.field.currentText())
        except (ValueError, SyntaxError, OSError) as error:
            self.error.setText(tr(str(error)))
            return
        self.applied.emit()
        self.close()
