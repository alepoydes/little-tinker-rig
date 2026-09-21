"""Local draft editors keep invalid text outside the committed document."""

import ast

from PySide6.QtWidgets import (
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)


class EditDialog(QDialog):
    def __init__(
        self, parent, title, apply, *, text=None, snippet=None, bindings=None, names=()
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 420)
        self.apply_edit = apply
        layout = QVBoxLayout(self)
        self.inputs = {}
        self.text = None
        if text is not None:
            self.text = QPlainTextEdit(text)
            layout.addWidget(self.text)
        else:
            form = QFormLayout()
            bindings = bindings or {}
            for parameter in snippet.parameters:
                value = (
                    ast.unparse(bindings[parameter.name])
                    if parameter.name in bindings
                    else parameter.default or ""
                )
                field = QLineEdit(value)
                field.setCompleter(QCompleter(list(names), field))
                label = parameter.name + (
                    f" · {parameter.annotation}" if parameter.annotation else ""
                )
                form.addRow(label, field)
                self.inputs[parameter.name] = field
            layout.addLayout(form)
            layout.addWidget(
                QLabel(snippet.help.splitlines()[0] if snippet.help else "")
            )
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #a03333")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self):
        value = (
            self.text.toPlainText()
            if self.text is not None
            else {name: field.text() for name, field in self.inputs.items()}
        )
        try:
            self.apply_edit(value)
        except (ValueError, SyntaxError, OSError) as error:
            self.error.setText(str(error))
            return
        self.accept()
