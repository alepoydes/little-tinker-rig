"""Compact workspace icons with localized tooltips and accessible names."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from little_tinker_rig.i18n import N_


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
        self.setStyleSheet(
            "ModeList { border: 0; background: transparent; color: #5b6572; }"
            "ModeList::item { padding: 0; border-left: 3px solid transparent; border-right: 3px solid transparent; }"
            "ModeList::item:hover { background: #f1f4f8; }"
            "ModeList::item:selected { background: #e7eef6; color: #25303d; border-left-color: #344f73; }"
        )
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
        path = Path(__file__).with_name("icons") / f"{icon}.svg"
        self.addItem(QListWidgetItem(QIcon(str(path)), label))

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
