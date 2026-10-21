"""Assembly steps and part inspection share the model used by the 3D viewport."""

import json
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap, QShortcut
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

from little_tinker_rig.core.lessons import (
    MAX_ASSEMBLY_STEP,
    camera_values,
    localized,
    resource,
    robot_description,
)
from little_tinker_rig.i18n import N_, language, tr

from .help import HelpBrowser
from .localization import localize
from .resources import ResourceJob
from .theme import colors, svg_pixmap


class PartsList(QListWidget):
    center_requested = Signal()

    def mousePressEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if (
            item is not None
            and event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.setCurrentItem(item)
            self.center_requested.emit()
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton and (
            item is None or (item is self.currentItem() and item.isSelected())
        ):
            self.setCurrentRow(-1)
            self.clearSelection()
            event.accept()
        else:
            super().mousePressEvent(event)


class AssemblyPage(QWidget):
    changed = Signal()

    def __init__(self, path, state=None):
        super().__init__()
        self.state = state if isinstance(state, dict) else {}
        step = self.state.get("step", 0)
        if type(step) is not int or not 0 <= step <= MAX_ASSEMBLY_STEP:
            step = 0
        if "camera" in self.state:
            try:
                camera_values(self.state["camera"])
            except ValueError:
                self.state.pop("camera")
        path = Path(path)
        self.robot = robot_description(path)
        self.root = path.parent
        self.selected_items = ()
        self.scene = None
        self.view = None
        self.view_container = None
        self.job = None
        self.loading_phase = "model"
        self.loading_bytes = (0, 0)
        self.attempted = False
        self.error_kind = None
        self.step = step
        self._overlay_compact = False
        self._restore_sidebar_width = False
        layout = QVBoxLayout(self)
        self.caption = QLabel(tr("Loading robot model…"))
        layout.addWidget(self.caption)
        split = QSplitter()
        self.splitter = split
        self.view_host = QWidget()
        self.view_host.setLayout(QVBoxLayout())
        self.placeholder = QWidget()
        self.placeholder.setObjectName("assemblyPlaceholder")
        placeholder_layout = QVBoxLayout(self.placeholder)
        placeholder_layout.setContentsMargins(24, 24, 24, 24)
        placeholder_layout.addStretch()
        self.placeholder_icon = QLabel()
        self.placeholder_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(self.placeholder_icon)
        self.placeholder_text = QLabel(tr("Loading robot model…"))
        self.placeholder_text.setWordWrap(True)
        self.placeholder_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(self.placeholder_text)
        placeholder_layout.addStretch()
        self.view_host.layout().addWidget(self.placeholder)
        split.addWidget(self.view_host)
        side = QWidget()
        self.sidebar = side
        side.setMinimumWidth(260)
        sidebar = QVBoxLayout(side)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.hide()
        sidebar.addWidget(self.error)
        self.notes = HelpBrowser()
        self.notes.setOpenExternalLinks(True)
        sidebar.addWidget(self.notes, 1)
        self.parts_caption = QLabel(N_("Parts for this step"))
        sidebar.addWidget(self.parts_caption)
        self.parts = PartsList()
        self.parts.setWordWrap(True)
        self.parts.setToolTip(
            N_(
                "Select all copies added in this step. Ctrl+click to center without zooming. Click again or press Escape to clear."
            )
        )
        self.parts.currentRowChanged.connect(self.select_part)
        self.parts.center_requested.connect(self.center_selection)
        sidebar.addWidget(self.parts, 1)
        self.devices = QComboBox()
        self.devices.setToolTip(
            N_(
                "Find a device already installed at this assembly step. This does not check its connection to the hub."
            )
        )
        self.devices.setProperty(
            "translationSources", {"toolTip": self.devices.toolTip()}
        )
        self.devices.hide()
        self.devices.currentIndexChanged.connect(self.select_device)
        sidebar.addWidget(self.devices)
        self.groups = QComboBox()
        self.groups.setToolTip(
            N_(
                "View the whole robot or isolate an assembled section without changing the step."
            )
        )
        self.groups.setProperty(
            "translationSources", {"toolTip": self.groups.toolTip()}
        )
        self.groups.currentIndexChanged.connect(self.focus_group)
        self.group_controls = QWidget()
        group_row = QHBoxLayout(self.group_controls)
        group_row.setContentsMargins(0, 0, 0, 0)
        group_row.addWidget(QLabel(N_("View:")))
        group_row.addWidget(self.groups, 1)
        sidebar.addWidget(self.group_controls)
        self.group_controls.hide()
        split.addWidget(side)
        split.setSizes([900, 340])
        layout.addWidget(split, 1)
        self.selection = QLabel()
        self.selection.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(self.selection, 1)
        self.future = QCheckBox(N_("Show future parts as outlines"))
        self.future.toggled.connect(self.show_future)
        row.addWidget(self.future, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(row)
        clear = QShortcut("Escape", self)
        clear.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        clear.activated.connect(self.clear_selection)
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
        self.reset_button = QPushButton(N_("Recommended view"))
        self.reset_button.clicked.connect(self.reset_camera)
        self.reset_button.hide()
        row.addWidget(self.reset_button)
        layout.addLayout(row)
        self.download_status = QLabel()
        self.download_status.hide()
        layout.addWidget(self.download_status)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)
        controls = QHBoxLayout()
        self.retry = QPushButton(N_("Retry loading parts"))
        self.retry.setObjectName("assemblyRetry")
        self.retry.clicked.connect(lambda: self.load())
        self.retry.hide()
        self.local = QPushButton(N_("Open parts ZIP…"))
        self.local.setObjectName("assemblyLocal")
        self.local.clicked.connect(self.open_library)
        self.local.hide()
        self.cancel = QPushButton(N_("Cancel loading"))
        self.cancel.clicked.connect(
            lambda: self.job.cancelled.set() if self.job else None
        )
        self.cancel.hide()
        for button in (self.retry, self.local, self.cancel):
            controls.addWidget(button)
        layout.addLayout(controls)
        localize(self)
        self.apply_theme()
        self.set_step(self.step)

    def set_overlay_compact(self, compact):
        compact = bool(compact)
        was_compact = self._overlay_compact
        self._overlay_compact = compact
        self.sidebar.setMinimumWidth(210 if compact else 260)
        minimum = QSize(200, 180) if compact else QSize(240, 200)
        if self.view:
            self.view.setMinimumSize(minimum)
        if self.view_container:
            self.view_container.setMinimumSize(minimum)
        self.view_host.setVisible(
            self.error_kind != "display"
            and (self.view_container is not None or not compact)
        )
        if self.job:
            self.download_status.setVisible(self.view_container is not None or compact)
        elif self.error_kind in ("load", "cancelled"):
            self.error.setVisible(self.view_container is not None or compact)
        if was_compact and not compact and self.view_container:
            self._restore_sidebar_width = True
            QTimer.singleShot(0, self, self._restore_wide_sidebar)
        elif compact:
            self._restore_sidebar_width = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._restore_sidebar_width:
            QTimer.singleShot(0, self, self._restore_wide_sidebar)

    def _restore_wide_sidebar(self):
        if (
            not self._restore_sidebar_width
            or self._overlay_compact
            or self.splitter.width() < 600
        ):
            return
        self._restore_sidebar_width = False
        self.splitter.setSizes([self.splitter.width() - 340, 340])

    def apply_theme(self):
        c = colors()
        self.placeholder.setStyleSheet(
            f"#assemblyPlaceholder {{ background: {c['panel']}; "
            f"border: 1px solid {c['border']}; border-radius: 12px; }}"
        )
        self.placeholder_icon.setPixmap(svg_pixmap("brand", QSize(72, 72)))
        self.placeholder_text.setStyleSheet(
            f"color: {c['text']}; font-size: 15px; font-weight: 700;"
        )
        self.error.setStyleSheet(
            f"background: {c['raised']}; color: {c['text']}; "
            f"border: 1px solid {c['border']}; border-radius: 8px; padding: 8px;"
        )

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

    def cancel_loading(self):
        if self.job:
            self.job.cancelled.set()

    def load(self, *, local=None):
        if self.job:
            return
        from little_tinker_rig.core.ldraw_parts import check_cancelled, resolve_library

        path = resource(self.root, self.robot["model"])
        root = self.root
        reference = self.robot.get("library", ".")

        def action(*, progress, cancelled):
            from little_tinker_rig.core.ldraw_cache import load_scene

            library = resolve_library(
                root,
                reference,
                download=True,
                local=local,
                progress=progress,
                cancelled=cancelled,
            )
            # No download progress uses zero bytes; this marks model preparation.
            progress(0, 0)
            scene = load_scene(
                path,
                library,
                library_digest=(
                    reference["sha256"] if isinstance(reference, dict) else None
                ),
                cancelled=cancelled,
            )
            check_cancelled(cancelled)
            return scene

        self.attempted = True
        self.error_kind = None
        self.error.clear()
        self.error.hide()
        self.loading_phase = "model"
        self.loading_bytes = (0, 0)
        self.view_host.show()
        self.placeholder.setVisible(self.view_container is None)
        self.update_loading_status()
        if self._overlay_compact and self.view_container is None:
            self.view_host.hide()
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
        if received == 0 and total == 0:
            self.loading_phase = "prepare"
            self.progress.setRange(0, 0)
            self.update_loading_status()
            return
        self.loading_phase = "parts"
        self.loading_bytes = received, total
        self.progress.setRange(0, 1000 if total else 0)
        self.progress.setValue(int(received * 1000 / total) if total else 0)
        self.update_loading_status()

    def update_loading_status(self):
        if self.loading_phase == "prepare":
            message = tr("Preparing 3D model…")
        elif self.loading_phase == "parts":
            received, total = self.loading_bytes
            message = tr(
                "Loading parts: {current} / {total} MiB",
                current=f"{received / 1024**2:.1f}",
                total=f"{total / 1024**2:.1f}" if total else "?",
            )
        else:
            message = tr("Loading robot model…")
        self.placeholder_text.setText(message)
        self.download_status.setText(message)
        self.download_status.setVisible(
            self.view_container is not None or self._overlay_compact
        )

    def loaded(self, scene, error):
        cancelled = self.job is not None and self.job.cancelled.is_set()
        self.job = None
        self.progress.hide()
        self.download_status.clear()
        self.download_status.hide()
        self.cancel.hide()
        if cancelled:
            scene, error = None, "cancelled"
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
            self.error_kind = "cancelled" if cancelled else "load"
            self.update_error_text()
            self.error.setVisible(
                self.view_container is not None or self._overlay_compact
            )
            self.placeholder_text.setText(self.error.text())
            self.placeholder.setVisible(self.view_container is None)
            if self._overlay_compact and self.view_container is None:
                self.view_host.hide()
            self.reset_button.setVisible(self.view is not None)
            self.notes.setMarkdown(self.step_description())
            return
        self.scene = scene
        self.error_kind = None
        self.error.clear()
        self.error.hide()
        self.view_host.show()
        if self.view:
            self.view.cleanup()
            self.view_host.layout().removeWidget(self.view_container)
            self.view_container.deleteLater()
            self.view = None
            self.view_container = None
        self.slider.setRange(0, scene.step_count - 1)
        if not QApplication.platformName().startswith(("offscreen", "minimal")):
            try:
                from .lego_view import LegoView

                self.view = LegoView(scene, self.state.get("camera"))
                self.view.failed.connect(self.show_error)
                self.view.changed.connect(self.remember_camera)
                self.view.selected.connect(self.select_instance)
                self.view_container = QWidget.createWindowContainer(self.view)
                self.view_container.setMinimumSize(240, 200)
                self.set_overlay_compact(self._overlay_compact)
                self.view_container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                self.view_host.layout().addWidget(self.view_container)
                self.placeholder.hide()
            except (ImportError, ValueError) as error:
                self.show_error(str(error))
        else:
            self.show_error("")
        self.reset_button.setVisible(self.view_available)
        self.set_step(min(self.step, scene.step_count - 1))
        if not self.state.get("camera"):
            self.reset_camera()

    def show_error(self, _error):
        self.error_kind = "display"
        self.update_error_text()
        self.future.hide()
        self.group_controls.hide()
        self.devices.hide()
        self.error.show()
        self.view_host.hide()
        self.reset_button.hide()

    @property
    def view_available(self):
        return self.view is not None and self.error_kind != "display"

    def update_error_text(self):
        if self.error_kind == "load":
            self.error.setText(
                tr(
                    "Could not load the robot model. Retry loading parts; step descriptions remain available."
                )
            )
        elif self.error_kind == "cancelled":
            self.error.setText(
                tr("Robot model loading was cancelled. Retry when ready.")
            )
        elif self.error_kind == "display":
            self.error.setText(
                tr(
                    "3D is unavailable on this display. Step descriptions and parts are still available."
                )
            )

    def step_description(self):
        details = self.robot.get("steps", {}).get(str(self.step + 1), {})
        return localized(
            details.get("text", self.robot.get("description", "")), language()
        )

    def set_step(self, step):
        # Annotations may cover only a few steps. Only the loaded model knows
        # the count; retain the saved request while loading or after a failure.
        count = self.scene.step_count if self.scene else 0
        self.step = max(0, min(step, count - 1) if count else step)
        self.clear_selection()
        self.state["step"] = self.step
        self.back.setEnabled(bool(count) and self.step > 0)
        self.next_step.setEnabled(self.step < count - 1)
        self.slider.setEnabled(bool(count))
        for control in (self.back, self.next_step, self.slider):
            control.setVisible(count > 1)
        self.parts_caption.setText(
            tr("Parts for this step") if count > 1 else tr("Parts")
        )
        self.parts_caption.setVisible(self.scene is not None)
        self.parts.setVisible(self.scene is not None)
        self.future.setVisible(self.view_available and self.step < count - 1)
        self.slider.blockSignals(True)
        self.slider.setValue(self.step)
        self.slider.blockSignals(False)
        self.caption.setText(
            tr(
                "Assembly · step {current} of {total}",
                current=self.step + 1,
                total=count,
            )
            if count > 1
            else localized(self.robot.get("title", ""), language()) or tr("Robot model")
        )
        self.notes.setMarkdown(self.step_description())
        self.changed.emit()
        if self.scene is None:
            return
        self.refresh_choices()
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
            from little_tinker_rig.core.ldraw import rgba

            swatch = QPixmap(18, 18)
            swatch.fill(QColor.fromRgbF(*rgba(color, self.scene.colors)))
            row.setIcon(QIcon(swatch))
        if self.view:
            self.view.step = self.step
        self.show_future(self.future.isChecked())

    def refresh_choices(self):
        # Inspection is restricted to the current construction, never navigation.
        built = {i.identity for i in self.scene.instances if i.step <= self.step}
        self.devices.blockSignals(True)
        self.devices.clear()
        self.devices.addItem(tr("Locate a device"), None)
        for device in self.robot.get("devices", []):
            if device["instance"] in built:
                self.devices.addItem(
                    localized(device["name"], language()) + " · " + device["port"],
                    device["instance"],
                )
        self.devices.blockSignals(False)
        self.devices.setVisible(self.view_available and self.devices.count() > 1)
        selected = self.groups.currentData()
        self.groups.blockSignals(True)
        self.groups.clear()
        self.groups.addItem(tr("Whole robot"), None)
        for group in sorted(
            {
                "/".join(i.groups)
                for i in self.scene.instances
                if i.groups and i.step <= self.step
            }
        ):
            self.groups.addItem(group, group)
        self.groups.setCurrentIndex(max(0, self.groups.findData(selected)))
        self.groups.blockSignals(False)
        self.group_controls.setVisible(self.view_available and self.groups.count() > 1)
        if self.view and self.groups.currentData() != selected:
            self.view.group = None

    def clear_selection(self):
        self.set_selection(())

    def set_selection(self, items, *, source=None):
        self.selected_items = tuple(items)
        if items and source is not None:
            self.groups.blockSignals(True)
            self.groups.setCurrentIndex(0)
            self.groups.blockSignals(False)
            if self.view:
                self.view.group = None
            self.show_future(self.future.isChecked())
        for widget in (self.parts, self.devices):
            if widget is source:
                continue
            widget.blockSignals(True)
            if widget is self.parts:
                widget.setCurrentRow(-1)
                widget.clearSelection()
            else:
                widget.setCurrentIndex(0)
            widget.blockSignals(False)
        if items:
            item = items[0]
            title = localized(
                self.robot.get("parts", {}).get(
                    item.part, self.scene.meshes[item.part].title
                ),
                language(),
            )
            self.selection.setText(
                f"{len(items)} × {title}"
                if len(items) > 1
                else title + " · " + item.identity
            )
        else:
            self.selection.setText(
                tr(
                    "Drag to rotate · Shift+drag to pan · Scroll to zoom · Ctrl+click to center"
                )
                if self.view
                else ""
            )
        if self.view:
            self.view.marker = None
            self.view.select(i.identity for i in items)

    def select_instance(self, identity):
        self.set_selection([i for i in self.scene.instances if i.identity == identity])

    def center_selection(self):
        if self.view:
            self.view.select((i.identity for i in self.selected_items), center=True)

    def select_part(self, row):
        if row < 0:
            self.clear_selection()
        else:
            self.set_selection(list(self.part_groups.values())[row], source=self.parts)

    def select_device(self):
        identity = self.devices.currentData()
        if identity and self.scene:
            self.set_selection(
                [
                    i
                    for i in self.scene.instances
                    if i.identity == identity and i.step <= self.step
                ],
                source=self.devices,
            )
            if self.view:
                device = next(
                    d for d in self.robot["devices"] if d["instance"] == identity
                )
                point = self.robot.get("ports", {}).get(device["port"])
                self.view.marker = (point, device["port"]) if point else None
        else:
            self.clear_selection()

    def focus_group(self):
        self.clear_selection()
        self.show_future(self.future.isChecked())
        if not self.view:
            return
        group = self.groups.currentData()
        indices = [
            i + 1
            for i, item in enumerate(self.scene.instances)
            if not group or item.identity.startswith(group + "/")
        ]
        items = [
            self.scene.instances[i - 1]
            for i in indices
            if self.scene.instances[i - 1].step <= self.step
        ]
        self.view.group = (min(indices), max(indices)) if group and indices else None
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
            self.view.fitted = True
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
        self.future.setVisible(
            self.view_available
            and self.next_step.isEnabled()
            and self.groups.currentData() is None
        )
        if self.view:
            self.view.future = enabled and self.groups.currentData() is None
            self.view.update()

    def retranslate(self):
        self.update_error_text()
        if self.error_kind:
            self.placeholder_text.setText(self.error.text())
        elif self.job:
            self.update_loading_status()
        else:
            self.placeholder_text.setText(tr("Loading robot model…"))
        self.set_step(self.step)


class AssemblyWorkspace(QWidget):
    """One viewer for lesson models and independently opened instructions."""

    changed = Signal()
    selection_changed = Signal()
    failed = Signal(str)
    projects_requested = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.lesson_page = self.free_page = None
        self.free_path = None
        self._overlay_clearance = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.models = QComboBox()
        self.models.setToolTip(N_("Choose one of the open robot models."))
        self.models.setProperty(
            "translationSources", {"toolTip": self.models.toolTip()}
        )
        self.models.currentIndexChanged.connect(self.select_model)
        layout.addWidget(self.models)
        self.pages = QStackedWidget()
        self.empty = QWidget()
        empty_layout = QVBoxLayout(self.empty)
        label = QLabel(
            N_(
                "Assembly steps appear when you open a robot project or a robot.json file."
            )
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch()
        empty_layout.addWidget(label)
        actions = QHBoxLayout()
        actions.addStretch()
        projects = self.projects_button = QPushButton(N_("Choose a project"))
        projects.setObjectName("assemblyProjects")
        projects.clicked.connect(self.projects_requested)
        actions.addWidget(projects)
        button = QPushButton(N_("Open robot instructions…"))
        button.clicked.connect(self.choose)
        actions.addWidget(button)
        actions.addStretch()
        empty_layout.addLayout(actions)
        empty_layout.addStretch()
        self.pages.addWidget(self.empty)
        layout.addWidget(self.pages, 1)
        self.refresh_models()

    def set_overlay_clearance(self, width):
        width = max(0, width)
        if width == self._overlay_clearance:
            return
        self._overlay_clearance = width
        self.layout().setContentsMargins(0, 0, width + 12 if width else 0, 0)
        for page in (self.lesson_page, self.free_page):
            if page:
                page.set_overlay_compact(bool(width))

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
        for key, page in (("free", self.free_page), ("lesson", self.lesson_page)):
            if page:
                title = localized(
                    page.robot.get("title", Path(page.robot["model"]).stem), language()
                )
                self.models.addItem(title, key)
                self.models.setItemData(
                    self.models.count() - 1, str(page.root), Qt.ItemDataRole.ToolTipRole
                )
        self.models.setCurrentIndex(max(0, self.models.findData(selected)))
        self.models.blockSignals(False)
        self.models.setVisible(self.models.count() > 1)
        self.select_model(self.models.currentIndex())

    def select_lesson(self):
        if self.lesson_page:
            self.models.setCurrentIndex(self.models.findData("lesson"))

    def replace_page(self, previous, page):
        if previous:
            previous.cancel_loading()
            self.pages.removeWidget(previous)
            previous.deleteLater()
        if page:
            page.set_overlay_compact(bool(self._overlay_clearance))
            self.pages.addWidget(page)

    def cancel_loading(self):
        for page in (self.lesson_page, self.free_page):
            if page:
                page.cancel_loading()

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
            f"{tr('Robot instructions')} (*.json)",
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
        self.models.setCurrentIndex(self.models.findData("free"))
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
