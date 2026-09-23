"""An Xbox-shaped input surface and explicit per-motor assignments."""

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pyblocks.i18n import N_, tr
from pyblocks.pybricks.control import ControlState, Gamepad
from pyblocks.pybricks.devices import SOURCES, MotorBinding, motor_commands


class Joystick(QWidget):
    def __init__(
        self, keys=(Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down)
    ):
        super().__init__()
        self.setFixedSize(100, 100)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.keys = keys
        self.pressed = set()
        self.x_value = self.y_value = 0
        self.setToolTip(
            N_(
                "Drag the stick; release to center it. Keyboard control is also available."
            )
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) * 0.37
        painter.setPen(QPen(QColor("#8296ad"), 2))
        painter.setBrush(QColor("#23364b"))
        painter.drawEllipse(center, radius, radius)
        painter.setPen(QPen(QColor("#465b72"), 1))
        painter.drawLine(center + QPointF(-radius, 0), center + QPointF(radius, 0))
        painter.drawLine(center + QPointF(0, -radius), center + QPointF(0, radius))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#71d1bd"))
        painter.drawEllipse(
            center + QPointF(self.x_value * radius, -self.y_value * radius), 20, 20
        )

    def _point(self, event):
        radius = min(self.width(), self.height()) * 0.37
        x = (event.position().x() - self.width() / 2) / radius
        y = (self.height() / 2 - event.position().y()) / radius
        length = max(1, (x * x + y * y) ** 0.5)
        self.set_values(x / length, y / length)

    def set_values(self, x, y):
        self.x_value, self.y_value = x, y
        self.update()

    def neutral(self):
        self.pressed.clear()
        self.set_values(0, 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self._point(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._point(event)

    def mouseReleaseEvent(self, event):
        self.neutral()

    def keyPressEvent(self, event):
        if event.key() not in self.keys:
            return super().keyPressEvent(event)
        self.pressed.add(event.key())
        self._keyboard()

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            self.pressed.discard(event.key())
            self._keyboard()

    def _keyboard(self):
        left, right, up, down = self.keys
        self.set_values(
            int(right in self.pressed) - int(left in self.pressed),
            int(up in self.pressed) - int(down in self.pressed),
        )

    def focusOutEvent(self, event):
        self.neutral()
        super().focusOutEvent(event)


class Controller(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("controllerSurface")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#controllerSurface { background: #172a3e; border-radius: 35px; }"
            "QLabel { color: #d8e4f0; }"
            "QPushButton { background: #334b64; color: #e7f0f8; border: 1px solid #59718a;"
            "min-width: 30px; min-height: 20px; padding: 2px 7px; border-radius: 11px; font-weight: bold; }"
            "QPushButton:pressed { background: #71d1bd; color: #172a3e; }"
        )
        layout = QGridLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setVerticalSpacing(4)
        self.left = Joystick((Qt.Key.Key_A, Qt.Key.Key_D, Qt.Key.Key_W, Qt.Key.Key_S))
        self.right = Joystick()
        self.triggers = []
        self.buttons = {}
        for column, label in ((0, "LT"), (2, "RT")):
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.sliderReleased.connect(lambda s=slider: s.setValue(0))
            slider.setToolTip(label + N_(" · release to return to zero"))
            self.triggers.append(slider)
            panel = QWidget()
            row = QHBoxLayout(panel)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(label))
            row.addWidget(slider)
            layout.addWidget(panel, 0, column)
        layout.addWidget(self.left, 2, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.right, 3, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            QLabel(N_("Left stick · WASD")),
            4,
            0,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        layout.addWidget(
            QLabel(N_("Right stick · arrows")),
            4,
            2,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        for column, number, label in ((0, 9, "LB"), (2, 10, "RB")):
            button = QPushButton(label)
            self.buttons[number] = button
            layout.addWidget(button, 1, column)
        cluster = QWidget()
        grid = QGridLayout(cluster)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        for number, label, color, row, column in (
            (0, "A", "#5bba75", 2, 1),
            (1, "B", "#ef7779", 1, 2),
            (2, "X", "#6fa8f2", 1, 0),
            (3, "Y", "#e9c969", 0, 1),
        ):
            button = QPushButton(label)
            button.setStyleSheet(f"background: {color}; color: #172a3e")
            self.buttons[number] = button
            grid.addWidget(button, row, column)
        layout.addWidget(cluster, 2, 2)
        arrows = QWidget()
        grid = QGridLayout(arrows)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        for number, label, row, column in (
            (11, "↑", 0, 1),
            (12, "↓", 2, 1),
            (13, "←", 1, 0),
            (14, "→", 1, 2),
        ):
            button = QPushButton(label)
            self.buttons[number] = button
            grid.addWidget(button, row, column)
        layout.addWidget(arrows, 3, 0)
        layout.addWidget(
            QLabel("PYBLOCKS\nCONTROLLER"), 2, 1, alignment=Qt.AlignmentFlag.AlignCenter
        )
        for number, label in ((4, "View"), (6, "Menu")):
            button = QPushButton(label)
            self.buttons[number] = button
            layout.addWidget(
                button,
                3,
                1,
                alignment=(
                    Qt.AlignmentFlag.AlignTop
                    if number == 4
                    else Qt.AlignmentFlag.AlignBottom
                ),
            )
        for column, number, label in ((0, 7, "L3"), (1, 5, "Guide"), (2, 8, "R3")):
            button = QPushButton(label)
            self.buttons[number] = button
            layout.addWidget(button, 5, column, alignment=Qt.AlignmentFlag.AlignCenter)

    def state(self):
        return ControlState(
            self.left.x_value,
            self.left.y_value,
            self.right.x_value,
            self.right.y_value,
            sum(
                1 << number
                for number, button in self.buttons.items()
                if button.isDown()
            ),
            left_trigger=self.triggers[0].value() / 100,
            right_trigger=self.triggers[1].value() / 100,
        )

    def display(self, state):
        self.left.set_values(state.left_x, state.left_y)
        self.right.set_values(state.right_x, state.right_y)
        for slider, value in zip(
            self.triggers, (state.left_trigger, state.right_trigger), strict=True
        ):
            slider.setValue(round(value * 100))
        for number, button in self.buttons.items():
            button.setDown(bool(state.buttons & (1 << number)))


class ControlsPage(QWidget):
    drive_requested = Signal(object)
    input_requested = Signal(object)
    monitor_requested = Signal()
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.info = None
        self.gamepad = None
        self.controller = Controller()
        self.state_label = QLabel()
        self.notice = QLabel(N_("Connect a virtual or physical hub at the top right."))
        self.notice.setWordWrap(True)
        self.start = QPushButton(N_("Start manual control"))
        self.start.setToolTip(N_("Stops the user program and starts the port monitor"))
        self.start.clicked.connect(self.monitor_requested)
        self.armed = QCheckBox(N_("Enable motor commands"))
        self.armed.toggled.connect(self._armed)
        self.physical = QCheckBox(N_("Physical Xbox / SDL controller"))
        self.physical.toggled.connect(self._physical)
        self.target = QComboBox()
        self.target.addItem(N_("Assign motors to sticks and triggers"), "motors")
        self.target.addItem(N_("Send controller input to my program"), "program")
        self.target.currentIndexChanged.connect(self._target_changed)
        self.table = QTableWidget(6, 6)
        self.table.setHorizontalHeaderLabels(
            [
                N_("Port"),
                N_("Input"),
                N_("Mode"),
                N_("Scale"),
                N_("Center, °"),
                N_("Reverse"),
            ]
        )
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setFixedHeight(225)
        self.rows = {}
        source_names = (
            N_("Left X"),
            N_("Left Y"),
            N_("Right X"),
            N_("Right Y"),
            "LT",
            "RT",
        )
        for row, port in enumerate("ABCDEF"):
            self.table.setItem(row, 0, QTableWidgetItem(port))
            source, mode = QComboBox(), QComboBox()
            source.addItem(N_("Unassigned"), None)
            for text, key in zip(source_names, SOURCES, strict=True):
                source.addItem(text, key)
            mode.addItem(N_("Rotation, °/s"), "speed")
            mode.addItem(N_("Servo, °"), "servo")
            scale, center = QDoubleSpinBox(), QDoubleSpinBox()
            scale.setRange(0, 2000)
            scale.setValue(500)
            center.setRange(-3600, 3600)
            center.setEnabled(False)
            reverse = QCheckBox()
            for widget, signal in (
                (source, "currentIndexChanged"),
                (mode, "currentIndexChanged"),
                (scale, "valueChanged"),
                (center, "valueChanged"),
                (reverse, "toggled"),
            ):
                getattr(widget, signal).connect(lambda *_: self.armed.setChecked(False))
            mode.currentIndexChanged.connect(
                lambda index, s=scale, c=center: (
                    s.setValue(90 if index else 500),
                    c.setEnabled(bool(index)),
                )
            )
            for column, widget in enumerate((source, mode, scale, center, reverse), 1):
                self.table.setCellWidget(row, column, widget)
            self.rows[port] = (source, mode, scale, center, reverse)
        layout = QVBoxLayout(self)
        title = QLabel(N_("Manual control"))
        title.setStyleSheet("font-size: 23px; font-weight: bold")
        layout.addWidget(title)
        layout.addWidget(self.target)
        layout.addWidget(self.notice)
        row = QHBoxLayout()
        row.addWidget(self.start)
        row.addWidget(self.armed)
        row.addStretch()
        row.addWidget(self.physical)
        layout.addLayout(row)
        body = QHBoxLayout()
        body.addStretch()
        self.controller.setMaximumWidth(720)
        self.controller.setMaximumHeight(350)
        body.addWidget(self.controller, 1)
        body.addStretch()
        layout.addLayout(body, 1)
        layout.addWidget(self.state_label)
        layout.addWidget(
            QLabel(
                N_(
                    "Assign motors to axes or triggers. Scale sets the speed or the angle relative to the center."
                )
            )
        )
        layout.addWidget(self.table)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.sample)

    def bindings(self):
        return tuple(
            MotorBinding(
                port,
                source.currentData(),
                mode.currentData(),
                scale.value(),
                center.value(),
                reverse.isChecked(),
            )
            for port, (source, mode, scale, center, reverse) in self.rows.items()
            if source.currentData() is not None
            and self.info
            and self.info.ports.get(port, {}).get("type") == "motor"
        )

    def update_info(self, info):
        self.info = info
        program = self.target.currentData() == "program"
        ready = info.connected and (info.running if program else info.monitoring)
        self.start.setEnabled(info.connected and not info.monitoring)
        self.start.setVisible(not program)
        self.table.setEnabled(not program)
        self.armed.setEnabled(ready)
        if not ready:
            self.armed.setChecked(False)
        self.notice.setText(
            tr(
                "Run a program using the Controller module (see Help → Robots and controls)."
            )
            if program
            else (
                tr("The port monitor is running. Assign a motor, then enable commands.")
                if ready
                else (
                    tr(
                        "Manual control stops the running program and opens the port monitor."
                    )
                    if info.connected
                    else tr("Connect a virtual or physical hub at the top right.")
                )
            )
        )
        for row, port in enumerate("ABCDEF"):
            self.table.setRowHidden(row, bool(info.ports) and port not in info.ports)
            data = info.ports.get(port, {})
            motor = data.get("type") == "motor"
            self.table.item(row, 0).setText(
                port + (f" · {data.get('angle', 0):g}°" if motor else " · —")
            )
            self.rows[port][0].setEnabled(motor)
        visible_rows = sum(not self.table.isRowHidden(row) for row in range(6))
        self.table.setFixedHeight(
            self.table.horizontalHeader().height() + visible_rows * 30 + 4
        )

    def _armed(self, enabled):
        if not enabled:
            self.controller.display(ControlState())
            if self.info and self.info.monitoring:
                self.drive_requested.emit(())
            elif self.info and self.info.connected and self.info.running:
                self.input_requested.emit(ControlState())

    def _target_changed(self):
        self.armed.setChecked(False)
        if self.info:
            self.update_info(self.info)

    def _physical(self, enabled):
        self.armed.setChecked(False)
        if self.gamepad:
            self.gamepad.close()
            self.gamepad = None
        self.controller.display(ControlState())
        if enabled:
            try:
                self.gamepad = Gamepad()
            except (ValueError, ImportError, RuntimeError) as error:
                self.physical.setChecked(False)
                self.failed.emit(str(error))

    def sample(self):
        try:
            state = self.gamepad.read() if self.gamepad else self.controller.state()
            if self.gamepad:
                self.controller.display(state)
            self.state_label.setText(
                f"LX {state.left_x:+.2f}  LY {state.left_y:+.2f}     RX {state.right_x:+.2f}  RY {state.right_y:+.2f}     LT {state.left_trigger:.2f}  RT {state.right_trigger:.2f}"
            )
            if self.armed.isChecked():
                if self.target.currentData() == "program":
                    self.input_requested.emit(state)
                else:
                    self.drive_requested.emit(motor_commands(self.bindings(), state))
        except Exception as error:
            self.armed.setChecked(False)
            self.physical.setChecked(False)
            self.failed.emit(str(error))

    def showEvent(self, event):
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        self.armed.setChecked(False)
        self.controller.display(ControlState())
        super().hideEvent(event)

    def close(self):
        self.timer.stop()
        self.armed.setChecked(False)
        if self.gamepad:
            self.gamepad.close()
            self.gamepad = None
