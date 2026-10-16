"""Review a family operation and its fields before one atomic source edit."""

import ast
from dataclasses import replace
from difflib import unified_diff

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.core.catalog import Family
from little_tinker_rig.core.parameters import suggestions
from little_tinker_rig.core.snippets import Expansion
from little_tinker_rig.core.types import Compatibility, compatibility, known_type
from little_tinker_rig.core.variants import field_key, variant_bindings, variant_source
from little_tinker_rig.i18n import tr

from .library import snippet_title
from .parameters import unit_text


def changed_default(value, default):
    if default is None:
        return True
    try:
        return ast.dump(ast.parse(value, mode="eval")) != ast.dump(
            ast.parse(default, mode="eval")
        )
    except SyntaxError:
        return True


def variant_choices(view, match):
    current = match.snippet
    members = tuple(
        s
        for s in view.session.available_snippets
        if s.catalog_id == current.catalog_id and not s.historical
    )
    family = Family(next((s for s in members if not s.family), current), members)
    available = family.choices(view.expression_level, view.expression_ids)
    return available if current in available else (current, *available)


class VariantDialog(QDialog):
    def __init__(self, view):
        super().__init__(view)
        self.session = view.session
        self.syntax = self.session.document.syntax
        self.match = self.session.selected_match()
        if self.match is None or self.match.snippet.historical:
            raise ValueError(tr("Select a current recognized block"))
        self.fields = {}
        self.drafts = {}
        self.snippet = self.match.snippet
        self.setWindowTitle(tr("Block variants and parameters"))
        self.resize(590, 340)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self.update_preview)
        layout = QVBoxLayout(self)
        self.variant = QComboBox()
        self.variant.setAccessibleName(tr("Variant"))
        available = variant_choices(view, self.match)
        self.variants = {s.identity: s for s in available}
        for snippet in available:
            self.variant.addItem(
                tr(snippet.variant) if snippet.variant else snippet_title(snippet),
                snippet.identity,
            )
        self.variant.setCurrentIndex(self.variant.findData(self.snippet.identity))
        layout.addWidget(self.variant)
        self.details = QLabel()
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        self.form_area = QScrollArea()
        self.form_area.setWidgetResizable(True)
        self.form_area.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(self.form_area)
        self.preview_toggle = QToolButton()
        self.preview_toggle.setText(tr("Python changes"))
        self.preview_toggle.setCheckable(True)
        self.preview_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.preview_toggle.setArrowType(Qt.ArrowType.RightArrow)
        layout.addWidget(self.preview_toggle)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.preview.setAccessibleName(tr("Python changes"))
        self.preview.setMaximumHeight(210)
        self.preview.setMinimumHeight(180)
        self.preview.hide()
        layout.addWidget(self.preview)
        self.preview_toggle.toggled.connect(self.show_preview)
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
        self.variant.currentIndexChanged.connect(self.change_variant)
        self.change_variant()
        self.resize(590, self.minimumSizeHint().height())

    def change_variant(self, *_):
        self.timer.stop()
        previous_values = self.values()
        for parameter in self.snippet.parameters:
            if parameter.name in self.fields:
                self.drafts[field_key(self.snippet, parameter.name)] = (
                    previous_values[parameter.name],
                    parameter.annotation,
                )
        self.snippet = self.variants[self.variant.currentData()]
        values = variant_bindings(self.session, self.match, self.snippet)
        for parameter in self.snippet.parameters:
            saved = self.drafts.get(field_key(self.snippet, parameter.name))
            if (
                saved
                and compatibility(parameter.annotation, known_type(saved[1]))
                is not Compatibility.INCOMPATIBLE
            ):
                values[parameter.name] = saved[0]
        self.fields = {}
        panel = QWidget()
        layout = QVBoxLayout(panel)
        essential = QFormLayout()
        layout.addLayout(essential)
        self.more = QToolButton()
        self.more.setText(tr("Additional settings"))
        self.more.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.more.setCheckable(True)
        layout.addWidget(self.more)
        self.additional = QWidget()
        extras = QFormLayout(self.additional)
        extras.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.additional)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        for parameter in self.snippet.parameters:
            field = QComboBox()
            field.setEditable(True)
            field.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            field.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            field.setMinimumContentsLength(16)
            for value in suggestions(
                self.session, parameter, self.match.span.start
            ).values():
                field.addItem(value.source, value)
            value = values[parameter.name]
            if isinstance(value, Expansion):
                index = field.findText(value.source)
                if index < 0:
                    field.addItem(value.source, value)
                    index = field.count() - 1
                else:
                    field.setItemData(index, value)
                field.setCurrentIndex(index)
            else:
                field.setCurrentText(value)
            field.setAccessibleName(parameter.name)
            field.setToolTip(parameter.annotation or "Python")
            field.currentTextChanged.connect(lambda *_: self.timer.start())
            self.fields[parameter.name] = field
            unit = unit_text(parameter.annotation)
            form = extras if parameter.name in self.snippet.advanced else essential
            form.addRow(parameter.name + (f" · {unit}" if unit else ""), field)
        self.more.setVisible(bool(self.snippet.advanced))
        self.more.setChecked(
            any(
                changed_default(self.fields[p.name].currentText(), p.default)
                for p in self.snippet.parameters
                if p.name in self.snippet.advanced
            )
        )
        self.more.toggled.connect(self.update_additional)
        self.update_additional()
        old = self.form_area.takeWidget()
        if old:
            old.deleteLater()
        self.form_area.setWidget(panel)
        self.details.setText("\n\n".join(tr(self.snippet.help).split("\n\n")[:2]))
        self.details.setToolTip(tr(self.snippet.help))
        self.update_preview()

    def show_preview(self, visible):
        self.preview.setVisible(visible)
        self.preview_toggle.setArrowType(
            Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow
        )
        self.resize(self.width(), self.minimumSizeHint().height())

    def values(self):
        return {
            name: (
                replace(value, source=field.currentText())
                if isinstance(value := field.currentData(), Expansion)
                else field.currentText()
            )
            for name, field in self.fields.items()
        }

    def update_additional(self):
        self.additional.setVisible(self.more.isChecked())
        self.more.setArrowType(
            Qt.ArrowType.DownArrow if self.more.isChecked() else Qt.ArrowType.RightArrow
        )
        active = [
            f"{p.name} = {self.fields[p.name].currentText()}"
            for p in self.snippet.parameters
            if p.name in self.snippet.advanced
            and changed_default(self.fields[p.name].currentText(), p.default)
        ]
        self.summary.setText("; ".join(active))
        self.summary.setVisible(bool(active) and not self.more.isChecked())
        if panel := self.form_area.widget():
            panel.layout().activate()
            self.form_area.setFixedHeight(min(300, panel.sizeHint().height() + 4))

    def update_preview(self):
        self.update_additional()
        try:
            if (
                self.session.document.syntax is not self.syntax
                or self.session.selected_match() is not self.match
            ):
                raise ValueError(tr("Document changed; choose the block again"))
            self.candidate = variant_source(
                self.session, self.match, self.snippet, self.values()
            )
        except (ValueError, SyntaxError, OSError) as error:
            self.error.setText(tr(str(error)))
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return False
        self.error.clear()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        diff = "\n".join(
            unified_diff(
                self.syntax.source.splitlines(),
                self.candidate.splitlines(),
                fromfile="before.py",
                tofile="after.py",
                lineterm="",
            )
        )
        self.preview.setPlainText(diff or tr("No changes"))
        self.preview_toggle.setVisible(bool(diff))
        if not diff:
            self.preview_toggle.setChecked(False)
        return True

    def apply(self):
        self.timer.stop()
        if not self.update_preview():
            return
        try:
            self.session.change_variant(self.snippet, self.values())
        except (ValueError, SyntaxError, OSError) as error:
            self.error.setText(tr(str(error)))
            return
        self.accept()
