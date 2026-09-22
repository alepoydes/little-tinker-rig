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

from pyblocks.i18n import tr
from pyblocks.pybricks.simulation import SENSOR_VALUES

from .localization import localize

KINDS = {
    "empty": "Пусто",
    "motor": "Мотор",
    "color": "Датчик цвета",
    "color_distance": "Цвет / расстояние BOOST",
    "ultrasonic": "Расстояние",
    "force": "Датчик силы",
    "unknown": "Устройство",
}


class ConnectDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Подключить хаб")
        self.resize(470, 230)
        layout = QVBoxLayout(self)
        title = QLabel("Начните с виртуального хаба или подключите свой робот.")
        title.setWordWrap(True)
        layout.addWidget(title)
        form = QFormLayout()
        self.transport = QComboBox()
        for label, key in (
            ("Виртуальный хаб · без оборудования", "virtual"),
            ("Bluetooth · Pybricks", "ble"),
            ("USB · Pybricks", "usb"),
        ):
            self.transport.addItem(label, key)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Пусто — первый найденный хаб")
        self.name.setEnabled(False)
        self.transport.currentIndexChanged.connect(
            lambda index: self.name.setEnabled(self.transport.currentData() == "ble")
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
        form.addRow("Подключение", self.transport)
        form.addRow("Имя Bluetooth", self.name)
        form.addRow("Модель виртуального хаба", self.model)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Подключить")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
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
        self.identity = QLabel("Хаб не подключён")
        self.identity.setWordWrap(True)
        self.identity.setStyleSheet("font-size: 15px; font-weight: bold")
        self.details = QLabel()
        self.details.setWordWrap(True)
        layout.addWidget(self.identity)
        layout.addWidget(self.details)
        self.monitor = QPushButton("Открыть монитор портов")
        self.monitor.setToolTip(
            "Запустит монитор вместо текущей программы. Моторы останутся остановленными."
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
            distance.setToolTip("Расстояние BOOST, %")
            distance.valueChanged.connect(
                lambda n, p=port: self.configure(p, {"distance_percent": n})
            )
            box.addWidget(distance)
            self.distance_sliders[port] = distance
            self.rows[port] = (kind, value, slider)
            layout.addWidget(card)
        layout.addStretch()
        self.disconnect = QPushButton("Отключить хаб")
        self.disconnect.clicked.connect(self.disconnect_requested)
        layout.addWidget(self.disconnect)

    def configure(self, port, value=None):
        if self.info and self.info.transport == "virtual" and self.info.connected:
            kind = self.rows[port][0].currentData()
            self.configure_requested.emit(port, kind, value)

    def update_info(self, info):
        self.info = info
        self.identity.setText(
            (tr("Виртуальный хаб") if info.transport == "virtual" else info.name)
            if info.connected
            else tr("Хаб не подключён")
        )
        state = (
            tr("Программа работает")
            if info.running
            else tr("Монитор портов") if info.monitoring else tr("Ожидание")
        )
        battery = (
            tr(" · {p0:.2f} В", p0=info.battery_mv / 1000) if info.battery_mv else ""
        )
        self.details.setText(
            f"{info.kind} · {info.firmware}\n{info.transport.upper()} · {state}{battery}"
            if info.connected
            else tr("Подключение — в правом верхнем углу окна.")
        )
        self.monitor.setEnabled(info.connected and not info.monitoring)
        self.monitor.setText(
            tr("Остановить программу и открыть порты")
            if info.running
            else tr("Открыть монитор портов")
        )
        self.disconnect.setEnabled(info.connected)
        virtual = info.connected and info.transport == "virtual"
        for port, (kind, label, slider) in self.rows.items():
            data = info.ports.get(port, {}) if info.connected else {}
            key = data.get("type", "empty")
            kind.blockSignals(True)
            kind.setCurrentIndex(max(0, kind.findData(key)))
            kind.blockSignals(False)
            kind.setEnabled(virtual and not (info.model == "boost" and port in "AB"))
            kind.parentWidget().setVisible(not info.ports or port in info.ports)
            if key == "motor":
                text = tr(
                    "{p0:g}°    {p1:g} °/с",
                    p0=data.get("angle", 0),
                    p1=data.get("speed", 0),
                )
            elif key in {"color", "color_distance"}:
                text = tr("Отражение: {p0:g} %", p0=data.get("reflection", 0))
                if key == "color_distance":
                    text += tr(
                        " · Дальность: {p0:g} %", p0=data.get("distance_percent", 0)
                    )
            elif key == "ultrasonic":
                text = tr("Расстояние: {p0:g} мм", p0=data.get("distance", 0))
            elif key == "force":
                text = tr("Сила: {p0:g} Н", p0=data.get("force", 0))
            else:
                text = (
                    tr("Нет устройства")
                    if key == "empty"
                    else tr("Устройство ID {p0}", p0=data.get("id", "?"))
                )
            fresh = info.monitoring or virtual
            label.setText(
                text + (tr(" · прошлое показание") if data and not fresh else "")
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
