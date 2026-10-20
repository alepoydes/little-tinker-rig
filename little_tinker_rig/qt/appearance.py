"""Editable source values with localized semantic choices."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QComboBox

from little_tinker_rig.core.presentation import ICONS, PALETTE
from little_tinker_rig.i18n import N_, tr

ROLE_LABELS = {
    "action": N_("Actions"),
    "loop": N_("Loops"),
    "control": N_("Control flow"),
    "value": N_("Values"),
    "state": N_("Variables and state"),
    "definition": N_("Definitions"),
    "snippet": N_("Compound blocks"),
    "placeholder": N_("Empty fields"),
    "warning": N_("Warnings"),
}


class AppearanceChoice(QComboBox):
    changed = Signal(str)

    def __init__(self, *, color=False):
        super().__init__()
        self.color = color
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMinimumContentsLength(9)
        self.setMinimumWidth(135 if color else 165)
        self.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.labels = (
            ROLE_LABELS
            if color
            else {
                **{symbol: ROLE_LABELS[role] for role, symbol in ICONS.items()},
                "⚙": N_("Devices"),
                "↻": N_("Motor rotation"),
                "⏱": N_("Time"),
                "◉": N_("Sensors"),
                "➜": N_("Movement"),
                "⌨": N_("Keyboard"),
            }
        )
        for value in self.labels:
            if color:
                swatch = QPixmap(18, 18)
                swatch.fill(QColor(PALETTE[value]))
                self.addItem(QIcon(swatch), "", value)
            else:
                self.addItem("", value)
        self.retranslate()
        self.activated.connect(lambda *_: self.changed.emit(self.value()))
        self.lineEdit().editingFinished.connect(lambda: self.changed.emit(self.value()))

    def value(self):
        text = self.currentText()
        index = self.findText(text)
        return self.itemData(index) if index >= 0 else text

    def set_value(self, value):
        previous = self.blockSignals(True)
        index = self.findData(value)
        self.setCurrentIndex(index)
        if index < 0:
            self.setEditText(value)
        self.blockSignals(previous)

    def retranslate(self):
        value = self.value()
        previous = self.blockSignals(True)
        for index, (key, label) in enumerate(self.labels.items()):
            self.setItemText(index, tr(label) if self.color else key + "  " + tr(label))
        self.set_value(value)
        self.blockSignals(previous)
