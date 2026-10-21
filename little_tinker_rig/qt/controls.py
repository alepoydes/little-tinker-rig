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
    QScrollArea,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.i18n import N_, tr
from little_tinker_rig.pybricks.control import ControlState, Gamepad
from little_tinker_rig.pybricks.devices import SOURCES, MotorBinding, motor_commands

from .theme import colors, svg_icon


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


class Trigger(QSlider):
    """A momentary input returns to neutral on release, including the keyboard."""

    def __init__(self):
        super().__init__(Qt.Orientation.Horizontal)
        self.setRange(0, 100)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setValue(0)

    def keyReleaseEvent(self, event):
        super().keyReleaseEvent(event)
        if not event.isAutoRepeat():
            self.setValue(0)

    def focusOutEvent(self, event):
        self.setValue(0)
        super().focusOutEvent(event)

    def wheelEvent(self, event):
        # A wheel has no release event and cannot operate a momentary control.
        event.ignore()


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
        layout = self.grid = QGridLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setVerticalSpacing(4)
        self.left = Joystick((Qt.Key.Key_A, Qt.Key.Key_D, Qt.Key.Key_W, Qt.Key.Key_S))
        self.right = Joystick()
        self.left.setAccessibleName(N_("Left stick · WASD"))
        self.right.setAccessibleName(N_("Right stick · arrows"))
        self.triggers = []
        self.trigger_panels = []
        self.buttons = {}
        for column, label, name in (
            (0, "LT", N_("Left trigger")),
            (2, "RT", N_("Right trigger")),
        ):
            slider = Trigger()
            slider.setToolTip(label + N_(" · release to return to zero"))
            slider.setAccessibleName(name)
            self.triggers.append(slider)
            panel = QWidget()
            self.trigger_panels.append(panel)
            row = QHBoxLayout(panel)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(label))
            row.addWidget(slider)
            layout.addWidget(panel, 0, column)
        layout.addWidget(self.left, 2, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.right, 3, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        self.stick_labels = [
            QLabel(N_("Left stick · WASD")),
            QLabel(N_("Right stick · arrows")),
        ]
        for column, label in zip((0, 2), self.stick_labels, strict=True):
            layout.addWidget(label, 4, column, alignment=Qt.AlignmentFlag.AlignCenter)
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
        for number, label, name, row, column in (
            (11, "↑", N_("D-pad up"), 0, 1),
            (12, "↓", N_("D-pad down"), 2, 1),
            (13, "←", N_("D-pad left"), 1, 0),
            (14, "→", N_("D-pad right"), 1, 2),
        ):
            button = QPushButton(label)
            button.setToolTip(name)
            button.setAccessibleName(name)
            self.buttons[number] = button
            grid.addWidget(button, row, column)
        layout.addWidget(arrows, 3, 0)
        self.brand_label = QLabel(N_("LittleTinker Rig\nController"))
        layout.addWidget(self.brand_label, 2, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        for number, label in ((4, "View"), (6, "Menu")):
            button = QPushButton(label)
            button.setProperty("translationSources", {})
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
            if number == 5:
                button.setProperty("translationSources", {})
            self.buttons[number] = button
            layout.addWidget(button, 5, column, alignment=Qt.AlignmentFlag.AlignCenter)

    def retranslate(self):
        suffix = tr(" · release to return to zero")
        for label, slider in zip(("LT", "RT"), self.triggers, strict=True):
            slider.setToolTip(label + suffix)

    def compact(self, enabled):
        essentials = (self.left, self.right, *self.trigger_panels, *self.stick_labels)
        for index in range(self.grid.count()):
            widget = self.grid.itemAt(index).widget()
            widget.setVisible(not enabled or widget in essentials)
        for widget, row, column in (
            (self.left, 1 if enabled else 2, 0),
            (self.right, 1 if enabled else 3, 2),
            (self.stick_labels[0], 2 if enabled else 4, 0),
            (self.stick_labels[1], 2 if enabled else 4, 2),
        ):
            self.grid.addWidget(
                widget, row, column, alignment=Qt.AlignmentFlag.AlignCenter
            )
        self.setMaximumHeight(180 if enabled else 350)

    def set_task_spacing(self, compact):
        self.grid.setContentsMargins(
            8 if compact else 24,
            6 if compact else 12,
            8 if compact else 24,
            6 if compact else 12,
        )
        self.grid.setVerticalSpacing(2 if compact else 4)

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
    connection_requested = Signal()
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.info = None
        self.gamepad = None
        self.controller = Controller()
        self.state_label = QLabel()
        self.state_label.setWordWrap(True)
        self.notice = QLabel(
            N_("Connect a virtual or physical hub to use the controller.")
        )
        self.notice.setWordWrap(True)
        self.start = QPushButton(N_("Start manual control"))
        self.start.setObjectName("manualStart")
        self.connect_button = QPushButton(N_("Connect hub"))
        self.connect_button.setObjectName("manualConnect")
        self.connect_button.clicked.connect(self.connection_requested)
        self.apply_theme()
        self.start.setToolTip(N_("Stops the user program and starts the port monitor"))
        self.start.clicked.connect(self.monitor_requested)
        self.armed = QCheckBox(N_("Enable commands"))
        self.armed.toggled.connect(self._armed)
        self.assignments = QPushButton(N_("Configure motors ↓"))
        self.assignments.clicked.connect(self.show_motor_assignments)
        self.physical = QCheckBox(N_("Physical controller"))
        self.physical.setToolTip(N_("Physical Xbox / SDL controller"))
        self.physical.toggled.connect(self._physical)
        self.target = QComboBox()
        self.target.setAccessibleName(N_("Control target"))
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
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(7)
        title = QLabel(N_("Manual control"))
        title.setStyleSheet("font-size: 23px; font-weight: bold")
        layout.addWidget(title)
        layout.addWidget(self.target)
        layout.addWidget(self.notice)
        row = self.action_row = QHBoxLayout()
        row.addWidget(self.connect_button)
        row.addWidget(self.start)
        row.addWidget(self.armed)
        row.addWidget(self.assignments)
        row.addStretch()
        row.addWidget(self.physical)
        layout.addLayout(row)
        self.compact_actions = QWidget()
        self.compact_action_row = QHBoxLayout(self.compact_actions)
        self.compact_action_row.setContentsMargins(0, 0, 0, 0)
        self.compact_action_row.addStretch()
        self.compact_actions.hide()
        layout.addWidget(self.compact_actions)
        body = QHBoxLayout()
        body.addStretch()
        self.controller.setMaximumWidth(720)
        self.controller.setMaximumHeight(350)
        body.addWidget(self.controller, 1)
        body.addStretch()
        self.assignment_hint = QLabel(
            N_(
                "Assign motors to axes or triggers. Scale sets the speed or the angle relative to the center."
            )
        )
        self.assignment_hint.setWordWrap(True)
        layout.addLayout(body)
        layout.addWidget(self.assignment_hint)
        layout.addWidget(self.table)
        layout.addWidget(self.state_label)
        layout.addStretch()
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.sample)
        for button in self.controller.buttons.values():
            button.pressed.connect(self.sample)
            button.released.connect(self.sample)
        self.controller.compact(True)
        self._compact_columns = None
        self._overlay_clearance = 0

    def set_overlay_clearance(self, width):
        width = max(0, width)
        if width == self._overlay_clearance:
            return
        if bool(width) != bool(self._overlay_clearance):
            if width:
                self.action_row.removeWidget(self.assignments)
                self.action_row.removeWidget(self.physical)
                self.compact_action_row.insertWidget(0, self.assignments)
                self.compact_action_row.addWidget(self.physical)
            else:
                self.compact_action_row.removeWidget(self.assignments)
                self.compact_action_row.removeWidget(self.physical)
                self.action_row.insertWidget(2, self.assignments)
                self.action_row.addWidget(self.physical)
            self.compact_actions.setVisible(bool(width))
            self.controller.set_task_spacing(bool(width))
        self._overlay_clearance = width
        self.layout().setContentsMargins(10, 8, 18 + width if width else 10, 8)
        self.layout().setSpacing(4 if width else 7)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 700
        if compact == self._compact_columns:
            return
        self._compact_columns = compact
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if compact:
            for column, width in ((0, 64), (3, 80), (4, 80), (5, 70)):
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(column, width)

    def apply_theme(self):
        self.start.setIcon(
            svg_icon("media-playback-start", tint=colors()["accent_text"])
        )
        self.connect_button.setIcon(
            svg_icon("network-connect", tint=colors()["accent_text"])
        )

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

    def show_motor_assignments(self):
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        if parent is not None:
            parent.ensureWidgetVisible(self.table, 12, 12)
            self.table.setFocus()

    def update_info(self, info):
        self.info = info
        program = self.target.currentData() == "program"
        ready = info.connected and (info.running if program else info.monitoring)
        self.connect_button.setVisible(not info.connected)
        self.connect_button.setEnabled(not info.connection_action)
        if info.connection_action == "connecting":
            self.connect_button.setText(tr("Connecting to hub…"))
        elif info.connection_action == "disconnecting":
            self.connect_button.setText(tr("Disconnecting…"))
        else:
            self.connect_button.setText(tr("Connect hub"))
        self.start.setEnabled(
            info.connected and not info.connection_action and not info.monitoring
        )
        self.start.setVisible(info.connected and not program)
        self.table.setEnabled(not program)
        self.armed.setEnabled(ready)
        if not ready:
            self.armed.setChecked(False)
        if not info.connected:
            notice = tr("Connect a virtual or physical hub to use the controller.")
        elif program:
            notice = tr(
                "Run a program using the Controller module (see Help → Robots and controls)."
            )
        elif ready:
            notice = tr(
                "The port monitor is running. Assign a motor, then enable commands."
            )
        else:
            notice = tr(
                "Manual control stops the running program and opens the port monitor."
            )
        self.notice.setText(notice)
        for row, port in enumerate("ABCDEF"):
            for widget, field in zip(
                self.rows[port],
                (N_("Input"), N_("Mode"), N_("Scale"), N_("Center, °"), N_("Reverse")),
                strict=True,
            ):
                name = tr("Port {port}: {field}", port=port, field=tr(field))
                if widget.accessibleName() != name:
                    widget.setAccessibleName(name)
            data = info.ports.get(port, {})
            motor = data.get("type") == "motor"
            self.table.setRowHidden(row, not motor)
            self.table.item(row, 0).setText(
                port + (f" · {data.get('angle', 0):g}°" if motor else " · —")
            )
            self.rows[port][0].setEnabled(motor)
        visible_rows = sum(not self.table.isRowHidden(row) for row in range(6))
        self.table.setVisible(bool(visible_rows) and not program)
        self.assignment_hint.setVisible(bool(visible_rows) and not program)
        self.assignments.setVisible(bool(visible_rows) and not program)
        self.table.setFixedHeight(
            self.table.horizontalHeader().height() + visible_rows * 30 + 4
        )

    def _armed(self, enabled):
        if enabled and self.gamepad:
            try:
                self.gamepad.read()
            except Exception as error:
                self.armed.setChecked(False)
                self.physical.setChecked(False)
                self.failed.emit(str(error))
        elif not enabled:
            self.controller.display(ControlState())
            if self.info and self.info.monitoring:
                self.drive_requested.emit(())
            elif self.info and self.info.connected and self.info.running:
                self.input_requested.emit(ControlState())

    def _target_changed(self):
        self.armed.setChecked(False)
        self.controller.compact(self.target.currentData() == "motors")
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
            samples = (
                self.gamepad.read_samples()
                if self.gamepad
                else (self.controller.state(),)
            )
            state = samples[-1]
            if self.gamepad:
                self.controller.display(state)
            self.state_label.setText(
                f"LX {state.left_x:+.2f}  LY {state.left_y:+.2f}     RX {state.right_x:+.2f}  RY {state.right_y:+.2f}     LT {state.left_trigger:.2f}  RT {state.right_trigger:.2f}"
            )
            if self.armed.isChecked():
                if self.target.currentData() == "program":
                    for sample in samples:
                        self.input_requested.emit(sample)
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
