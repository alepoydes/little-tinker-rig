"""Compact, colored source previews that remain recognizable after insertion."""

from PySide6.QtCore import QMimeData, QSize, Qt
from PySide6.QtGui import QColor, QDrag, QFontDatabase, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem

from pyblocks.core.presentation import PALETTE, snippet_role
from pyblocks.core.snippets import instantiate

IDENTITY = Qt.ItemDataRole.UserRole
PREVIEW = int(IDENTITY) + 1
COLOR = int(IDENTITY) + 2
DESCRIPTION = int(IDENTITY) + 3


class CardDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if not index.data(IDENTITY):
            return super().paint(painter, option, index)
        painter.save()
        rect = option.rect.adjusted(3, 3, -4, -3)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(index.data(COLOR)))
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(
            QPen(QColor("#277d96" if selected else "#c5d1da"), 2 if selected else 1)
        )
        painter.drawRoundedRect(rect, 6, 6)
        painter.setClipRect(rect)
        painter.setPen(QColor("#203040"))
        description = index.data(DESCRIPTION)
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
        painter.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        for row, line in enumerate(index.data(PREVIEW).splitlines()[:3]):
            text = painter.fontMetrics().elidedText(
                line, Qt.TextElideMode.ElideRight, rect.width() - 20
            )
            painter.drawText(rect.left() + 10, rect.top() + 42 + row * 17, text)
        painter.restore()

    def sizeHint(self, option, index):
        if index.data(IDENTITY):
            return QSize(
                270, 54 + 17 * (min(3, len(index.data(PREVIEW).splitlines())) - 1)
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
        groups = {}
        for snippet in snippets:
            if snippet.historical:
                continue
            group, name = snippet.identity.rsplit("/", 1)
            if group not in groups:
                groups[group] = QTreeWidgetItem(self, [group])
                groups[group].setFlags(
                    groups[group].flags() & ~Qt.ItemFlag.ItemIsDragEnabled
                )
            expansion = instantiate(
                snippet,
                {p.name: p.name for p in snippet.parameters if p.default is None},
            )
            item = QTreeWidgetItem(groups[group], [name])
            item.setData(0, IDENTITY, snippet.identity)
            item.setData(0, PREVIEW, expansion.source)
            item.setData(0, COLOR, PALETTE[snippet_role(snippet)])
            item.setData(
                0, DESCRIPTION, snippet.help.splitlines()[0] if snippet.help else name
            )
            item.setToolTip(0, expansion.source + "\n\n" + snippet.help)
        self.expandAll()

    def filter(self, search):
        for index in range(self.topLevelItemCount()):
            group = self.topLevelItem(index)
            visible = False
            for child in range(group.childCount()):
                item = group.child(child)
                match = (
                    search.casefold()
                    in (item.text(0) + item.toolTip(0) + group.text(0)).casefold()
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
        drag = QDrag(self)
        drag.setMimeData(self.mimeData([item]))
        rect = self.visualItemRect(item)
        drag.setPixmap(self.viewport().grab(rect))
        drag.exec(Qt.DropAction.CopyAction)
