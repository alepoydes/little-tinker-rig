"""One asyncio worker for radio I/O; Qt owns widgets and the input sampling timer."""

import asyncio
import codecs
from concurrent.futures import TimeoutError
from threading import Event, Thread

from PySide6.QtCore import QObject, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from pyblocks.pybricks.connection import Connection
from pyblocks.pybricks.control import ControlState, Gamepad


class Joystick(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(150, 150)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.x_value = self.y_value = 0
        self.setToolTip(
            "Drag to steer; release to return to neutral. Arrow keys also work."
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) * 0.4
        painter.setPen(QColor("#78909c"))
        painter.setBrush(QColor("#e5eff1"))
        painter.drawEllipse(center, radius, radius)
        painter.setBrush(QColor("#277d96"))
        painter.drawEllipse(
            center + QPointF(self.x_value * radius, -self.y_value * radius), 14, 14
        )

    def _point(self, event):
        radius = min(self.width(), self.height()) * 0.4
        self.x_value = max(
            -1, min(1, (event.position().x() - self.width() / 2) / radius)
        )
        self.y_value = max(
            -1, min(1, (self.height() / 2 - event.position().y()) / radius)
        )
        self.update()

    def mousePressEvent(self, event):
        self._point(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._point(event)

    def mouseReleaseEvent(self, event):
        self.neutral()

    def keyPressEvent(self, event):
        values = {
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, 1),
            Qt.Key.Key_Down: (0, -1),
        }
        if event.key() in values:
            self.x_value, self.y_value = values[event.key()]
            self.update()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            self.neutral()

    def focusOutEvent(self, event):
        self.neutral()
        super().focusOutEvent(event)

    def neutral(self):
        self.x_value = self.y_value = 0
        self.update()


class Robot(QObject):
    output = Signal(str)
    failed = Signal(str)
    status = Signal(str)
    control_failed = Signal()

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.connection = None
        self.loop = None
        ready = Event()

        def run():
            with asyncio.Runner() as runner:
                self.loop = runner.get_loop()
                decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
                self.connection = Connection(
                    lambda data: self.output.emit(decoder.decode(data))
                )
                ready.set()
                self.loop.run_forever()

        self.thread = Thread(target=run, name="pyblocks-hub", daemon=True)
        self.thread.start()
        if not ready.wait(5):
            raise RuntimeError("Could not start the hub event loop")
        self.dock = None
        self.gamepad = None
        self.pending = None
        self.streaming = False
        self.control_failed.connect(self._stop_controls)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.sample)

    def submit(self, coroutine, message=None):
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)

        def finished(result):
            try:
                result.result()
                if message:
                    self.status.emit(message)
            except Exception as error:
                self.failed.emit(str(error) or type(error).__name__)

        future.add_done_callback(finished)
        return future

    def connect_hub(self, name):
        self.submit(self.connection.connect(name), "Hub connected")

    def run_file(self, path):
        self.submit(self.connection.run(path), "Program started")

    def stop_program(self):
        self.submit(self.connection.stop(), "Program stopped")

    def disconnect_hub(self):
        self.timer.stop()
        self.submit(self.connection.disconnect(), "Hub disconnected")

    def show_controls(self):
        if self.dock is None:
            self.dock = QDockWidget("Controller", self.window)
            panel = QWidget()
            layout = QVBoxLayout(panel)
            self.joystick = Joystick()
            layout.addWidget(self.joystick)
            self.buttons = []
            row = QHBoxLayout()
            for number in range(4):
                button = QPushButton(str(number + 1))
                self.buttons.append(button)
                row.addWidget(button)
            layout.addLayout(row)
            layout.addWidget(QLabel("Slider"))
            self.slider = QSlider(Qt.Orientation.Horizontal)
            self.slider.setRange(0, 100)
            layout.addWidget(self.slider)
            physical = QCheckBox("Physical gamepad")
            physical.toggled.connect(self.enable_gamepad)
            layout.addWidget(physical)
            self.enable = QCheckBox("Send controls (20 Hz)")
            self.enable.toggled.connect(self.enable_controls)
            layout.addWidget(self.enable)
            self.dock.setWidget(panel)
            self.window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
            self.dock.visibilityChanged.connect(
                lambda visible: self.enable.setChecked(False) if not visible else None
            )
        self.dock.show()

    def enable_gamepad(self, enabled):
        try:
            if self.gamepad:
                self.gamepad.close()
            self.gamepad = Gamepad() if enabled else None
        except (ValueError, ImportError) as error:
            self.failed.emit(str(error))

    def enable_controls(self, enabled):
        self.streaming = enabled
        if enabled:
            self.timer.start()
        else:
            self.timer.stop()
            if self.connection.hub:
                self.submit(self.connection.send(ControlState()))

    def sample(self):
        if self.pending and not self.pending.done():
            return  # Coalesce input: never queue stale control frames.
        try:
            state = (
                self.gamepad.read()
                if self.gamepad
                else ControlState(
                    self.joystick.x_value,
                    self.joystick.y_value,
                    buttons=sum(
                        1 << i
                        for i, button in enumerate(self.buttons)
                        if button.isDown()
                    ),
                    slider=self.slider.value() / 100,
                )
            )
            self.pending = self.submit(self.connection.send(state))
            self.pending.add_done_callback(
                lambda result: (
                    self.control_failed.emit()
                    if not result.cancelled() and result.exception()
                    else None
                )
            )
        except Exception as error:
            self.timer.stop()
            self.failed.emit(str(error))

    def _stop_controls(self):
        self.timer.stop()
        if self.dock:
            self.enable.blockSignals(True)
            self.enable.setChecked(False)
            self.enable.blockSignals(False)

    def close(self):
        self.timer.stop()
        if self.gamepad:
            self.gamepad.close()
        future = self.submit(self.connection.disconnect())
        try:
            future.result(timeout=5)
        except TimeoutError:
            future.cancel()
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=5)
