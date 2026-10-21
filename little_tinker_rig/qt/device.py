"""Connection choice, hub identity and live port inspection."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
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
from .theme import colors, svg_pixmap


class ConnectDialog(QDialog):
    def __init__(self, parent, *, preferred_transport=None, preferred_model=None):
        super().__init__(parent)
        self.setWindowTitle(N_("Connect hub"))
        self.resize(470, 260)
        layout = QVBoxLayout(self)
        header = QFrame()
        header.setObjectName("dialogHeader")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(16, 13, 16, 13)
        mark = QLabel()
        mark.setPixmap(
            svg_pixmap("network-connect", QSize(30, 30), tint=colors()["accent_text"])
        )
        header_row.addWidget(mark)
        heading = QVBoxLayout()
        heading.setSpacing(2)
        title = QLabel(N_("Connect hub"))
        title.setObjectName("dialogHeaderTitle")
        heading.addWidget(title)
        description = QLabel(N_("Start with a virtual hub or connect your robot."))
        description.setObjectName("dialogHeaderDescription")
        description.setWordWrap(True)
        heading.addWidget(description)
        header_row.addLayout(heading, 1)
        layout.addWidget(header)
        form = self.form = QFormLayout()
        self.transport = QComboBox()
        self.transport.setAccessibleName(N_("Connection"))
        for label, key in (
            (N_("Virtual hub · no hardware needed"), "virtual"),
            ("Bluetooth · Pybricks", "ble"),
            ("USB · Pybricks", "usb"),
        ):
            self.transport.addItem(label, key)
        self.name = QLineEdit()
        self.name.setAccessibleName(N_("Bluetooth hub name"))
        self.name.setPlaceholderText(N_("Empty — first available hub"))
        self.name.setToolTip(
            N_(
                "Enter the Bluetooth hub name, or leave empty for the first available hub."
            )
        )
        self.model = QComboBox()
        self.model.setAccessibleName(N_("Virtual hub model"))
        for label, key in (
            ("Robot Inventor / SPIKE Prime", "inventor"),
            ("BOOST Move Hub", "boost"),
            ("LEGO Technic Hub", "technic"),
        ):
            self.model.addItem(label, key)
        model = (
            preferred_model
            if preferred_model in {"inventor", "boost", "technic"}
            else "inventor"
        )
        self.model.setCurrentIndex(self.model.findData(model))
        transport = (
            preferred_transport
            if preferred_transport in {"virtual", "ble", "usb"}
            else "virtual"
        )
        self.transport.setCurrentIndex(self.transport.findData(transport))
        form.addRow(N_("Connection"), self.transport)
        form.addRow(N_("Bluetooth hub name"), self.name)
        form.addRow(N_("Virtual hub model"), self.model)
        self.name_label = form.labelForField(self.name)
        self.transport.currentIndexChanged.connect(self.update_connection_fields)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        connect_button = buttons.addButton(
            N_("Connect"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        connect_button.setObjectName("dialogPrimary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.help_button = buttons.addButton(
            N_("USB connection help"), QDialogButtonBox.ButtonRole.HelpRole
        )
        self.help_button.setObjectName("dialogHelp")
        self.help_button.clicked.connect(self.reject)
        self.help_button.clicked.connect(parent.show_usb_help)
        layout.addWidget(buttons)
        localize(self)
        self.update_connection_fields()

    def update_connection_fields(self, *_):
        transport = self.transport.currentData()
        virtual = transport == "virtual"
        self.name.setEnabled(not virtual)
        self.model.setEnabled(virtual)
        self.form.setRowVisible(self.name, not virtual)
        self.form.setRowVisible(self.model, virtual)
        self.help_button.setVisible(transport == "usb")
        name_source = (
            N_("USB serial port") if transport == "usb" else N_("Bluetooth hub name")
        )
        placeholder_source = (
            N_("Empty — detect a single USB hub")
            if transport == "usb"
            else N_("Empty — first available hub")
        )
        tooltip_source = (
            N_(
                "Enter a USB serial port such as COM3 or /dev/ttyACM0. Leave empty if only one Pybricks USB hub is connected."
            )
            if transport == "usb"
            else N_(
                "Enter the Bluetooth hub name, or leave empty for the first available hub."
            )
        )
        label_sources = dict(self.name_label.property("translationSources") or {})
        label_sources["text"] = name_source
        self.name_label.setProperty("translationSources", label_sources)
        self.name_label.setText(tr(name_source))
        name_sources = dict(self.name.property("translationSources") or {})
        name_sources.update(
            accessibleName=name_source,
            placeholderText=placeholder_source,
            toolTip=tooltip_source,
        )
        self.name.setProperty("translationSources", name_sources)
        self.name.setAccessibleName(tr(name_source))
        self.name.setPlaceholderText(tr(placeholder_source))
        self.name.setToolTip(tr(tooltip_source))


class DevicePanel(QWidget):
    monitor_requested = Signal()
    disconnect_requested = Signal()
    configure_requested = Signal(str, str, object)

    def __init__(self):
        super().__init__()
        self.info = None
        layout = QVBoxLayout(self)
        self.header = QWidget()
        self.header_grid = QGridLayout(self.header)
        self.header_grid.setContentsMargins(0, 0, 0, 0)
        self.identity = QLabel(N_("No hub connected"))
        self.identity.setWordWrap(True)
        self.identity.setStyleSheet("font-size: 15px; font-weight: bold")
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.header_grid.addWidget(self.identity, 0, 0)
        self.header_grid.addWidget(self.details, 1, 0)
        self.monitor = QPushButton(N_("Open port monitor"))
        self.monitor.setToolTip(
            N_(
                "Replaces the running program with the port monitor. Motors remain stopped."
            )
        )
        self.monitor.clicked.connect(self.monitor_requested)
        self.header_grid.addWidget(self.monitor, 2, 0)
        layout.addWidget(self.header)
        self.port_container = QWidget()
        self.port_grid = QGridLayout(self.port_container)
        self.port_grid.setContentsMargins(0, 0, 0, 0)
        self.port_grid.setSpacing(6)
        layout.addWidget(self.port_container)
        self._bottom_layout = False
        self._visible_ports = tuple("ABCDEF")
        self.rows = {}
        self.port_cards = []
        self.distance_sliders = {}
        for index, port in enumerate("ABCDEF"):
            card = QFrame()
            card.setObjectName("portCard")
            self.port_cards.append(card)
            box = QVBoxLayout(card)
            row = QHBoxLayout()
            label = QLabel(port)
            label.setObjectName("portLetter")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(26, 26)
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
            self.port_grid.addWidget(card, index, 0)
        layout.addStretch()
        self.disconnect = QPushButton(N_("Disconnect hub"))
        self.disconnect.clicked.connect(self.disconnect_requested)
        layout.addWidget(self.disconnect)
        self.apply_theme()

    def set_bottom_layout(self, bottom):
        bottom = bool(bottom)
        if bottom == self._bottom_layout:
            return
        self._bottom_layout = bottom
        self.header_grid.removeWidget(self.monitor)
        if bottom:
            self.header_grid.addWidget(
                self.monitor, 0, 1, 2, 1, Qt.AlignmentFlag.AlignVCenter
            )
        else:
            self.header_grid.addWidget(self.monitor, 2, 0)
        self._arrange_ports()

    def _arrange_ports(self):
        for card in self.port_cards:
            self.port_grid.removeWidget(card)
        columns = 3 if self._bottom_layout else 1
        for index, port in enumerate(self._visible_ports):
            self.port_grid.addWidget(
                self.port_cards[ord(port) - ord("A")], index // columns, index % columns
            )
        for column in range(3):
            self.port_grid.setColumnStretch(column, int(column < columns))

    def apply_theme(self):
        from .theme import colors

        c = colors()
        for card in self.port_cards:
            card.setStyleSheet(
                f"#portCard {{ background: {c['raised']}; "
                f"color: {c['text']}; border-radius: 7px; }}"
            )

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
        identity = " · ".join(part for part in (info.kind, info.firmware) if part)
        status = (
            " · ".join(part for part in (info.transport.upper(), state) if part)
            + battery
        )
        self.details.setText(
            "\n".join(part for part in (identity, status) if part)
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
            for widget, field in (
                (kind, tr("Device")),
                (slider, tr("Sensor value")),
                (self.distance_sliders[port], tr("BOOST distance, %")),
            ):
                name = tr("Port {port}: {field}", port=port, field=field)
                if widget.accessibleName() != name:
                    widget.setAccessibleName(name)
            data = info.ports.get(port, {}) if info.connected else {}
            key = data.get("type", "empty")
            kind.blockSignals(True)
            kind.setCurrentIndex(max(0, kind.findData(key)))
            kind.blockSignals(False)
            kind.setEnabled(virtual and not (info.model == "boost" and port in "AB"))
            kind.parentWidget().setVisible(
                info.connected
                and info.model != "ev3"
                and (not info.ports or port in info.ports)
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
        visible_ports = tuple(
            port
            for port in "ABCDEF"
            if info.connected
            and info.model != "ev3"
            and (not info.ports or port in info.ports)
        )
        if visible_ports != self._visible_ports:
            self._visible_ports = visible_ports
            self._arrange_ports()
