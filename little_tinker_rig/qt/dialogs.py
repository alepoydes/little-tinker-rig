"""Local Python drafts keep invalid text outside the committed document."""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from .code import CodeEdit
from .localization import localize
from .theme import colors


class EditDialog(QDialog):
    def __init__(self, parent, title, apply, *, text):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 420)
        self.apply_edit = apply
        layout = QVBoxLayout(self)
        self.text = CodeEdit()
        self.text.setPlainText(text)
        layout.addWidget(self.text)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.apply_theme()
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        localize(self)

    def apply_theme(self):
        self.error.setStyleSheet(f"color: {colors()['danger']}")
        self.text.apply_theme()

    def apply(self):
        try:
            self.apply_edit(self.text.toPlainText())
        except (ValueError, SyntaxError, OSError) as error:
            self.error.setText(str(error))
            return
        self.accept()
