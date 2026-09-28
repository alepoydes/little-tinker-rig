"""Connection choice, hub identity and live port inspection."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.i18n import N_, tr
from little_tinker_rig.pybricks.devices import DEVICE_KINDS as KINDS
from little_tinker_rig.pybricks.devices import describe_device
from little_tinker_rig.pybricks.simulation import SENSOR_VALUES

from .localization import localize


class ConnectDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(N_("Connect hub"))
        self.resize(470, 230)
        layout = QVBoxLayout(self)
        title = QLabel(N_("Start with a virtual hub or connect your robot."))
        title.setWordWrap(True)
        layout.addWidget(title)
        form = QFormLayout()
        self.transport = QComboBox()
        for label, key in (
            (N_("Virtual hub · no hardware needed"), "virtual"),
            ("Bluetooth · Pybricks", "ble"),
            ("USB · Pybricks", "usb"),
        ):
            self.transport.addItem(label, key)
        self.name = QLineEdit()
        self.name.setPlaceholderText(N_("Empty — first available hub"))
        self.name.setEnabled(False)
        self.transport.currentIndexChanged.connect(
            lambda index: self.name.setEnabled(
                self.transport.currentData() != "virtual"
            )
        )
        self.name.setToolTip(
            N_(
                "Bluetooth hub name, or USB serial port such as /dev/ttyACM0 or COM3. Leave empty for automatic discovery."
            )
        )
        self.model = QComboBox()
        for label, key in (
            ("Robot Inventor / SPIKE Prime", "inventor"),
            ("BOOST Move Hub", "boost"),
            ("LEGO Technic Hub", "technic"),
        ):
            self.model.addItem(label, key)
        self.transport.currentIndexChanged.connect(
            lambda index: self.model.setEnabled(
                self.transport.currentData() == "virtual"
            )
        )
        self.transport.setCurrentIndex(self.transport.findData("ble"))
        form.addRow(N_("Connection"), self.transport)
        form.addRow(N_("Hub name / USB port"), self.name)
        form.addRow(N_("Virtual hub model"), self.model)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(N_("Connect"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        help_button = buttons.addButton(
            N_("USB connection help"), QDialogButtonBox.ButtonRole.HelpRole
        )
        help_button.clicked.connect(self.reject)
        help_button.clicked.connect(parent.show_usb_help)
        layout.addWidget(buttons)
        localize(self)


class DevicePanel(QWidget):
    monitor_requested = Signal()
    disconnect_requested = Signal()
    configure_requested = Signal(str, str, object)

    def __init__(self):
        super().__init__()
        self.info = None
        layout = QVBoxLayout(self)
        self.identity = QLabel(N_("No hub connected"))
        self.identity.setWordWrap(True)
        self.identity.setStyleSheet("font-size: 15px; font-weight: bold")
        self.details = QLabel()
        self.details.setWordWrap(True)
        layout.addWidget(self.identity)
        layout.addWidget(self.details)
        self.monitor = QPushButton(N_("Open port monitor"))
        self.monitor.setToolTip(
            N_(
                "Replaces the running program with the port monitor. Motors remain stopped."
            )
        )
        self.monitor.clicked.connect(self.monitor_requested)
        layout.addWidget(self.monitor)
        self.rows = {}
        self.distance_sliders = {}
        for port in "ABCDEF":
            card = QFrame()
            card.setObjectName("portCard")
            card.setStyleSheet("#portCard { background: #edf2f7; border-radius: 7px; }")
            box = QVBoxLayout(card)
            row = QHBoxLayout()
            label = QLabel(port)
            label.setStyleSheet("font-size: 18px; font-weight: bold")
            row.addWidget(label)
            kind = QComboBox()
            for key, text in KINDS.items():
                kind.addItem(text, key)
            kind.model().item(kind.findData("unknown")).setEnabled(False)
            row.addWidget(kind, 1)
            kind.currentIndexChanged.connect(lambda index, p=port: self.configure(p))
            box.addLayout(row)
            value = QLabel("—")
            box.addWidget(value)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.valueChanged.connect(lambda n, p=port: self.configure(p, n))
            box.addWidget(slider)
            distance = QSlider(Qt.Orientation.Horizontal)
            distance.setRange(0, 100)
            distance.setToolTip(N_("BOOST distance, %"))
            distance.valueChanged.connect(
                lambda n, p=port: self.configure(p, {"distance_percent": n})
            )
            box.addWidget(distance)
            self.distance_sliders[port] = distance
            self.rows[port] = (kind, value, slider)
            layout.addWidget(card)
        layout.addStretch()
        self.disconnect = QPushButton(N_("Disconnect hub"))
        self.disconnect.clicked.connect(self.disconnect_requested)
        layout.addWidget(self.disconnect)

    def configure(self, port, value=None):
        if self.info and self.info.transport == "virtual" and self.info.connected:
            kind = self.rows[port][0].currentData()
            self.configure_requested.emit(port, kind, value)

    def update_info(self, info):
        self.info = info
        self.identity.setText(
            (tr("Virtual hub") if info.transport == "virtual" else info.name)
            if info.connected
            else tr("No hub connected")
        )
        state = (
            tr("Program running")
            if info.running
            else tr("Port monitor") if info.monitoring else tr("Idle")
        )
        battery = (
            tr(" · {p0:.2f} V", p0=info.battery_mv / 1000) if info.battery_mv else ""
        )
        self.details.setText(
            f"{info.kind} · {info.firmware}\n{info.transport.upper()} · {state}{battery}"
            if info.connected
            else tr("Connect a hub at the top right of the window.")
        )
        self.monitor.setEnabled(
            info.connected
            and not info.connection_action
            and not info.monitoring
            and info.model != "ev3"
        )
        self.monitor.setToolTip(
            tr("EV3 port monitoring is not supported yet")
            if info.model == "ev3"
            else tr(
                "Replaces the running program with the port monitor. Motors remain stopped."
            )
        )
        self.monitor.setText(
            tr("Stop program and inspect ports")
            if info.running
            else tr("Open port monitor")
        )
        self.disconnect.setEnabled(
            info.connection_action == "connecting"
            or (info.connected and not info.connection_action)
        )
        self.disconnect.setText(
            tr("Cancel connection")
            if info.connection_action == "connecting"
            else tr("Disconnect hub")
        )
        virtual = info.connected and info.transport == "virtual"
        for port, (kind, label, slider) in self.rows.items():
            data = info.ports.get(port, {}) if info.connected else {}
            key = data.get("type", "empty")
            kind.blockSignals(True)
            kind.setCurrentIndex(max(0, kind.findData(key)))
            kind.blockSignals(False)
            kind.setEnabled(virtual and not (info.model == "boost" and port in "AB"))
            kind.parentWidget().setVisible(
                info.model != "ev3" and (not info.ports or port in info.ports)
            )
            text = describe_device(data)
            fresh = info.monitoring or virtual
            label.setText(
                text + (tr(" · previous reading") if data and not fresh else "")
            )
            slider.setVisible(
                virtual and key in {"color", "color_distance", "ultrasonic", "force"}
            )
            if (
                slider.isVisible()
                and not slider.isSliderDown()
                and not slider.hasFocus()
            ):
                field, (_, maximum) = next(iter(SENSOR_VALUES[key].items()))
                slider.blockSignals(True)
                slider.setRange(0, maximum)
                slider.setValue(round(data.get(field, 0)))
                slider.setToolTip(text.split(" · ")[0])
                slider.blockSignals(False)
            distance = self.distance_sliders[port]
            distance.setVisible(virtual and key == "color_distance")
            if not distance.isSliderDown() and not distance.hasFocus():
                distance.blockSignals(True)
                distance.setValue(round(data.get("distance_percent", 50)))
                distance.blockSignals(False)
