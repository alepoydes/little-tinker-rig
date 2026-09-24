"""Compact, colored source previews that remain recognizable after insertion."""

from PySide6.QtCore import QMimeData, QSize, Qt
from PySide6.QtGui import QColor, QFontDatabase, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem

from pyblocks.core.presentation import PALETTE, snippet_role
from pyblocks.core.snippets import instantiate, snippet_groups
from pyblocks.i18n import N_, tr

from .annotations import block_icon
from .drag import Drag

IDENTITY = Qt.ItemDataRole.UserRole
PREVIEW = int(IDENTITY) + 1
COLOR = int(IDENTITY) + 2
DESCRIPTION = int(IDENTITY) + 3
ICON = int(IDENTITY) + 4
LEVEL = int(IDENTITY) + 5

LEVEL_TITLES = {
    "beginner": N_("Beginner"),
    "standard": N_("Standard"),
    "expert": N_("Expert"),
}


GROUP_TITLES = {
    "document/functions": N_("My functions"),
    "python/basics": N_("Python basics"),
    "pybricks/motors": N_("Motors"),
    "pybricks/sensors": N_("Sensors and timing"),
    "pybricks/drive": N_("Drive bases and clocks"),
}


def group_title(identity):
    return tr(GROUP_TITLES[identity]) if identity in GROUP_TITLES else identity


def snippet_title(snippet):
    return (
        tr(snippet.help).splitlines()[0]
        if snippet.help
        else snippet.identity.rsplit("/", 1)[1]
    )


class CardDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if not index.data(IDENTITY):
            return super().paint(painter, option, index)
        painter.save()
        rect = option.rect.adjusted(3, 3, -4, -3)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        color = QColor(index.data(COLOR))
        painter.setBrush(color.darker(112) if selected else color)
        painter.setPen(QPen(QColor("#c5d1da"), 1))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setClipRect(rect)
        painter.setPen(QColor("#203040"))
        description = index.data(ICON) + "  " + index.data(DESCRIPTION)
        font = option.font
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            rect.adjusted(10, 7, -8, 0),
            Qt.AlignmentFlag.AlignTop,
            QFontMetrics(font).elidedText(
                description, Qt.TextElideMode.ElideRight, rect.width() - 20
            ),
        )
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(
            rect.adjusted(10, 26, -8, 0),
            Qt.AlignmentFlag.AlignTop,
            tr(LEVEL_TITLES[index.data(LEVEL)]),
        )
        painter.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        for row, line in enumerate(index.data(PREVIEW).splitlines()[:2]):
            text = painter.fontMetrics().elidedText(
                line, Qt.TextElideMode.ElideRight, rect.width() - 20
            )
            painter.drawText(rect.left() + 10, rect.top() + 57 + row * 17, text)
        painter.restore()

    def sizeHint(self, option, index):
        if index.data(IDENTITY):
            return QSize(
                270, 69 + 17 * (min(2, len(index.data(PREVIEW).splitlines())) - 1)
            )
        return super().sizeHint(option, index)


class Library(QTreeWidget):
    def __init__(self, snippets):
        super().__init__()
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setIndentation(12)
        self.setItemDelegate(CardDelegate(self))
        self.setMinimumWidth(270)
        self.level = "all"
        self.load(snippets)

    def load(self, snippets):
        self.function_key = tuple(
            (s.identity, s.parameters, s.help)
            for s in snippets
            if s.identity.startswith("document/")
        )
        self.clear()
        for group, members in snippet_groups(snippets).items():
            heading = QTreeWidgetItem(self, [group_title(group)])
            heading.setToolTip(0, group)
            heading.setFlags(heading.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            for snippet in members:
                name = snippet.identity.rsplit("/", 1)[1]
                expansion = instantiate(
                    snippet,
                    {p.name: p.name for p in snippet.parameters if p.default is None},
                )
                item = QTreeWidgetItem(heading, [name])
                item.setData(0, IDENTITY, snippet.identity)
                item.setData(0, ICON, block_icon(snippet))
                item.setData(0, LEVEL, snippet.level)
                item.setData(0, PREVIEW, expansion.source)
                item.setData(0, COLOR, PALETTE[snippet_role(snippet)])
                item.setData(0, DESCRIPTION, snippet_title(snippet))
                item.setToolTip(0, expansion.source + "\n\n" + tr(snippet.help))
        self.expandAll()

    def update_functions(self, snippets):
        key = tuple(
            (s.identity, s.parameters, s.help)
            for s in snippets
            if s.identity.startswith("document/")
        )
        if key != self.function_key:
            self.load(snippets)
            self.filter(getattr(self, "search", ""))
            return True
        return False

    def filter(self, search, level=None):
        self.search = search
        words = search.casefold().split()
        if level is not None:
            self.level = level
        for index in range(self.topLevelItemCount()):
            group = self.topLevelItem(index)
            visible = False
            for child in range(group.childCount()):
                item = group.child(child)
                match = (self.level == "all" or item.data(0, LEVEL) == self.level) and (
                    all(
                        word
                        in (
                            item.text(0) + " " + item.toolTip(0) + " " + group.text(0)
                        ).casefold()
                        for word in words
                    )
                )
                item.setHidden(not match)
                visible |= match
            group.setHidden(not visible)

    def mimeData(self, items):
        data = QMimeData()
        if items and items[0].data(0, IDENTITY):
            data.setData(
                "application/x-pyblocks-snippet", items[0].data(0, IDENTITY).encode()
            )
        return data

    def startDrag(self, actions):
        item = self.currentItem()
        if not item or not item.data(0, IDENTITY):
            return
        rect = self.visualItemRect(item)
        Drag(self, self.mimeData([item]), self.viewport().grab(rect))
