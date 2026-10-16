"""Edit catalog metadata in the same Python definition as its executable template."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.core.block_metadata import CATEGORIES, change_property
from little_tinker_rig.core.snippets import load_module
from little_tinker_rig.i18n import tr


class CatalogProperties(QDialog):
    def __init__(self, source, snippet, snippets, parent=None):
        super().__init__(parent)
        self.source, self.snippet = source, snippet
        self.setWindowTitle(tr("Catalog properties"))
        self.resize(590, 500)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit(snippet.title)
        form.addRow(tr("Short title"), self.title)
        self.group = QLineEdit(" / ".join(snippet.group))
        self.group.setPlaceholderText(tr("Group / subgroup (family primary only)"))
        self.group.setCompleter(
            QCompleter(
                sorted({" / ".join(s.group) for s in snippets if s.group}), self.group
            )
        )
        form.addRow(tr("Group path"), self.group)
        self.category = QComboBox()
        self.category.addItem(tr("Module heading"), "")
        for key, title in CATEGORIES.items():
            self.category.addItem(tr(title), key)
        self.category.setCurrentIndex(self.category.findData(snippet.category))
        form.addRow(tr("Category"), self.category)
        self.family = QLineEdit(snippet.family)
        self.family.setPlaceholderText(tr("Separate card (no family)"))
        self.family.setCompleter(
            QCompleter(
                sorted(
                    {
                        s.identity
                        for s in snippets
                        if not s.historical
                        and not s.family
                        and s.identity != snippet.identity
                        and s.identity.split("/")[0] == snippet.identity.split("/")[0]
                        and s.expression == snippet.expression
                        and s.context == snippet.context
                    }
                ),
                self.family,
            )
        )
        form.addRow(tr("Family primary"), self.family)
        self.variant = QLineEdit(snippet.variant or "")
        form.addRow(tr("Variant label"), self.variant)
        layout.addLayout(form)
        hint = QLabel(
            tr(
                "A family points to its primary block. Leave a member's variant label empty only for a recognition-only alias."
            )
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        help_text = QLabel(
            tr(
                "Shared fields keep their values across variants. Optional fields can appear under Additional settings."
            )
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        panel = QWidget()
        fields = QFormLayout(panel)
        self.fields = {}
        for parameter in snippet.parameters:
            row = QHBoxLayout()
            shared = QLineEdit(snippet.bindings.get(parameter.name, parameter.name))
            shared.setAccessibleName(tr("Shared field for {name}", name=parameter.name))
            row.addWidget(shared, 1)
            additional = QCheckBox(tr("Additional"))
            additional.setEnabled(parameter.default is not None)
            additional.setChecked(parameter.name in snippet.advanced)
            row.addWidget(additional)
            fields.addRow(parameter.name, row)
            self.fields[parameter.name] = shared, additional
        scroll.setWidget(panel)
        layout.addWidget(scroll, 1)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #a03333")
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.apply)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def apply(self):
        values = {
            "title": self.title.text().strip(),
            "group": (
                tuple(part.strip() for part in self.group.text().split("/"))
                if self.group.text().strip()
                else ()
            ),
            "category": self.category.currentData(),
            "family": self.family.text().strip(),
            "variant": self.variant.text().strip() or None,
            "advanced": tuple(
                name
                for name, (_, additional) in self.fields.items()
                if additional.isChecked()
            ),
            "bindings": {
                name: shared.text().strip()
                for name, (shared, _) in self.fields.items()
                if shared.text().strip() != name
            },
        }
        try:
            source = self.source
            previous = {name: getattr(self.snippet, name) for name in values}
            for name, value in values.items():
                if value != previous[name]:
                    source = change_property(
                        source, self.snippet.identity.rsplit("/", 1)[1], name, value
                    )
            load_module(
                source, self.snippet.identity.rsplit("/", 1)[0], self.snippet.version
            )
        except (ValueError, SyntaxError) as error:
            self.error.setText(str(error))
            return
        self.source = source
        self.accept()
