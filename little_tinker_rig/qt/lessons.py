"""Optional lesson workspaces; the existing document editor owns all Python edits."""

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThreadPool, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.core.lessons import (
    Lesson,
    StudentProject,
    lessons_directory,
    localized,
    pack,
    read_json,
    resource,
    write_json,
)
from little_tinker_rig.i18n import N_, language, tr

from .help import HelpBrowser


class Lessons(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.projects = {}
        self.current = None
        self.export_job = None
        self.page = QWidget()
        layout = QVBoxLayout(self.page)
        self.title = QLabel()
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        split = QSplitter()
        self.stages = QListWidget()
        self.stages.setWordWrap(True)
        self.stages.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stages.currentRowChanged.connect(self.select_stage)
        self.description = HelpBrowser()
        self.description.setOpenLinks(False)
        self.description.anchorClicked.connect(
            lambda url: window.perform(lambda: self.follow_link(url))
        )
        split.addWidget(self.stages)
        split.addWidget(self.description)
        split.setSizes([220, 850])
        layout.addWidget(split, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.actions = {}
        for name, label, callback in (
            ("start", "", self.start_stage),
            ("hint", N_("Next hint"), self.hint),
            ("starter", N_("Open starter program"), self.open_starter),
            ("complete", N_("Mark complete"), self.complete),
            ("previous", N_("← Previous stage"), lambda: self.navigate_stage(-1)),
            ("next", N_("Next stage →"), lambda: self.navigate_stage(1)),
        ):
            action = QAction(label, self)
            action.setToolTip(label)
            action.triggered.connect(
                lambda checked=False, fn=callback: window.perform(fn)
            )
            self.actions[name] = action
        for name, theme, fallback in (
            ("hint", "help-hint", "SP_MessageBoxQuestion"),
            ("starter", "document-new", "SP_FileIcon"),
        ):
            self.actions[name].setIcon(window._icon(theme, fallback))

        def add_actions(row, names):
            for name in names:
                button = QToolButton()
                action = self.actions[name]
                button.setDefaultAction(action)
                if name in ("hint", "starter"):
                    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
                    button.setAccessibleName(action.text())
                # QToolButton shares text/enabled state, but not action visibility.
                action.changed.connect(
                    lambda a=action, b=button: b.setVisible(a.isVisible())
                )
                row.addWidget(button)

        self.explore = QCheckBox(N_("Show all blocks"))
        self.explore.toggled.connect(self.set_explore)
        window.library_pane.layout().insertWidget(3, self.explore)
        self.explore.hide()
        self.guidance = window._action(
            window.view_menu, N_("Current task"), None, self.toggle_guidance
        )
        self.guidance.setCheckable(True)
        self.guidance.setEnabled(False)
        self.card = QWidget()
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(8, 4, 8, 4)
        self.task = QLabel()
        self.task.setWordWrap(True)
        self.task.setTextFormat(self.task.textFormat().PlainText)
        card_layout.addWidget(self.task)
        row = QHBoxLayout()
        self.open_lesson = QPushButton(N_("Open lesson"))
        self.open_lesson.clicked.connect(self.show_stage)
        row.addWidget(self.open_lesson)
        add_actions(row, ("start", "hint", "starter"))
        row.addStretch()
        add_actions(row, ("previous", "complete", "next"))
        hide = QToolButton()
        hide.setText("×")
        hide.setToolTip(N_("Hide task"))
        hide.clicked.connect(lambda: self.guidance.trigger())
        row.addWidget(hide)
        card_layout.addLayout(row)
        card_layout.addWidget(self.status)
        window.workspace_body.insertWidget(0, self.card)
        window.pages.addWidget(self.page)
        window.modes.add_mode("lesson", N_("Lesson"))
        from .assembly import AssemblyWorkspace

        self.assembly_host = AssemblyWorkspace(window.settings)
        self.assembly_host.changed.connect(self.changed)
        self.assembly_host.selection_changed.connect(self.update_card)
        self.assembly_host.failed.connect(window.error)
        window.pages.addWidget(self.assembly_host)
        window.modes.add_mode("assembly", N_("Assembly"))
        window.modes.set_mode_visible(4, False)
        self.card.hide()
        self.menu = window.file_menu.addMenu(N_("Lessons"))
        self.menu.aboutToShow.connect(self.populate)
        window._action(self.menu, N_("Open lesson or project…"), None, self.choose)
        self.new_program_action = window._action(
            window.file_menu,
            N_("New program in lesson project"),
            None,
            self.new_program,
        )
        self.new_program_action.setEnabled(False)
        self.export_action = window._action(
            window.file_menu,
            N_("Export lesson project with resources…"),
            None,
            self.export,
        )
        self.export_action.setEnabled(False)
        window._action(
            window.file_menu, N_("Open robot instructions…"), None, self.open_robot
        )

    def populate(self):
        self.menu.clear()
        self.window._action(self.menu, tr("Open lesson or project…"), None, self.choose)
        self.menu.addSeparator()
        groups = {}
        for path in sorted(lessons_directory().rglob("lesson.json")):
            try:
                lesson = Lesson.load(path.parent)
            except (ValueError, OSError) as error:
                self.window.error(str(error))
                continue
            label = localized(lesson.data["title"], language())
            group = localized(lesson.data.get("group", ""), language())
            if group and group not in groups:
                groups[group] = self.menu.addMenu(group)
            self.window._action(
                groups.get(group, self.menu),
                label,
                None,
                lambda p=path.parent: self.open(p),
            )

    def open_program(self, name):
        if (
            self.current is None
            or name not in self.current.lesson.data.get("programs", {})
            or not name.endswith(".py")
        ):
            raise ValueError("Unknown lesson program")
        self.window.open_document(resource(self.current.root / "programs", name))
        self.window.set_mode(0)

    def follow_link(self, url):
        if url.scheme() == "program":
            self.open_program(url.path())
        elif url.scheme() == "assembly":
            self.open_assembly()
        elif url.scheme() == "lesson":
            self.show_stage()
        elif url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)
        elif not url.path() and url.fragment():
            self.description.scrollToAnchor(url.fragment())
        else:
            resolved = self.description.document().baseUrl().resolved(url)
            if not resolved.isLocalFile():
                return
            path = Path(resolved.toLocalFile()).resolve()
            if self.current and path.is_relative_to(self.current.lesson.root):
                text = path.read_text(encoding="utf-8")
                self.description.document().setBaseUrl(
                    QUrl.fromLocalFile(str(path.parent) + "/")
                )
                self.description.setMarkdown(
                    f"[{tr('Back to task')}](lesson:)\n\n{text}"
                )
                self.description.style_document()
                self.description.scrollToAnchor(url.fragment())

    def show_stage(self):
        self.refresh()
        self.window.set_mode(4)

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            tr("Open lesson or project"),
            "",
            "LittleTinker Rig (*.pylesson *.ltr *.pyblocks)",
        )
        if path:
            self.open(Path(path))

    def open(self, path):
        path = Path(path).resolve()
        project = next((p for p in self.projects.values() if p.path == path), None)
        if project is not None:
            pages = self.window.documents
            page = next(
                (
                    pages.widget(i)
                    for i in range(pages.count())
                    if pages.widget(i).lesson_project is project
                ),
                None,
            )
            if page is not None:
                pages.setCurrentWidget(page)
                self.window.set_mode(project.progress.get("mode", 4))
                return page
        if project is None:
            project = (
                StudentProject.open(path)
                if path.suffix in {".ltr", ".pyblocks"}
                else StudentProject.create(path)
            )
            self.projects[project.root] = project
        # Activating documents may update workspace widgets; preserve the saved mode.
        mode = project.progress.get("mode", 4)
        page = self.window.open_document(project.main)
        page.lesson_project = project
        available = {s.identity for s in page.session.available_snippets}
        missing = {
            identity
            for stage in project.lesson.stages
            for identity in stage.get("blocks", [])
        } - available
        if missing:
            self.window.error(
                tr(
                    "Lesson blocks are unavailable: {blocks}",
                    blocks=", ".join(sorted(missing)),
                )
            )
        workspace = project.root / "workspace.json"
        if workspace.is_file():
            saved = read_json(workspace)
            for name, state in saved.get("documents", {}).items():
                program = resource(project.root / "programs", name)
                if program.is_file():
                    other = self.window.open_document(program)
                    other.lesson_project = project
                    other.restore(other.checkpoint() | state)
            active = resource(project.root / "programs", saved.get("active", "main.py"))
            if active.is_file():
                page = self.window.open_document(active)
        self.activate()
        self.window.set_mode(mode)
        if project.path:
            self.window.remember_file(project.path)
        self.changed()
        return page

    def restore(self, data):
        root = Path(data["root"])
        if root not in self.projects:
            self.projects[root] = StudentProject.restore(data)
        return self.projects[root]

    def activate(self):
        project = getattr(self.window.document_page, "lesson_project", None)
        different = project is not self.current
        self.current = project
        self.new_program_action.setEnabled(project is not None)
        self.export_action.setEnabled(project is not None and self.export_job is None)
        self.guidance.setEnabled(project is not None)
        self.guidance.setChecked(
            project is not None and project.progress.get("guidance", True)
        )
        self.window.modes.set_mode_visible(4, project is not None)
        if project is None:
            if self.window.pages.currentIndex() == 4:
                self.window.set_mode(0)
        else:
            self.refresh()
        if different:
            self.load_robot()
        self.update_card()
        self.palette()

    def refresh(self):
        project = self.current
        if project is None:
            return
        self.title.setText(localized(project.lesson.data["title"], language()))
        self.stages.blockSignals(True)
        self.stages.clear()
        for stage in project.lesson.stages:
            done = stage["id"] in project.progress["completed"]
            item = QListWidgetItem(localized(stage["title"], language()))
            if done:
                icon = QIcon(str(Path(__file__).with_name("icons") / "completed.svg"))
                # Preserve green even when Qt paints the selected row's icon.
                icon.addFile(
                    str(Path(__file__).with_name("icons") / "completed.svg"),
                    mode=QIcon.Mode.Selected,
                )
                item.setIcon(icon)
                item.setToolTip(tr("Completed"))
            self.stages.addItem(item)
        self.stages.setCurrentRow(project.lesson.stages.index(project.stage))
        self.stages.blockSignals(False)
        stage = project.stage
        text = project.lesson.description(stage, language())
        if stage.get("mode") == "assembly":
            text = f"**[{tr('Open 3D building instructions')}](assembly:)**\n\n{text}"
        shown = project.progress.get("hints", {}).get(stage["id"], 0)
        for hint in stage.get("hints", [])[:shown]:
            text += "\n\n---\n\n" + localized(hint, language())
        self.description.document().setBaseUrl(
            QUrl.fromLocalFile(
                str(
                    project.lesson.file(
                        localized(stage["description"], language()).partition("#")[0]
                    ).parent
                )
                + "/"
            )
        )
        self.description.setMarkdown(text)
        self.description.style_document()
        self.description.verticalScrollBar().setValue(0)
        self.task.setText(
            tr(
                "Stage {current} of {total} · {title}",
                current=project.lesson.stages.index(stage) + 1,
                total=len(project.lesson.stages),
                title=localized(stage["title"], language()),
            )
            + "\n"
            + localized(stage.get("goal", stage["title"]), language())
        )
        self.explore.blockSignals(True)
        self.explore.setChecked(project.progress.get("explore", False))
        self.explore.blockSignals(False)
        self.actions["start"].setText(
            tr(
                {
                    "assembly": N_("Open assembly"),
                    "control": N_("Open controls"),
                    "program": N_("Open program"),
                }[stage.get("mode", "program")]
            )
        )
        self.actions["hint"].setVisible(bool(stage.get("hints")))
        self.actions["hint"].setEnabled(shown < len(stage.get("hints", [])))
        self.actions["starter"].setVisible(bool(stage.get("starter")))
        self.update_check()
        self.update_card()

    def update_card(self):
        mode = self.window.pages.currentIndex()
        self.card.setVisible(
            self.current is not None
            and self.guidance.isChecked()
            and (mode != 5 or self.assembly_host.showing_lesson)
        )
        self.open_lesson.setVisible(mode != 4)
        if self.current:
            target = {"program": 0, "control": 1, "assembly": 5}[
                self.current.stage.get("mode", "program")
            ]
            program = self.current.stage.get("program")
            other_program = (
                program
                and self.window.document_page.session.project.path
                != resource(self.current.root / "programs", program)
            )
            self.actions["start"].setVisible(mode != target or bool(other_program))

    def toggle_guidance(self):
        if self.current:
            self.current.progress["guidance"] = self.guidance.isChecked()
            self.update_card()
            self.changed()

    def navigate_stage(self, offset):
        if self.current:
            index = self.current.lesson.stages.index(self.current.stage) + offset
            if 0 <= index < len(self.current.lesson.stages):
                self.select_stage(index)
                self.window.set_mode(4)

    def select_stage(self, index):
        if self.current is None or index < 0:
            return
        self.current.progress["stage"] = self.current.lesson.stages[index]["id"]
        self.refresh()
        self.changed()

    def start_stage(self):
        if self.current:
            mode = self.current.stage.get("mode", "program")
            if mode == "assembly":
                self.open_assembly()
                return
            if mode == "program" and "program" in self.current.stage:
                self.open_program(self.current.stage["program"])
            self.window.set_mode({"program": 0, "control": 1}[mode])

    def open_assembly(self):
        if self.current and self.assembly:
            self.assembly_host.select_lesson()
            steps = self.current.stage.get("assembly")
            if steps and not steps[0] - 1 <= self.assembly.step < steps[1]:
                self.assembly.set_step(steps[0] - 1)
            self.window.set_mode(5)

    def hint(self):
        if self.current:
            stage = self.current.stage
            hints = self.current.progress.setdefault("hints", {})
            hints[stage["id"]] = min(
                hints.get(stage["id"], 0) + 1, len(stage.get("hints", []))
            )
            self.refresh()
            self.changed()
            self.window.set_mode(4)

    def open_starter(self):
        if self.current is None:
            return
        name = self.current.stage.get("starter")
        if name is None:
            self.status.setText(tr("This stage has no starter program."))
            return
        source = self.current.lesson.file(name).read_text(encoding="utf-8")
        self.new_program()
        page = self.window.document_page
        page.session.editor.commit(source, focus=0)
        page.source.refresh_source()
        page.changed.emit()

    def connections(self):
        if self.current is None or "robot" not in self.current.lesson.data:
            return []
        robot = read_json(
            resource(self.current.lesson.root, self.current.lesson.data["robot"])
        )
        required = self.current.stage.get("devices")
        return [
            d
            for d in robot.get("devices", [])
            if required is None or d["instance"] in required
        ]

    def check_ready(self):
        info = self.window.hub_info
        return (
            info.connected
            and info.monitoring
            and all(
                info.ports.get(d["port"], {}).get("type") == d["type"]
                for d in self.connections()
            )
        )

    def update_check(self):
        if self.current is None:
            return
        project = self.current
        done = project.stage["id"] in project.progress["completed"]
        ready = project.stage.get("check") != "devices" or self.check_ready()
        self.actions["complete"].setText(
            tr("Completed") if done else tr("Mark complete")
        )
        self.actions["complete"].setEnabled(not done and ready)
        index = project.lesson.stages.index(project.stage)
        self.actions["previous"].setEnabled(index > 0)
        self.actions["next"].setEnabled(index + 1 < len(project.lesson.stages))
        if len(project.progress["completed"]) == len(project.lesson.stages):
            text = tr(
                "Lesson complete. Save your project to keep the program and progress."
            )
        elif done:
            text = tr(
                "Stage complete. Continue with Next stage, or keep experimenting."
            )
        elif project.stage.get("check") == "devices":
            info = self.window.hub_info
            if not info.connected:
                text = tr("Connect a hub at the top right of the window.")
            elif not info.monitoring:
                text = tr("Open the port monitor to check the expected connections.")
            elif ready:
                text = tr("Connections match the lesson.")
            else:
                from .device import KINDS

                text = tr(
                    "Check connections: {devices}",
                    devices=", ".join(
                        f'{d["port"]} · {tr(KINDS.get(d["type"], "Device"))}'
                        for d in self.connections()
                        if info.ports.get(d["port"], {}).get("type") != d["type"]
                    ),
                )
        else:
            text = tr("Complete the task, then mark it complete.")
        self.status.setText(text)
        self.actions["complete"].setToolTip(text)

    def complete(self):
        if self.current is None:
            return
        if self.current.stage.get("check") == "devices" and not self.check_ready():
            self.update_check()
            return
        completed = self.current.progress["completed"]
        identity = self.current.stage["id"]
        if identity not in completed:
            completed.append(identity)
        self.refresh()
        self.changed()

    def set_explore(self, enabled):
        if self.current:
            self.current.progress["explore"] = enabled
            self.changed()

    def palette(self):
        window = self.window
        project = self.current
        self.explore.setVisible(project is not None)
        restricted = project is not None and not project.progress.get("explore", False)
        ids = frozenset(project.stage.get("blocks", [])) if restricted else None
        level = "all" if project else window.block_level
        window.level_filter.blockSignals(True)
        window.level_filter.select(level)
        window.level_filter.blockSignals(False)
        window.level_filter.setEnabled(project is None)
        stage_ids = frozenset(project.stage.get("blocks", [])) if project else None
        window.scratch.allowed_ids = ids
        if (
            window.library.lesson_ids != ids
            or window.library.stage_ids != stage_ids
            or window.library.level != level
        ):
            window.library.stage_ids = stage_ids
            window.library.lesson_ids = ids
            window.library.filter(window.search.text(), level)
            if restricted:
                window.library.expandAll()
        view = window.editing_source
        view.expression_level = level
        view.expression_ids = ids
        view.expression_operations = (
            frozenset(project.stage.get("operations", [])) if restricted else None
        )

    def changed(self):
        self.palette()
        self.window.refresh_status()
        if hasattr(self.window, "recovery"):
            self.window.recovery.schedule()

    def load_robot(self):
        if self.current and "robot" in self.current.lesson.data:
            self.assembly_host.set_lesson(
                resource(self.current.lesson.root, self.current.lesson.data["robot"]),
                self.current.progress.setdefault("assembly", {}),
            )
        else:
            self.assembly_host.set_lesson(None)

    @property
    def assembly(self):
        return self.assembly_host.lesson_page

    def open_robot(self):
        self.window.set_mode(5)
        self.assembly_host.choose()

    def new_program(self):
        if self.current:
            self.window.open_document(
                self.window.new_document_path(self.current.main.parent)
            )
            self.current.pending = True
            self.window.set_mode(0)

    def release_unused(self, *, all_projects=False):
        if all_projects:
            # Queued hub updates may arrive after the working copies are removed.
            self.current = None
        active = (
            {
                self.window.documents.widget(i).lesson_project.root
                for i in range(self.window.documents.count())
                if self.window.documents.widget(i).lesson_project
            }
            if not all_projects
            else set()
        )
        for root in self.projects.keys() - active:
            self.projects.pop(root).discard_working_copy()

    def save(self, project, *, choose=False):
        path = project.path
        if choose or path is None:
            name, _ = QFileDialog.getSaveFileName(
                self.window,
                tr("Save lesson project"),
                str(path or Path.home() / "lesson.ltr"),
                "LittleTinker Rig (*.ltr)",
            )
            if not name:
                return False
            path = Path(name)
            if path.suffix != ".ltr":
                path = path.with_suffix(".ltr")
        if any(
            other is not project and other.path == path.resolve()
            for other in self.projects.values()
        ):
            raise ValueError(tr("This project is already open. Choose another file."))
        self.store_documents(project)
        project.save(path)
        self.window.remember_file(path)
        self.window.recovery.flush()
        return True

    def store_documents(self, project):
        workspace = {"documents": {}, "active": "main.py"}
        for index in range(self.window.documents.count()):
            page = self.window.documents.widget(index)
            if getattr(page, "lesson_project", None) is project:
                project.pending |= page.dirty
                page.save()
                name = page.session.project.path.relative_to(
                    project.root / "programs"
                ).as_posix()
                checkpoint = page.checkpoint()
                workspace["documents"][name] = {
                    key: checkpoint[key] for key in ("python", "cursor", "scroll")
                }
                if page is self.window.document_page:
                    workspace["active"] = name
        write_json(project.root / "workspace.json", workspace)

    def export(self):
        if self.current is None or self.export_job:
            return
        from .resources import ResourceJob

        project = self.current
        default = (
            project.path.with_stem(project.path.stem + "-offline")
            if project.path
            else Path.home() / "lesson-offline.ltr"
        )
        name, _ = QFileDialog.getSaveFileName(
            self.window,
            tr("Export lesson project with resources"),
            str(default),
            "LittleTinker Rig (*.ltr)",
        )
        if not name:
            return
        destination = Path(name).with_suffix(".ltr").resolve()
        if any(
            p.path == destination or destination.is_relative_to(p.root)
            for p in self.projects.values()
        ):
            raise ValueError(tr("Export to a separate project file"))
        self.store_documents(project)
        project.checkpoint()
        snapshot = pack(project.root)
        self.window.recovery.flush()
        self.export_job = ResourceJob(
            lambda **kwargs: project.export(destination, snapshot=snapshot, **kwargs)
        )
        dialog = QProgressDialog(
            tr("Preparing offline resources…"), tr("Cancel"), 0, 0, self.window
        )
        dialog.setWindowTitle(tr("Export lesson project with resources"))
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.canceled.connect(self.export_job.cancelled.set)
        self.window.destroyed.connect(self.export_job.cancelled.set)
        self.export_action.setEnabled(False)
        self.export_dialog = dialog
        self.export_destination = destination
        self.export_job.signals.progress.connect(self.export_progress)
        self.export_job.signals.ready.connect(self.export_finished)
        dialog.show()
        QThreadPool.globalInstance().start(self.export_job)

    def export_progress(self, received, total):
        self.export_dialog.setRange(0, 1000 if total else 0)
        self.export_dialog.setValue(int(received * 1000 / total) if total else 0)

    def export_finished(self, result, error):
        cancelled = self.export_job.cancelled.is_set()
        self.export_job = None
        self.export_dialog.close()
        self.export_dialog.deleteLater()
        self.export_action.setEnabled(self.current is not None)
        if error and not cancelled:
            self.window.error(error)
        elif not error:
            self.window.statusBar().showMessage(
                tr("Exported {path}", path=str(self.export_destination)), 5000
            )
