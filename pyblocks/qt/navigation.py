"""Narrow navigation tabs reserve color for the program's semantic blocks."""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QTabBar


class ModeTabs(QTabBar):
    translate_tabs = True

    def __init__(self):
        super().__init__()
        self.setShape(QTabBar.Shape.RoundedWest)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setFixedWidth(36)
        for label in ("Программа", "Управление", "Помощь"):
            self.addTab(label)
        self.setAccessibleName("Режимы")

    def tabSizeHint(self, index):
        return QSize(36, self.fontMetrics().horizontalAdvance(self.tabText(index)) + 36)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        for index in range(self.count()):
            rect = self.tabRect(index)
            active = index == self.currentIndex()
            if active:
                painter.setPen(QPen(QColor("#303944"), 2))
                painter.drawLine(
                    rect.left() + 2, rect.top() + 8, rect.left() + 2, rect.bottom() - 8
                )
            painter.save()
            painter.translate(rect.center())
            painter.rotate(-90)
            font = self.font()
            font.setBold(active)
            painter.setFont(font)
            painter.setPen(QColor("#25303d" if active else "#697380"))
            painter.drawText(
                QRectF(
                    -rect.height() / 2, -rect.width() / 2, rect.height(), rect.width()
                ),
                Qt.AlignmentFlag.AlignCenter,
                self.tabText(index),
            )
            painter.restore()
