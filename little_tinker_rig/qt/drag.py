"""One cancellable pointer gesture for source, library and Scratch transfers."""

from PySide6.QtCore import QEvent, QMimeData, QObject, QPoint, Qt, QTimer
from PySide6.QtGui import (
    QCursor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
)
from PySide6.QtWidgets import QApplication, QLabel

_active = None


class BlockMime(QMimeData):
    def __init__(self, transfer):
        super().__init__()
        self.transfer = transfer
        self.setData("application/x-little-tinker-rig-fragment", transfer.text.encode())
        self.setText(transfer.text)


def cancel_drag():
    if _active is not None:
        _active.finish(False)
        return True
    return False


class Drag(QObject):
    """The document stays immutable until the accepted drop; Escape ends the gesture."""

    def __init__(self, widget, data, pixmap, *, origin=None, hotspot=None):
        super().__init__(widget.window())
        global _active
        cancel_drag()
        _active = self
        self.widget, self.data, self.origin = widget, data, origin
        self.target = None
        self.accepted = False
        self.position = QCursor.pos()
        self.action = (
            Qt.DropAction.MoveAction
            if isinstance(data, BlockMime)
            else Qt.DropAction.CopyAction
        )
        self.preview = QLabel(widget.window())
        self.preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.preview.setPixmap(pixmap)
        self.preview.resize(pixmap.deviceIndependentSize().toSize())
        self.preview.setStyleSheet("border: 1px solid #567b90; background: #fafbfc")
        self.hotspot = hotspot or QPoint(16, 12)
        self.preview.show()
        self.preview.raise_()
        if origin is not None:
            origin.show_drag_origin(data.transfer)
        QApplication.instance().installEventFilter(self)
        QApplication.setOverrideCursor(Qt.CursorShape.ClosedHandCursor)
        widget.grabMouse()
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.scroll)
        self.timer.start()
        self.move(self.position)

    def locate(self, position):
        widget = QApplication.widgetAt(position)
        while widget is not None:
            if getattr(widget, "block_drop_target", False):
                return widget
            widget = widget.parentWidget()
        return None

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.finish(False)
            return True
        if event.type() == QEvent.Type.MouseMove:
            self.move(event.globalPosition().toPoint())
            return True
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint())
            self.finish(True)
            return True
        if event.type() == QEvent.Type.ApplicationDeactivate:
            self.finish(False)
        return False

    def move(self, position):
        self.position = position
        self.preview.move(
            self.preview.parentWidget().mapFromGlobal(position) - self.hotspot
        )
        self.preview.raise_()
        marker = getattr(self.origin, "origin_marker", None)
        returning = (
            marker is not None
            and marker.isVisible()
            and marker.rect().contains(marker.mapFromGlobal(position))
        )
        target = None if returning else self.locate(position)
        if target is not self.target:
            if self.target is not None:
                self.target.dragLeaveEvent(QDragLeaveEvent())
            self.target = target
            if target is not None:
                enter = QDragEnterEvent(
                    target.viewport().mapFromGlobal(position),
                    self.action,
                    self.data,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                target.dragEnterEvent(enter)
                if not enter.isAccepted():
                    self.target = None
        self.accepted = returning
        if self.target is not None:
            event = QDragMoveEvent(
                self.target.viewport().mapFromGlobal(position),
                self.action,
                self.data,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            self.target.dragMoveEvent(event)
            self.accepted = event.isAccepted()
        QApplication.changeOverrideCursor(
            Qt.CursorShape.ClosedHandCursor
            if self.accepted
            else Qt.CursorShape.ForbiddenCursor
        )

    def scroll(self):
        target = self.target
        while target is not None:
            if (
                hasattr(target, "verticalScrollBar")
                and target.verticalScrollBar().maximum()
            ):
                point = target.viewport().mapFromGlobal(self.position)
                height = target.viewport().height()
                step = -12 if point.y() < 24 else 12 if point.y() > height - 24 else 0
                if step:
                    bar = target.verticalScrollBar()
                    bar.setValue(bar.value() + step)
                    self.move(self.position)
                break
            target = target.parentWidget()

    def finish(self, drop):
        global _active
        if _active is not self:
            return
        _active = None
        self.timer.stop()
        QApplication.instance().removeEventFilter(self)
        self.widget.releaseMouse()
        QApplication.restoreOverrideCursor()
        self.preview.hide()
        target = self.target
        # Restore transient formats before source visibility and before committing.
        destination = getattr(target, "drop_target", None)
        if destination is not None:
            target.set_drop_target(None)
        if self.origin is not None:
            self.origin.hide_drag_origin()
        if destination is not None:
            target.drop_target = destination
        if target is not None:
            if drop and self.accepted:
                event = QDropEvent(
                    target.viewport().mapFromGlobal(self.position),
                    self.action,
                    self.data,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                target.dropEvent(event)
            target.dragLeaveEvent(QDragLeaveEvent())
        self.preview.deleteLater()
        self.deleteLater()


def drag_block(widget, transfer):
    view = widget if hasattr(widget, "drag_pixmap") else getattr(widget, "source", None)
    origin = widget if hasattr(widget, "origin_marker") else view
    if getattr(widget, "code_active", False):
        rect = widget.code.viewport().rect()
        rect.setHeight(min(rect.height(), widget.code.fontMetrics().lineSpacing() * 4))
        pixmap = widget.code.viewport().grab(rect)
    else:
        pixmap = view.drag_pixmap(transfer) if view is not None else widget.grab()
    hotspot = None
    if view is not None and hasattr(view, "preview_origin"):
        point = QCursor.pos() - view.preview_origin
        size = pixmap.deviceIndependentSize()
        hotspot = QPoint(
            max(0, min(point.x(), int(size.width()) - 8)),
            max(0, min(point.y(), int(size.height()) - 8)),
        )
    return Drag(widget, BlockMime(transfer), pixmap, origin=origin, hotspot=hotspot)
