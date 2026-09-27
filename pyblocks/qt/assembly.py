"""Assembly steps and part inspection share the model used by the 3D viewport."""

import json
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pyblocks.core.lessons import localized, resource, robot_description
from pyblocks.i18n import N_, language, tr

from .help import HelpBrowser
from .localization import localize
from .resources import ResourceJob


class AssemblyPage(QWidget):
    changed = Signal()

    def __init__(self, path, state=None):
        super().__init__()
        self.state = state if state is not None else {}
        path = Path(path)
        self.robot = robot_description(path)
        self.root = path.parent
        self.scene = None
        self.view = None
        self.job = None
        self.attempted = False
        self.step = max(0, self.state.get("step", 0))
        layout = QVBoxLayout(self)
        self.caption = QLabel(tr("Loading robot model…"))
        layout.addWidget(self.caption)
        split = QSplitter()
        self.view_host = QWidget()
        self.view_host.setLayout(QVBoxLayout())
        split.addWidget(self.view_host)
        side = QWidget()
        sidebar = QVBoxLayout(side)
        self.notes = HelpBrowser()
        self.notes.setOpenExternalLinks(True)
        sidebar.addWidget(self.notes, 1)
        sidebar.addWidget(QLabel(N_("Parts for this step")))
        self.parts = QListWidget()
        self.parts.setWordWrap(True)
        self.parts.currentRowChanged.connect(self.select_part)
        sidebar.addWidget(self.parts, 1)
        self.devices = QComboBox()
        self.devices.addItem(N_("Locate a device"), None)
        for device in self.robot.get("devices", []):
            self.devices.addItem(
                localized(device["name"], language()) + " · " + device["port"],
                device["instance"],
            )
        self.devices.currentIndexChanged.connect(self.select_device)
        sidebar.addWidget(self.devices)
        self.groups = QComboBox()
        self.groups.addItem(N_("Whole robot"), None)
        self.groups.currentIndexChanged.connect(self.focus_group)
        sidebar.addWidget(self.groups)
        split.addWidget(side)
        split.setSizes([900, 340])
        layout.addWidget(split, 1)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.selection = QLabel()
        self.selection.setWordWrap(True)
        layout.addWidget(self.selection)
        row = QHBoxLayout()
        self.back = QPushButton(N_("Previous step"))
        self.back.clicked.connect(lambda: self.set_step(self.step - 1))
        row.addWidget(self.back)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self.set_step)
        row.addWidget(self.slider, 1)
        self.next_step = QPushButton(N_("Next step"))
        self.next_step.clicked.connect(lambda: self.set_step(self.step + 1))
        row.addWidget(self.next_step)
        reset = QPushButton(N_("Recommended view"))
        reset.clicked.connect(self.reset_camera)
        row.addWidget(reset)
        layout.addLayout(row)
        self.future = QCheckBox(N_("Show future parts as outlines"))
        self.future.toggled.connect(self.show_future)
        layout.addWidget(self.future)
        self.download_status = QLabel()
        layout.addWidget(self.download_status)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)
        controls = QHBoxLayout()
        self.retry = QPushButton(N_("Retry loading parts"))
        self.retry.clicked.connect(lambda: self.load())
        self.retry.hide()
        self.local = QPushButton(N_("Open parts ZIP…"))
        self.local.clicked.connect(self.open_library)
        self.local.hide()
        self.cancel = QPushButton(N_("Cancel download"))
        self.cancel.clicked.connect(
            lambda: self.job.cancelled.set() if self.job else None
        )
        self.cancel.hide()
        for button in (self.retry, self.local, self.cancel):
            controls.addWidget(button)
        layout.addLayout(controls)
        localize(self)
        self.set_step(self.step)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.attempted:
            self.load()

    def open_library(self):
        name, _ = QFileDialog.getOpenFileName(
            self, tr("Open parts ZIP"), "", "ZIP (*.zip)"
        )
        if name:
            self.load(local=Path(name))

    def load(self, *, local=None):
        if self.job:
            return
        from pyblocks.core.ldraw_parts import check_cancelled, resolve_library

        path = resource(self.root, self.robot["model"])
        root = self.root
        reference = self.robot.get("library", ".")

        def action(*, progress, cancelled):
            from pyblocks.core.ldraw import LDraw

            library = resolve_library(
                root,
                reference,
                download=True,
                local=local,
                progress=progress,
                cancelled=cancelled,
            )
            with LDraw(path, library) as reader:
                scene = reader.scene()
            check_cancelled(cancelled)
            return scene

        self.attempted = True
        self.error.clear()
        self.download_status.setText(tr("Loading robot model…"))
        self.progress.setRange(0, 0)
        self.progress.show()
        self.retry.hide()
        self.local.hide()
        self.cancel.show()
        self.job = ResourceJob(action)
        self.destroyed.connect(self.job.cancelled.set)
        self.job.signals.ready.connect(self.loaded)
        self.job.signals.progress.connect(self.download_progress)
        QThreadPool.globalInstance().start(self.job)

    def download_progress(self, received, total):
        self.progress.setRange(0, 1000 if total else 0)
        self.progress.setValue(int(received * 1000 / total) if total else 0)
        self.download_status.setText(
            tr(
                "Loading parts: {current} / {total} MiB",
                current=f"{received / 1024**2:.1f}",
                total=f"{total / 1024**2:.1f}" if total else "?",
            )
        )

    def loaded(self, scene, error):
        self.job = None
        self.progress.hide()
        self.download_status.clear()
        self.cancel.hide()
        if scene is not None:
            identities = {i.identity for i in scene.instances}
            missing = {
                d["instance"] for d in self.robot.get("devices", [])
            } - identities
            if missing:
                error = "Unknown model devices: " + ", ".join(sorted(missing))
        if error:
            self.retry.show()
            self.local.setVisible(isinstance(self.robot.get("library"), dict))
            self.caption.setText(tr("Robot instructions"))
            self.error.setText(tr("3D unavailable: {detail}", detail=error))
            self.notes.setMarkdown(
                localized(self.robot.get("description", ""), language())
            )
            count = max((int(s) for s in self.robot.get("steps", {})), default=1)
            self.slider.setRange(0, count - 1)
            self.set_step(min(self.step, count - 1))
            return
        self.scene = scene
        if self.view:
            self.view.cleanup()
            self.view_host.layout().removeWidget(self.view)
            self.view.deleteLater()
            self.view = None
        self.groups.blockSignals(True)
        while self.groups.count() > 1:
            self.groups.removeItem(1)
        self.groups.blockSignals(False)
        self.slider.setRange(0, scene.step_count - 1)
        for group in sorted({"/".join(i.groups) for i in scene.instances if i.groups}):
            self.groups.addItem(group, group)
        if not QApplication.platformName().startswith(("offscreen", "minimal")):
            try:
                from .lego_view import LegoView

                self.view = LegoView(scene, self.state.get("camera"))
                self.view.failed.connect(
                    lambda error: self.error.setText(
                        tr("3D unavailable: {detail}", detail=error)
                    )
                )
                self.view.changed.connect(self.remember_camera)
                self.view.selected.connect(self.identify)
                self.view_host.layout().addWidget(self.view)
            except (ImportError, ValueError) as error:
                self.error.setText(tr("3D unavailable: {detail}", detail=str(error)))
        else:
            self.error.setText(
                tr(
                    "3D is unavailable on this display. Step descriptions and parts are still available."
                )
            )
        self.set_step(min(self.step, scene.step_count - 1))

    def set_step(self, step):
        count = (
            self.scene.step_count
            if self.scene
            else max((int(s) for s in self.robot.get("steps", {})), default=1)
        )
        self.step = max(0, min(step, count - 1))
        self.state["step"] = self.step
        self.back.setEnabled(self.step > 0)
        self.next_step.setEnabled(self.step < count - 1)
        self.slider.blockSignals(True)
        self.slider.setValue(self.step)
        self.slider.blockSignals(False)
        self.caption.setText(
            tr(
                "Assembly · step {current} of {total}",
                current=self.step + 1,
                total=count,
            )
        )
        details = self.robot.get("steps", {}).get(str(self.step + 1), {})
        self.notes.setMarkdown(
            localized(
                details.get("text", self.robot.get("description", "")), language()
            )
        )
        self.changed.emit()
        if self.scene is None:
            return
        self.items = [item for item in self.scene.instances if item.step == self.step]
        self.part_groups = {}
        for item in self.items:
            self.part_groups.setdefault((item.part, item.color), []).append(item)
        self.parts.clear()
        descriptions = self.robot.get("parts", {})
        for (part, color), items in self.part_groups.items():
            title = localized(
                descriptions.get(part, self.scene.meshes[part].title), language()
            )
            self.parts.addItem(f"{len(items)} × {title}")
            row = self.parts.item(self.parts.count() - 1)
            row.setToolTip(self.scene.meshes[part].title + " · " + part)
            from pyblocks.core.ldraw import rgba

            swatch = QPixmap(18, 18)
            swatch.fill(QColor.fromRgbF(*rgba(color, self.scene.colors)))
            row.setIcon(QIcon(swatch))
        if self.view:
            self.view.step = self.step
            self.view.update()

    def identify(self, identity):
        item = next(i for i in self.scene.instances if i.identity == identity)
        title = localized(
            self.robot.get("parts", {}).get(
                item.part, self.scene.meshes[item.part].title
            ),
            language(),
        )
        self.selection.setText(title + " · " + identity)

    def select_part(self, row):
        if self.view and row >= 0:
            items = list(self.part_groups.values())[row]
            self.view.select(items[0].identity)

    def select_device(self):
        identity = self.devices.currentData()
        if identity and self.scene:
            item = next(
                (i for i in self.scene.instances if i.identity == identity), None
            )
            if item:
                self.set_step(max(self.step, item.step))
                if self.view:
                    self.groups.setCurrentIndex(0)
                    self.view.select(identity)
                    device = next(
                        d for d in self.robot["devices"] if d["instance"] == identity
                    )
                    point = self.robot.get("ports", {}).get(device["port"])
                    self.view.marker = (point, device["port"]) if point else None
                self.identify(identity)

    def focus_group(self):
        if not self.view:
            return
        group = self.groups.currentData()
        items = [
            i
            for i in self.scene.instances
            if not group or i.identity.startswith(group + "/")
        ]
        indices = [
            i + 1
            for i, item in enumerate(self.scene.instances)
            if not group or item.identity.startswith(group + "/")
        ]
        self.view.group = (min(indices), max(indices)) if group and indices else None
        self.view.marker = None
        if group and items:
            self.set_step(max(self.step, max(i.step for i in items)))
        self.view.camera.fit(
            self.scene.bounds(items), self.view.width() / max(self.view.height(), 1)
        )
        self.view.update()
        self.remember_camera()

    def reset_camera(self):
        if self.view:
            visible = [i for i in self.scene.instances if i.step <= self.step]
            self.view.camera.fit(
                self.scene.bounds(visible),
                self.view.width() / max(self.view.height(), 1),
            )
            hint = self.robot.get("steps", {}).get(str(self.step + 1), {}).get("camera")
            if hint:
                self.view.camera.restore(hint)
            self.view.update()
            self.remember_camera()

    def remember_camera(self):
        if self.view:
            self.state["camera"] = self.view.camera.state()
            self.changed.emit()

    def show_future(self, enabled):
        if self.view:
            self.view.future = enabled
            self.view.update()

    def retranslate(self):
        self.devices.setItemText(0, tr("Locate a device"))
        self.groups.setItemText(0, tr("Whole robot"))
        for index, device in enumerate(self.robot.get("devices", []), 1):
            self.devices.setItemText(
                index, localized(device["name"], language()) + " · " + device["port"]
            )
        self.set_step(self.step)


class AssemblyWorkspace(QWidget):
    """One viewer for lesson models and independently opened instructions."""

    changed = Signal()
    selection_changed = Signal()
    failed = Signal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.lesson_page = self.free_page = None
        self.free_path = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.models = QComboBox()
        self.models.setProperty("translationSources", {})
        self.models.currentIndexChanged.connect(self.select_model)
        row.addWidget(self.models, 1)
        button = QPushButton(N_("Open robot instructions…"))
        button.clicked.connect(self.choose)
        row.addWidget(button)
        layout.addLayout(row)
        self.pages = QStackedWidget()
        self.empty = QLabel(
            N_("Open a robot.json file to follow assembly steps without a lesson.")
        )
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pages.addWidget(self.empty)
        layout.addWidget(self.pages, 1)
        self.refresh_models()

    @property
    def showing_lesson(self):
        return (
            self.lesson_page is not None
            and self.pages.currentWidget() is self.lesson_page
        )

    def select_model(self, index):
        page = (
            self.lesson_page
            if self.models.itemData(index) == "lesson"
            else self.free_page
        )
        self.pages.setCurrentWidget(page or self.empty)
        self.selection_changed.emit()

    def refresh_models(self):
        selected = self.models.currentData()
        self.models.blockSignals(True)
        self.models.clear()
        self.models.addItem(
            self.free_path.name if self.free_path else tr("Independent assembly"),
            "free",
        )
        if self.free_path:
            self.models.setItemData(0, str(self.free_path), Qt.ItemDataRole.ToolTipRole)
        if self.lesson_page:
            self.models.addItem(tr("Lesson robot"), "lesson")
        self.models.setCurrentIndex(max(0, self.models.findData(selected)))
        self.models.blockSignals(False)
        self.select_model(self.models.currentIndex())

    def select_lesson(self):
        if self.lesson_page:
            self.models.setCurrentIndex(self.models.findData("lesson"))

    def replace_page(self, previous, page):
        if previous:
            self.pages.removeWidget(previous)
            previous.deleteLater()
        if page:
            self.pages.addWidget(page)

    def set_lesson(self, path, state=None):
        page = AssemblyPage(path, state) if path else None
        self.replace_page(self.lesson_page, page)
        self.lesson_page = page
        if page:
            page.changed.connect(self.changed)
        self.refresh_models()
        self.select_lesson()

    def choose(self):
        name, _ = QFileDialog.getOpenFileName(
            self,
            tr("Open robot instructions"),
            str(self.free_path.parent) if self.free_path else "",
            "Robot instructions (*.json)",
        )
        if name:
            self.open(Path(name))

    def open(self, path, state=None):
        try:
            page = AssemblyPage(path, state)
        except (ValueError, OSError) as error:
            self.failed.emit(str(error))
            return
        self.replace_page(self.free_page, page)
        self.free_page, self.free_path = page, path
        page.changed.connect(self.remember)
        self.refresh_models()
        self.models.setCurrentIndex(0)
        self.remember()

    def remember(self):
        if self.free_page:
            self.settings.setValue("assembly/path", str(self.free_path))
            self.settings.setValue("assembly/state", json.dumps(self.free_page.state))

    def showEvent(self, event):
        super().showEvent(event)
        # Restore lazily; programming and hub control need no model or parts cache.
        if self.free_page is None and not self.showing_lesson:
            path = self.settings.value("assembly/path")
            if path and Path(path).is_file():
                try:
                    state = json.loads(self.settings.value("assembly/state", "{}"))
                except ValueError:
                    state = {}
                self.open(Path(path), state)

    def retranslate(self):
        self.refresh_models()
        for page in (self.free_page, self.lesson_page):
            if page:
                page.retranslate()
