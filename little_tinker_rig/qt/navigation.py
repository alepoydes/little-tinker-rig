"""Compact workspace icons with localized tooltips and accessible names."""


from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QWidget,
)

from little_tinker_rig.i18n import N_, tr

from .theme import colors, contrast_icon, svg_icon


def tool_button(title, icon):
    button = QToolButton()
    button.setText(title)
    button.setToolTip(title)
    button.setAccessibleName(title)
    button.setProperty("standardIcon", icon)
    button.setIcon(contrast_icon(button.style().standardIcon(icon)))
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    return button


class ChoiceButtons(QWidget):
    """Exclusive icon choices with localized tooltips and keyboard focus."""

    changed = Signal(str)

    def __init__(self, choices):
        super().__init__()
        self.choices = choices
        self.buttons = {}
        self.value = next(iter(choices))
        self.group = QButtonGroup(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        for key, title in choices.items():
            button = QToolButton()
            button.setCheckable(True)
            button.setToolTip(title)
            button.setAccessibleName(title)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setIcon(svg_icon(key))
            button.setIconSize(QSize(20, 20))
            button.clicked.connect(lambda checked=False, key=key: self.select(key))
            self.group.addButton(button)
            self.buttons[key] = button
            layout.addWidget(button)
        self.buttons[self.value].setChecked(True)
        self.retranslate()

    def select(self, value):
        if value not in self.buttons:
            return
        changed = value != self.value
        self.value = value
        self.buttons[value].setChecked(True)
        self.retranslate()
        if changed:
            self.changed.emit(value)

    def retranslate(self):
        for key, button in self.buttons.items():
            button.setToolTip(tr(self.choices[key]))
            button.setAccessibleName(tr(self.choices[key]))

    def apply_theme(self):
        for key, button in self.buttons.items():
            button.setIcon(svg_icon(key))


class ModeDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Keep names in the model for accessibility and tooltips, not on screen.
        option.text = ""
        option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDisplay

    def paint(self, painter, option, index):
        option = QStyleOptionViewItem(option)
        self.initStyleOption(option, index)
        icon = QIcon(option.icon)
        option.icon = QIcon()
        option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDecoration
        option.widget.style().drawControl(
            QStyle.ControlElement.CE_ItemViewItem, option, painter, option.widget
        )
        rect = QStyle.alignedRect(
            option.direction,
            Qt.AlignmentFlag.AlignCenter,
            option.decorationSize,
            option.rect,
        )
        icon.paint(painter, rect)

    def sizeHint(self, option, index):
        return QSize(30, 48)


class ModeList(QListWidget):
    translate_items = True

    def __init__(self):
        super().__init__()
        self.setIconSize(QSize(24, 24))
        self.setItemDelegate(ModeDelegate(self))
        self.setUniformItemSizes(True)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.apply_theme()
        for icon, label in (
            ("program", N_("Program")),
            ("control", N_("Control")),
            ("help", N_("Help")),
            ("block-editor", N_("Block Editor")),
        ):
            self.add_mode(icon, label)
        self.setCurrentRow(0)
        self.setAccessibleName(N_("Workspaces"))

    def add_mode(self, icon, label):
        item = QListWidgetItem(svg_icon(icon, rail=True), label)
        item.setData(Qt.ItemDataRole.UserRole, icon)
        self.addItem(item)

    def apply_theme(self):
        c = colors()
        self.setStyleSheet(
            f"ModeList {{ border: 0; background: {c['rail']}; color: white; }}"
            "ModeList::item { padding: 0; border-left: 3px solid transparent; "
            "border-right: 3px solid transparent; }"
            f"ModeList::item:hover {{ background: {c['rail_hover']}; }}"
            f"ModeList::item:selected {{ background: {c['rail_hover']}; "
            f"border-left-color: {c['accent']}; }}"
        )
        for index in range(self.count()):
            item = self.item(index)
            item.setIcon(svg_icon(item.data(Qt.ItemDataRole.UserRole), rail=True))

    def set_mode_visible(self, row, visible):
        item = self.item(row)
        item.setHidden(not visible)
        # Hidden QListWidget rows can still be targeted by Home/End unless disabled.
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            if visible
            else Qt.ItemFlag.NoItemFlags
        )

    def moveCursor(self, action, modifiers):
        if action in (self.CursorAction.MoveHome, self.CursorAction.MoveEnd):
            rows = [i for i in range(self.count()) if not self.item(i).isHidden()]
            if rows:
                row = rows[0] if action == self.CursorAction.MoveHome else rows[-1]
                return self.model().index(row, 0)
        return super().moveCursor(action, modifiers)

    def sizeHint(self):
        return QSize(48, 48 * self.count())

    def minimumSizeHint(self):
        return QSize(48, 48)
