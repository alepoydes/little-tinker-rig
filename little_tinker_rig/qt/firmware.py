"""Prepare, review and install firmware without a browser or a live editor link."""

import asyncio
import codecs
import re
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from little_tinker_rig.core.paths import firmware_cache
from little_tinker_rig.i18n import language, tr
from little_tinker_rig.pybricks import firmware
from little_tinker_rig.pybricks.simulation import PROFILES


class PrepareJob(QThread):
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action

    def run(self):
        try:
            self.result.emit(self.action())
        except Exception as error:
            self.failed.emit(str(error) or type(error).__name__)


class FirmwareDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Hub firmware"))
        self.resize(760, 680)
        self.cache = firmware_cache()
        self.job = None
        self.package = None
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.installed)
        self.process.errorOccurred.connect(self.process_error)
        self.images = []
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.model, self.kind, self.version = QComboBox(), QComboBox(), QComboBox()
        for key, (name, _, _) in PROFILES.items():
            self.model.addItem(name, key)
        self.kind.addItem(tr("Install Pybricks"), "pybricks")
        self.kind.addItem(tr("Restore LEGO firmware"), "lego")
        form.addRow(tr("Hub model"), self.model)
        form.addRow(tr("Firmware"), self.kind)
        form.addRow(tr("Version"), self.version)
        layout.addLayout(form)
        row = QHBoxLayout()
        self.refresh_button = QPushButton(tr("Refresh versions"))
        self.download_button = QPushButton(tr("Prepare download"))
        self.local_button = QPushButton(tr("Open local firmware…"))
        for button in (self.refresh_button, self.download_button, self.local_button):
            row.addWidget(button)
        layout.addLayout(row)
        self.instructions = QLabel()
        self.instructions.setWordWrap(True)
        layout.addWidget(self.instructions)
        self.details = QLabel()
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.consent = QCheckBox(
            tr(
                "I agree to the firmware license and replacing the current firmware and stored program"
            )
        )
        layout.addWidget(self.consent)
        self.install_button = QPushButton(tr("Install firmware"))
        self.close_button = QPushButton(tr("Close"))
        row = QHBoxLayout()
        row.addWidget(self.install_button)
        row.addWidget(self.close_button)
        layout.addLayout(row)
        self.model.currentIndexChanged.connect(self.selection_changed)
        self.kind.currentIndexChanged.connect(self.selection_changed)
        self.version.currentIndexChanged.connect(self.invalidate)
        self.refresh_button.clicked.connect(self.refresh_catalog)
        self.download_button.clicked.connect(self.prepare_download)
        self.local_button.clicked.connect(self.open_local)
        self.install_button.clicked.connect(self.install)
        self.close_button.clicked.connect(self.reject)
        self.consent.toggled.connect(self.update_buttons)
        try:
            self.images = firmware.catalog(self.cache)
        except (ValueError, OSError, TypeError) as error:
            self.log.setPlainText(str(error))
        self.selection_changed()

    def busy(self):
        return (
            self.job is not None
        ) or self.process.state() != QProcess.ProcessState.NotRunning

    def update_buttons(self):
        idle = not self.busy()
        for widget in (
            self.model,
            self.kind,
            self.version,
            self.refresh_button,
            self.local_button,
            self.close_button,
            self.consent,
        ):
            widget.setEnabled(idle)
        self.download_button.setEnabled(idle and self.version.currentData() is not None)
        self.install_button.setEnabled(
            idle and self.package is not None and self.consent.isChecked()
        )

    def invalidate(self):
        self.package = None
        self.consent.setChecked(False)
        self.details.clear()
        self.update_buttons()

    def selection_changed(self):
        self.version.clear()
        model, kind = self.model.currentData(), self.kind.currentData()
        for image in self.images:
            if (image.model, image.kind) == (model, kind):
                self.version.addItem(image.version, image)
        self.instructions.setText(firmware.instructions(model, kind))
        self.invalidate()

    def start_job(self, action, receiver):
        self.job = PrepareJob(action, self)
        self.job.result.connect(receiver)
        self.job.failed.connect(self.failed)
        self.job.finished.connect(self.job_finished)
        self.progress.setRange(0, 0)
        self.job.start()
        self.update_buttons()

    def job_finished(self):
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        job, self.job = self.job, None
        job.deleteLater()
        self.update_buttons()

    def refresh_catalog(self):
        self.start_job(
            lambda: firmware.catalog(self.cache, refresh=True), self.catalog_ready
        )

    def catalog_ready(self, images):
        self.images = images
        self.selection_changed()

    def prepare_download(self):
        image = self.version.currentData()
        if image:
            self.prepare(lambda: firmware.download(image, self.cache))

    def open_local(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Open firmware"), "", "Firmware (*.zip *.bin)"
        )
        if path:
            self.prepare(lambda: Path(path))

    def prepare(self, source):
        self.invalidate()
        self.log.clear()
        model, kind = self.model.currentData(), self.kind.currentData()
        self.start_job(
            lambda: asyncio.run(firmware.prepare(source(), model, kind)), self.prepared
        )

    def prepared(self, package):
        self.package = package
        self.details.setText(
            f"{self.model.currentText()} · {self.kind.currentText()} · {package.version}\n{package.path}\nSHA-256: {package.digest}"
        )
        self.log.setPlainText(package.license)
        self.update_buttons()

    def failed(self, message):
        self.log.append(message)
        self.update_buttons()

    def install(self):
        if self.package is None or not self.consent.isChecked() or self.busy():
            return
        owner = self.parentWidget()
        if (
            owner is not None
            and getattr(owner, "hub_info", None)
            and owner.hub_info.connected
        ):
            owner.controls.armed.setChecked(False)
            future = owner.robot.disconnect_hub()
            self.start_job(
                lambda: future.result(timeout=20), lambda result: self.begin_flash()
            )
            return
        self.begin_flash()

    def begin_flash(self):
        p = self.package
        self.decoder.reset()
        self.log.clear()
        self.progress.setRange(0, 0)
        self.process.start(
            sys.executable,
            [
                "-u",
                "-m",
                "little_tinker_rig.pybricks.firmware",
                str(p.path),
                p.model,
                p.kind,
                p.digest,
                "--language",
                language(),
            ],
        )
        self.update_buttons()

    def read_output(self):
        text = self.decoder.decode(bytes(self.process.readAllStandardOutput()))
        self.log.insertPlainText(text.replace("\r", "\n"))
        self.log.ensureCursorVisible()
        percentages = re.findall(r"(\d+)%", text)
        if percentages:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, int(percentages[-1])))

    def installed(self, code, status):
        self.read_output()
        self.log.insertPlainText(self.decoder.decode(b"", final=True))
        self.progress.setRange(0, 100)
        success = code == 0 and status == QProcess.ExitStatus.NormalExit
        self.progress.setValue(100 if success else 0)
        message = firmware.result_message(success, self.package.kind)
        self.log.append(message)
        self.consent.setChecked(False)
        self.update_buttons()

    def process_error(self, error):
        self.failed(self.process.errorString())
        if error == QProcess.ProcessError.FailedToStart:
            self.progress.setRange(0, 100)
            self.update_buttons()

    def reject(self):
        if not self.busy():
            super().reject()

    def closeEvent(self, event):
        if self.busy():
            event.ignore()
        else:
            super().closeEvent(event)
