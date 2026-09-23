"""Visible window controls with native compositor move/resize operations."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStyle, QToolButton, QWidget

from pyblocks.i18n import N_, tr


class TitleBar(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.owner = window
        self.setFixedHeight(34)
        self.setStyleSheet(
            "TitleBar { background: #e8eef5; } QToolButton { border: 0; border-radius: 0; min-width: 28px; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 0, 0)
        row.setSpacing(0)
        self.title = QLabel(window.windowTitle())
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.title.setProperty("translationSources", {})
        row.addWidget(self.title, 1)
        for name, caption, icon, callback in (
            (
                "minimize",
                N_("Minimize"),
                QStyle.StandardPixmap.SP_TitleBarMinButton,
                window.showMinimized,
            ),
            (
                "maximize",
                N_("Maximize"),
                QStyle.StandardPixmap.SP_TitleBarMaxButton,
                self.toggle_maximized,
            ),
            (
                "close_button",
                N_("Close"),
                QStyle.StandardPixmap.SP_TitleBarCloseButton,
                window.close,
            ),
        ):
            button = QToolButton(self)
            button.setIcon(self.style().standardIcon(icon))
            button.setToolTip(caption)
            button.setAccessibleName(caption)
            button.setFixedHeight(34)
            button.clicked.connect(callback)
            row.addWidget(button)
            setattr(self, name, button)
        self.close_button.setStyleSheet("QToolButton:hover { background: #c44141; }")
        window.windowTitleChanged.connect(self.title.setText)
        window.installEventFilter(self)

    def toggle_maximized(self):
        (
            self.owner.showNormal()
            if self.owner.isMaximized()
            else self.owner.showMaximized()
        )

    def update_state(self):
        maximized = self.owner.isMaximized()
        self.maximize.setToolTip(tr("Restore") if maximized else tr("Maximize"))
        self.maximize.setAccessibleName(self.maximize.toolTip())
        self.maximize.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_TitleBarNormalButton
                if maximized
                else QStyle.StandardPixmap.SP_TitleBarMaxButton
            )
        )
        self.setVisible(not self.owner.isFullScreen())
        (
            self.owner.setContentsMargins(0, 0, 0, 0)
            if maximized or self.owner.isFullScreen()
            else self.owner.setContentsMargins(5, 5, 5, 5)
        )

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self.update_state()
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner.windowHandle().startSystemMove()
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()


def resize_edges(window, point):
    if window.isMaximized() or window.isFullScreen():
        return Qt.Edge(0)
    edges = Qt.Edge(0)
    for condition, edge in (
        (point.x() < 5, Qt.Edge.LeftEdge),
        (point.x() >= window.width() - 5, Qt.Edge.RightEdge),
        (point.y() < 5, Qt.Edge.TopEdge),
        (point.y() >= window.height() - 5, Qt.Edge.BottomEdge),
    ):
        if condition:
            edges |= edge
    return edges
