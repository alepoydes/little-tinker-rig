"""Visible window controls with native compositor move/resize operations."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QToolButton,
    QWidget,
)

from little_tinker_rig.i18n import N_, tr

from .theme import colors, contrast_icon, svg_icon


class ElidedTitle(QLabel):
    """Keep a useful drag area when a localized title grows too long."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().windowText().color())
        text = self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideMiddle, max(0, self.width() - 16)
        )
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)


class TitleBar(QWidget):
    def __init__(self, window, menu):
        super().__init__(window)
        self.owner = window
        self.setFixedHeight(42)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 0, 0)
        row.setSpacing(3)
        self.mark = QLabel(self)
        self.mark.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.mark.setPixmap(svg_icon("brand").pixmap(25, 25))
        row.addWidget(self.mark)
        self.brand = QLabel(self)
        self.brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.brand.setTextFormat(Qt.TextFormat.RichText)
        self.brand.setAccessibleName("LittleTinker Rig")
        self.brand.setProperty("translationSources", {})
        self.brand.setStyleSheet("font-size: 18px; font-weight: 700; padding-right: 10px")
        row.addWidget(self.brand)
        self.menu = menu
        menu.setNativeMenuBar(False)
        menu.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        row.addWidget(menu)
        self.title = ElidedTitle(window.windowTitle())
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.title.setProperty("translationSources", {})
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
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
            button.setProperty("standardIcon", icon)
            button.setIcon(contrast_icon(self.style().standardIcon(icon)))
            button.setToolTip(caption)
            button.setAccessibleName(caption)
            button.setFixedHeight(42)
            button.clicked.connect(callback)
            row.addWidget(button)
            setattr(self, name, button)
        self.close_button.setObjectName("windowClose")
        window.windowTitleChanged.connect(self.title.setText)
        window.installEventFilter(self)
        self.apply_theme(window.visual_theme)

    def apply_theme(self, name):
        palette = colors(name)
        self.setStyleSheet(
            f"TitleBar {{ background: {palette['title']}; }}"
            "TitleBar QToolButton { border: 0; border-radius: 0; min-width: 28px; }"
            f"TitleBar QToolButton:hover {{ background: {palette['hover']}; }}"
            "TitleBar #windowClose:hover { background: #c44141; color: white; }"
        )
        self.brand.setText(
            f"<span style='color:{palette['text']}'>LittleTinker</span> "
            f"<span style='color:{palette['accent']}'>Rig</span>"
        )
        for button in (self.minimize, self.maximize, self.close_button):
            button.setIcon(
                contrast_icon(self.style().standardIcon(button.property("standardIcon")))
            )
        self.title.update()

    def toggle_maximized(self):
        (
            self.owner.showNormal()
            if self.owner.isMaximized() or self.owner.isFullScreen()
            else self.owner.showMaximized()
        )

    def update_state(self):
        maximized = self.owner.isMaximized() or self.owner.isFullScreen()
        self.maximize.setToolTip(tr("Restore") if maximized else tr("Maximize"))
        self.maximize.setAccessibleName(self.maximize.toolTip())
        self.maximize.setIcon(
            contrast_icon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_TitleBarNormalButton
                if maximized
                else QStyle.StandardPixmap.SP_TitleBarMaxButton
            ))
        )
        self.maximize.setProperty(
            "standardIcon",
            QStyle.StandardPixmap.SP_TitleBarNormalButton
            if maximized
            else QStyle.StandardPixmap.SP_TitleBarMaxButton,
        )
        self.setVisible(True)
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
