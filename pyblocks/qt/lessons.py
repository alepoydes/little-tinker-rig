"""Optional lesson workspaces; the existing document editor owns all Python edits."""

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThreadPool, QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pyblocks.core.lessons import (
    Lesson,
    StudentProject,
    lessons_directory,
    localized,
    pack,
    read_json,
    resource,
    write_json,
)
from pyblocks.i18n import N_, language, tr

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
        self.stages.currentRowChanged.connect(self.select_stage)
        self.description = HelpBrowser()
        self.description.setOpenExternalLinks(True)
        split.addWidget(self.stages)
        split.addWidget(self.description)
        split.setSizes([220, 850])
        layout.addWidget(split, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        for label, callback in (
            (N_("Start this stage"), self.start_stage),
            (N_("Next hint"), self.hint),
            (N_("Apply starter program…"), self.apply_starter),
            (N_("Mark complete"), self.complete),
        ):
            button = QPushButton(label)
            button.clicked.connect(
                lambda checked=False, fn=callback: window.perform(fn)
            )
            row.addWidget(button)
        layout.addLayout(row)
        self.explore = QCheckBox(N_("Show all blocks"))
        self.explore.toggled.connect(self.set_explore)
        layout.addWidget(self.explore)
        self.card = QGroupBox(N_("Current task"))
        self.card.setCheckable(True)
        self.card.setChecked(True)
        card_layout = QVBoxLayout(self.card)
        self.task = QLabel()
        self.task.setWordWrap(True)
        self.task.setTextFormat(self.task.textFormat().PlainText)
        self.card.toggled.connect(self.task.setVisible)
        card_layout.addWidget(self.task)
        button = QPushButton(N_("Open lesson"))
        button.clicked.connect(lambda: window.set_mode(4))
        card_layout.addWidget(button)
        window.program_documents.layout().insertWidget(0, self.card)
        window.pages.addWidget(self.page)
        window.mode_tabs.addTab(N_("Lesson"))
        # The assembly widget is loaded only when a lesson uses a robot model.
        self.assembly_host = QWidget()
        self.assembly_host.setLayout(QVBoxLayout())
        self.assembly = None
        window.pages.addWidget(self.assembly_host)
        window.mode_tabs.addTab(N_("Assembly"))
        window.mode_tabs.setTabVisible(4, False)
        window.mode_tabs.setTabVisible(5, False)
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

    def populate(self):
        self.menu.clear()
        self.window._action(self.menu, tr("Open lesson or project…"), None, self.choose)
        self.menu.addSeparator()
        for path in sorted(lessons_directory().glob("*/lesson.json")):
            try:
                lesson = Lesson.load(path.parent)
            except (ValueError, OSError) as error:
                self.window.error(str(error))
                continue
            label = localized(lesson.data["title"], language())
            self.window._action(
                self.menu, label, None, lambda p=path.parent: self.open(p)
            )

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            tr("Open lesson or project"),
            "",
            "PyBlocks (*.pylesson *.pyblocks)",
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
                return page
        if project is None:
            project = (
                StudentProject.open(path)
                if path.suffix == ".pyblocks"
                else StudentProject.create(path)
            )
            self.projects[project.root] = project
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
        self.window.set_mode(project.progress.get("mode", 4))
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
        self.card.setVisible(project is not None)
        self.window.mode_tabs.setTabVisible(4, project is not None)
        self.window.mode_tabs.setTabVisible(
            5, project is not None and "robot" in project.lesson.data
        )
        if project is None:
            if self.window.pages.currentIndex() >= 4:
                self.window.set_mode(0)
        else:
            self.refresh()
            if different:
                self.load_robot()
        self.palette()

    def refresh(self):
        project = self.current
        if project is None:
            return
        self.card.setTitle(tr("Current task"))
        self.title.setText(localized(project.lesson.data["title"], language()))
        self.stages.blockSignals(True)
        self.stages.clear()
        for stage in project.lesson.stages:
            done = stage["id"] in project.progress["completed"]
            self.stages.addItem(
                ("✓ " if done else "") + localized(stage["title"], language())
            )
        self.stages.setCurrentRow(project.lesson.stages.index(project.stage))
        self.stages.blockSignals(False)
        stage = project.stage
        text = project.lesson.description(stage, language())
        shown = project.progress.get("hints", {}).get(stage["id"], 0)
        for hint in stage.get("hints", [])[:shown]:
            text += "\n\n---\n\n" + localized(hint, language())
        self.description.document().setBaseUrl(
            QUrl.fromLocalFile(str(project.lesson.root) + "/")
        )
        self.description.setMarkdown(text)
        self.description.style_document()
        self.task.setText(
            localized(stage["title"], language())
            + "\n"
            + localized(stage.get("goal", stage["title"]), language())
        )
        self.explore.blockSignals(True)
        self.explore.setChecked(project.progress.get("explore", False))
        self.explore.blockSignals(False)
        self.update_check()

    def select_stage(self, index):
        if self.current is None or index < 0:
            return
        self.current.progress["stage"] = self.current.lesson.stages[index]["id"]
        self.refresh()
        self.changed()

    def start_stage(self):
        if self.current:
            mode = self.current.stage.get("mode", "program")
            if mode == "assembly" and self.assembly:
                steps = self.current.stage.get("assembly")
                if steps and not steps[0] - 1 <= self.assembly.step < steps[1]:
                    self.assembly.set_step(steps[0] - 1)
            self.window.set_mode({"program": 0, "control": 1, "assembly": 5}[mode])

    def hint(self):
        if self.current:
            stage = self.current.stage
            hints = self.current.progress.setdefault("hints", {})
            hints[stage["id"]] = min(
                hints.get(stage["id"], 0) + 1, len(stage.get("hints", []))
            )
            self.refresh()
            self.changed()

    def apply_starter(self):
        if self.current is None:
            return
        name = self.current.stage.get("starter")
        if name is None:
            self.status.setText(tr("This stage has no starter program."))
            return
        if (
            QMessageBox.question(
                self.window,
                tr("Apply starter program"),
                tr(
                    "Replace this program with the stage starter? You can undo this change."
                ),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        page = self.window.document_page
        source = resource(self.current.lesson.root, name).read_text(encoding="utf-8")
        if page.code_active:
            cursor = page.code.textCursor()
            cursor.select(cursor.SelectionType.Document)
            cursor.insertText(source)
        else:
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
        if self.current and self.current.stage.get("check") == "devices":
            self.status.setText(
                tr("Connections match the lesson.")
                if self.check_ready()
                else tr("Open the port monitor to check the expected connections.")
            )
        else:
            self.status.setText(tr("Complete the task, then mark it complete."))

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
        restricted = project is not None and not project.progress.get("explore", False)
        ids = frozenset(project.stage.get("blocks", [])) if restricted else None
        level = (
            "all"
            if restricted or project is not None
            else window.level_filter.currentData()
        )
        window.level_filter.setEnabled(project is None)
        if window.library.lesson_ids != ids or window.library.level != level:
            window.library.lesson_ids = ids
            window.library.filter(window.search.text(), level)
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
        if self.assembly:
            self.assembly_host.layout().removeWidget(self.assembly)
            self.assembly.deleteLater()
            self.assembly = None
        if self.current and "robot" in self.current.lesson.data:
            from .assembly import AssemblyPage

            self.assembly = AssemblyPage(self.current)
            self.assembly.changed.connect(self.changed)
            self.assembly_host.layout().addWidget(self.assembly)

    def new_program(self):
        if self.current:
            self.window.open_document(
                self.window.new_document_path(self.current.main.parent)
            )
            self.current.pending = True
            self.window.set_mode(0)

    def release_unused(self, *, all_projects=False):
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
                str(path or Path.home() / "lesson.pyblocks"),
                "PyBlocks (*.pyblocks)",
            )
            if not name:
                return False
            path = Path(name)
            if path.suffix != ".pyblocks":
                path = path.with_suffix(".pyblocks")
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
            else Path.home() / "lesson-offline.pyblocks"
        )
        name, _ = QFileDialog.getSaveFileName(
            self.window,
            tr("Export lesson project with resources"),
            str(default),
            "PyBlocks (*.pyblocks)",
        )
        if not name:
            return
        destination = Path(name).with_suffix(".pyblocks").resolve()
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
