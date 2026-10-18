"""Project-scoped lesson tasks alongside the ordinary desktop workspaces."""

import hashlib
from datetime import datetime
from html import escape
from math import ceil
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QThreadPool, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from little_tinker_rig.core.lessons import (
    Lesson,
    StudentProject,
    lessons_directory,
    localized,
    read_json,
    resource,
    write_json,
)
from little_tinker_rig.core.project import atomic_write
from little_tinker_rig.i18n import N_, language, tr

from .markdown import fit_images
from .theme import colors, recolor_document_links, svg_icon


class TaskMarkdown(QTextBrowser):
    """A Markdown link surface that grows with its content inside the task scroll area."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.document().setDocumentMargin(0)
        self.apply_theme()
        self.document().documentLayout().documentSizeChanged.connect(
            lambda *_: QTimer.singleShot(0, self, self.fit_height)
        )

    def apply_theme(self):
        c = colors()
        self.setStyleSheet(
            f"QTextBrowser {{ background: transparent; color: {c['text']}; "
            "border: 0; }"
        )
        self.document().setDefaultStyleSheet(f"a {{ color: {c['link']}; }}")
        recolor_document_links(self.document())

    def setMarkdown(self, markdown):
        super().setMarkdown(markdown)
        recolor_document_links(self.document())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self, self.fit_height)

    def fit_height(self):
        width = max(1, self.viewport().width())
        if self.document().textWidth() != width:
            self.document().setTextWidth(width)
        fit_images(self)
        height = max(24, ceil(self.document().size().height()) + 4)
        if self.height() != height:
            self.setFixedHeight(height)
            if parent := self.parentWidget():
                parent.updateGeometry()
                if host := parent.parentWidget():
                    if layout := host.layout():
                        layout.invalidate()
                        layout.activate()


LESSON_DOCK_MIN_WIDTH = 1320


class Lessons(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.projects = {}
        self.current = None
        self.export_job = None
        self._updating_panel = False
        self._dock_active = False
        self._transient_hidden = False
        self._narrow = window.width() < LESSON_DOCK_MIN_WIDTH
        self.panel = QWidget()
        self.panel.setObjectName("lessonTaskPanel")
        self.panel.setAccessibleName(N_("Task panel"))
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(10, 8, 10, 8)
        header = QHBoxLayout()
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-weight: 700; font-size: 18px;")
        header.addWidget(self.title, 1)
        collapse = self.collapse_button = QToolButton()
        collapse.setIcon(window._icon("go-next", "SP_ArrowForward"))
        collapse.setToolTip(N_("Collapse task panel"))
        collapse.setAccessibleName(N_("Collapse task panel"))
        collapse.clicked.connect(lambda: self.set_panel_expanded(False))
        header.addWidget(collapse)
        layout.addLayout(header)
        self.summary = QLabel()
        self.summary.setAccessibleName(N_("Lesson progress"))
        self.summary.setStyleSheet("font-size: 12px; font-weight: 600;")
        layout.addWidget(self.summary)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("lessonTaskProgress")
        self.progress_bar.setAccessibleName(N_("Lesson progress"))
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)
        self.task_area = QScrollArea()
        self.task_area.setObjectName("lessonTaskScroll")
        self.task_area.setWidgetResizable(True)
        self.task_area.setFrameShape(QFrame.Shape.NoFrame)
        self.task_content = QWidget()
        self.task_layout = QVBoxLayout(self.task_content)
        self.task_layout.setContentsMargins(0, 4, 2, 4)
        self.task_layout.setSpacing(9)
        self.intro = TaskMarkdown()
        self.intro.anchorClicked.connect(
            lambda url: window.perform(
                lambda: self.follow_task_anchor(None, url, self.intro)
            )
        )
        self.intro.hide()
        self.task_layout.addWidget(self.intro)
        self.task_layout.addStretch(1)
        self.task_area.setWidget(self.task_content)
        layout.addWidget(self.task_area, 1)
        self.cards = {}
        self.status = QLabel()

        window.help_page.lesson_action_requested.connect(
            lambda url: window.perform(lambda: self.follow_link(url))
        )

        # Actions remain shared by menus and shortcuts; task links own the visible UI.
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
        self.guidance = window._action(
            window.view_menu, N_("Task panel"), None, self.toggle_guidance
        )
        self.guidance.setCheckable(True)
        self.guidance.setEnabled(False)

        self.progress_button = QToolButton()
        self.progress_button.setObjectName("lessonProgressChip")
        self.progress_button.setIcon(svg_icon("lesson"))
        self.progress_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.progress_button.setText(N_("Lesson"))
        self.progress_button.setToolTip(N_("Open task panel"))
        self.progress_button.setAccessibleName(N_("Open task panel"))
        self.progress_button.clicked.connect(lambda: self.set_panel_expanded(True))
        self.progress_action = window.main_toolbar.insertWidget(
            window.hub_button_action, self.progress_button
        )
        self.dock = window.dock(
            N_("Task panel"), self.panel, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock.setObjectName("lessonTaskDock")
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.dock.setTitleBarWidget(QWidget())
        self.dock.setMinimumWidth(320)
        self.dock.setMaximumWidth(460)
        self.overlay = QFrame(window.workspace)
        self.overlay.setObjectName("lessonTaskOverlay")
        self.apply_theme()
        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        self.overlay.hide()
        window.setCorner(
            Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea
        )
        window.tabifyDockWidget(window.scratch_dock, self.dock)
        self.dock.visibilityChanged.connect(self._dock_visibility_changed)
        app = QApplication.instance()
        app.installEventFilter(self)
        window.destroyed.connect(lambda *_: app.removeEventFilter(self))
        self.dock.hide()
        self.progress_action.setVisible(False)
        from .assembly import AssemblyWorkspace

        self.assembly_host = AssemblyWorkspace(window.settings)
        self.assembly_host.changed.connect(self.changed)
        self.assembly_host.selection_changed.connect(self.update_card)
        self.assembly_host.failed.connect(window.error)
        window.pages.addWidget(self.assembly_host)
        window.modes.add_mode("assembly", N_("Assembly"))
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

    def apply_theme(self):
        c = colors()
        self.collapse_button.setIcon(self.window._icon("go-next", "SP_ArrowForward"))
        self.progress_button.setIcon(svg_icon("lesson"))
        self.panel.setStyleSheet(
            f"#lessonTaskPanel {{ background: {c['window']}; color: {c['text']}; }}"
            f"#lessonTaskCard {{ background: {c['panel']}; color: {c['text']}; "
            f"border: 1px solid {c['border']}; border-radius: 9px; }}"
            f'#lessonTaskCard[completed="true"] {{ border-color: {c["success"]}; }}'
            f'#lessonTaskCard[selected="true"] {{ border: 2px solid {c["accent"]}; '
            f'background: {c["selected"]}; }}'
            f"#lessonTaskNumber {{ background: {c['raised']}; color: {c['text']}; "
            f"border: 1px solid {c['border']}; border-radius: 12px; "
            "font-weight: 700; min-width: 24px; max-width: 24px; "
            "min-height: 24px; max-height: 24px; }"
            f'#lessonTaskNumber[completed="true"] {{ background: {c["success_fill"]}; '
            "color: white; border-color: transparent; }"
            f'#lessonTaskNumber[selected="true"] {{ background: {c["accent"]}; '
            f'color: {c["accent_text"]}; border-color: transparent; }}'
            f"QProgressBar#lessonTaskProgress {{ background: {c['raised']}; "
            "border: 0; border-radius: 4px; }"
            f"QProgressBar#lessonTaskProgress::chunk {{ background: {c['accent']}; "
            "border-radius: 4px; }"
        )
        self.progress_button.setStyleSheet(
            f"#lessonProgressChip {{ background: {c['selected']}; color: {c['text']}; "
            f"border: 1px solid {c['border']}; border-radius: 7px; padding: 5px 8px; }}"
            f"#lessonProgressChip:hover {{ background: {c['hover']}; }}"
        )
        self.overlay.setStyleSheet(
            f"#lessonTaskOverlay {{ background: {c['window']}; "
            f"border: 1px solid {c['border']}; border-radius: 8px; }}"
        )
        self.intro.apply_theme()
        for widgets in self.cards.values():
            title = widgets["title"]
            title.setText(
                f'<a href="task:select" style="color:{c["text"]}; '
                'text-decoration:none; font-weight:600;">'
                f"{escape(title.accessibleName())}</a>"
            )
            widgets["body"].apply_theme()
            widgets["status"].setStyleSheet(f"color: {c['muted']}; font-size: 11px;")

    def populate(self):
        self.menu.clear()
        self.window._action(self.menu, tr("Open lesson or project…"), None, self.choose)
        if self.current and self.current.data.get("origin"):
            restart = self.window._action(
                self.menu,
                tr("Start new attempt"),
                None,
                lambda: self.open(Path(self.current.data["origin"]), new=True),
            )
            restart.setEnabled(Path(self.current.data["origin"]).exists())
        attempts = StudentProject.attempts()
        if attempts:
            own = self.menu.addMenu(tr("My lesson attempts"))
            groups = {}
            for attempt in attempts:
                title = localized(attempt.lesson.data["title"], language())
                if title not in groups:
                    groups[title] = own.addMenu(title.replace("&", "&&"))
                group = groups[title]
                when = datetime.fromtimestamp(attempt.data["opened"] / 1e9)
                label = when.strftime("%Y-%m-%d %H:%M")
                action = group.addAction(label)
                action.setToolTip(str(attempt.root))
                action.triggered.connect(
                    lambda checked=False, project=attempt: self.window.perform(
                        lambda: self.open(Path(project.data["origin"]), attempt=project)
                    )
                )
        self.menu.addSeparator()
        guided = self.menu.addMenu(tr("Guided lessons"))
        projects = self.menu.addMenu(tr("Explore projects"))
        groups = {}
        for path in sorted(lessons_directory().rglob("lesson.json")):
            try:
                lesson = Lesson.load(path.parent)
            except (ValueError, OSError) as error:
                self.window.error(str(error))
                continue
            label = localized(lesson.data["title"], language())
            group = localized(lesson.data.get("group", ""), language())
            parent = projects if lesson.data.get("kind") == "project" else guided
            key = (parent, group)
            if group and key not in groups:
                groups[key] = parent.addMenu(group)
            self.window._action(
                groups.get(key, parent),
                label,
                None,
                lambda p=path.parent: self.open(p),
            )

    def open_program(self, name):
        if (
            self.current is None
            or name
            not in (
                *self.current.lesson.data.get("programs", {}),
                self.current.main.relative_to(
                    self.current.root / "programs"
                ).as_posix(),
            )
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
        elif url.scheme() == "control":
            self.window.set_mode(1)
        elif url.scheme() == "devices":
            self.window.device_dock.show()
            self.window.device_dock.raise_()
        elif url.scheme() == "connect":
            self.window.connect_hub()
        elif url.scheme() == "scratch":
            name = (
                url.path()
                or self.current.main.relative_to(
                    self.current.root / "programs"
                ).as_posix()
            )
            self.open_program(name)
            self.window.scratch_dock.show()
            self.window.scratch_dock.raise_()
        elif url.scheme() == "lesson":
            self.show_stage()

    def show_stage(self):
        if self.current:
            self.window.help_page.show_lesson_stage(
                self.current.lesson, self.current.stage
            )
            self.window.set_mode(2)
            self._collapse_for_destination()

    def follow_task_link(self, link):
        if self.current is None:
            return
        kind = link["kind"]
        target = link.get("target")
        if kind == "markdown":
            name = localized(target, language())
            self.window.help_page.show_lesson_material(
                self.current.lesson, name, localized(link["label"], language())
            )
            self.window.set_mode(2)
            self._collapse_for_destination()
        elif kind in ("program", "scratch"):
            self.window.open_document(resource(self.current.root / "programs", target))
            self.window.set_mode(0)
            if kind == "scratch":
                self.window.scratch_dock.show()
                self.window.scratch_dock.raise_()
        elif kind == "assembly":
            self.open_assembly()
        elif kind == "control":
            self.window.set_mode(1)
        elif kind == "devices":
            self.window.device_dock.show()
            self.window.device_dock.raise_()
        elif kind == "connect":
            self.window.connect_hub()

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            tr("Open lesson or project"),
            "",
            "LittleTinker Rig (*.pylesson *.ltr *.pyblocks)",
        )
        if path:
            self.open(Path(path))

    def saved_workspace(self, project):
        path = project.root / "workspace.json"
        if not path.is_file():
            return None
        try:
            saved = read_json(path)
            if not isinstance(saved, dict) or not isinstance(
                saved.get("documents", {}), dict
            ):
                raise ValueError("Invalid lesson workspace")
            programs = project.root / "programs"
            active = saved.get("active", "main.py")
            resource(programs, active)
            documents = {}
            for name, state in saved.get("documents", {}).items():
                resource(programs, name)
                if not isinstance(state, dict):
                    raise ValueError("Invalid lesson tab state")
                for key, value in state.items():
                    if key == "python" and type(value) is not bool:
                        raise ValueError("Invalid lesson tab state")
                    if key in ("cursor", "scroll") and (
                        type(value) is not int or not 0 <= value <= 2**31 - 1
                    ):
                        raise ValueError("Invalid lesson tab state")
                documents[name] = {
                    key: state[key]
                    for key in ("python", "cursor", "scroll")
                    if key in state
                }
            return {"documents": documents, "active": active}
        except (OSError, ValueError, TypeError):
            message = tr(
                "Lesson tab layout could not be restored. Program files are still available."
            )
            self.window.statusBar().showMessage(message, 15000)
            self.window.append_output(message + "\n")
            return None

    def open(self, path, *, new=False, attempt=None):
        path = Path(path).resolve()
        template = path.suffix not in {".ltr", ".pyblocks"}
        created = False
        if attempt is not None:
            project = self.projects.get(attempt.root, attempt)
        elif new:
            project = None
        elif template:
            project = max(
                (
                    p
                    for p in self.projects.values()
                    if p.retain and p.data.get("origin") == str(path)
                ),
                key=lambda p: p.data.get("opened", 0),
                default=None,
            )
        else:
            project = next((p for p in self.projects.values() if p.path == path), None)
            if project is None:
                saved = [p for p in StudentProject.attempts() if p.path == path]
                if saved:
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    project = next((p for p in saved if p.disk_hash == digest), None)
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
                project.remember_opened()
                pages.setCurrentWidget(page)
                self.window.help_page.show_lesson_stage(project.lesson, project.stage)
                self.window.set_mode(2)
                self._collapse_for_destination()
                return page
        if project is None:
            if template:
                project = None if new else StudentProject.latest(path)
                if project is None:
                    project = StudentProject.create(path)
                    created = True
            else:
                project = StudentProject.open(path)
            self.projects[project.root] = project
        else:
            self.projects[project.root] = project
        if project.retain:
            for other in QApplication.topLevelWidgets():
                manager = getattr(other, "lessons", None)
                if other is self.window or manager is None:
                    continue
                if getattr(getattr(other, "recovery", None), "closed", False):
                    continue
                pages = other.documents
                owner_page = next(
                    (
                        pages.widget(i)
                        for i in range(pages.count())
                        if getattr(pages.widget(i).lesson_project, "root", None)
                        == project.root
                    ),
                    None,
                )
                if owner_page is not None:
                    owner_page.lesson_project.remember_opened()
                    pages.setCurrentWidget(owner_page)
                    other.help_page.show_lesson_stage(
                        owner_page.lesson_project.lesson,
                        owner_page.lesson_project.stage,
                    )
                    other.set_mode(2)
                    manager._collapse_for_destination()
                    other.show()
                    other.raise_()
                    other.activateWindow()
                    self.projects.pop(project.root, None)
                    return owner_page
        saved = self.saved_workspace(project)
        project.remember_opened()
        page = self.window.open_document(project.main)
        page.lesson_project = project
        if saved is not None:
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
        if created:
            self.window.help_page.show_lesson_home(project.lesson)
        else:
            self.window.help_page.show_lesson_stage(project.lesson, project.stage)
        self.window.set_mode(2)
        self._collapse_for_destination()
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
            project is not None and project.progress.get("panel_expanded", True)
        )
        if project is not None:
            self.refresh(reveal=different)
        self.window.help_page.set_lesson(project.lesson if project else None)
        if different:
            self.load_robot()
        self.update_card()
        self.update_panel_visibility()
        self.palette()

    def _task_links(self, stage):
        def link(label, destination):
            label = label.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
            return f"[{label}]({destination})"

        links = [link(tr("Instructions"), "task:instructions")]
        mode = stage.get("mode", "program")
        links.append(
            link(
                tr(
                    {
                        "assembly": N_("Assembly"),
                        "control": N_("Controls"),
                        "program": N_("Program"),
                    }[mode]
                ),
                f"task:{mode}",
            )
        )
        if stage.get("blocks"):
            links.append(link(tr("Suggested blocks"), "task:blocks"))
        if stage.get("starter"):
            links.append(link(tr("Open starter program"), "task:starter"))
        shown = self.current.progress.get("hints", {}).get(stage["id"], 0)
        if shown < len(stage.get("hints", [])):
            links.append(link(tr("Next hint"), "task:hint"))
        for index, extra in enumerate(stage.get("links", [])):
            links.append(
                link(localized(extra["label"], language()), f"task:extra/{index}")
            )
        return " · ".join(links)

    def _task_markdown(self, stage):
        text = self.current.lesson.panel_text(stage, language())
        shown = self.current.progress.get("hints", {}).get(stage["id"], 0)
        for hint in stage.get("hints", [])[:shown]:
            text += "\n\n> **" + tr("Hint") + ":** " + localized(hint, language())
        if stage.get("panel_actions", True):
            text += "\n\n" + self._task_links(stage)
        return text

    def _material_base(self, name):
        return QUrl.fromLocalFile(
            str(self.current.lesson.file(name.split("#", 1)[0]).parent) + "/"
        )

    def _build_card(self, stage, index):
        identity = stage["id"]
        title = localized(stage["title"], language())
        card = QFrame()
        card.setObjectName("lessonTaskCard")
        card.setAccessibleName(title)
        card.setProperty("selected", identity == self.current.stage["id"])
        card.setProperty("completed", identity in self.current.progress["completed"])
        frame = QVBoxLayout(card)
        frame.setContentsMargins(10, 8, 10, 8)
        frame.setSpacing(5)
        header = QHBoxLayout()
        check = QCheckBox()
        check.setAccessibleName(tr("Mark {title} complete", title=title))
        check.setToolTip(title)
        check.blockSignals(True)
        check.setChecked(identity in self.current.progress["completed"])
        check.blockSignals(False)
        check.toggled.connect(
            lambda checked, key=identity: self.set_completion(key, checked)
        )
        header.addWidget(check)
        number = QLabel(str(index + 1))
        number.setObjectName("lessonTaskNumber")
        number.setProperty("selected", identity == self.current.stage["id"])
        number.setProperty("completed", identity in self.current.progress["completed"])
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(number)
        name = QLabel(
            f'<a href="task:select" style="color:{colors()["text"]}; '
            'text-decoration:none; font-weight:600;">'
            f"{escape(title)}</a>"
        )
        name.setCursor(Qt.CursorShape.PointingHandCursor)
        name.setWordWrap(True)
        name.setAccessibleName(title)
        name.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        name.linkActivated.connect(lambda _, row=index: self.open_task(row))
        header.addWidget(name, 1)
        points = QLabel(f"★ {stage.get('points', 1)}")
        points.setToolTip(tr("Points for this task"))
        header.addWidget(points)
        frame.addLayout(header)
        body = TaskMarkdown()
        if "panel" in stage:
            body.document().setBaseUrl(
                self._material_base(localized(stage["panel"], language()))
            )
        else:
            body.document().setBaseUrl(
                QUrl.fromLocalFile(str(self.current.lesson.root) + "/")
            )
        body.setMarkdown(self._task_markdown(stage))
        body.anchorClicked.connect(
            lambda url, key=identity, view=body: self.window.perform(
                lambda: self.follow_task_anchor(key, url, view)
            )
        )
        frame.addWidget(body)
        body.setVisible(identity == self.current.stage["id"])
        status = QLabel()
        status.setWordWrap(True)
        status.setStyleSheet(f"color: {colors()['muted']}; font-size: 11px;")
        frame.addWidget(status)
        status.setVisible(identity == self.current.stage["id"])
        self.cards[identity] = {
            "frame": card,
            "check": check,
            "number": number,
            "title": name,
            "body": body,
            "status": status,
        }
        self.task_layout.insertWidget(self.task_layout.count() - 1, card)
        body.fit_height()

    def refresh(self, *, reveal=False):
        project = self.current
        if project is None:
            return
        self.title.setText(localized(project.lesson.data["title"], language()))
        scroll = self.task_area.verticalScrollBar().value()
        for widgets in self.cards.values():
            card = widgets["frame"]
            self.task_layout.removeWidget(card)
            card.hide()
            card.deleteLater()
        self.cards.clear()
        if "panel_intro" in project.lesson.data:
            name = localized(project.lesson.data["panel_intro"], language())
            self.intro.document().setBaseUrl(self._material_base(name))
            self.intro.setMarkdown(project.lesson.material(name))
            self.intro.show()
            self.intro.fit_height()
        else:
            self.intro.hide()
        for index, stage in enumerate(project.lesson.stages):
            self._build_card(stage, index)
        self.status = self.cards[project.stage["id"]]["status"]
        self.actions["start"].setText(
            tr(
                {
                    "assembly": N_("Open assembly"),
                    "control": N_("Open controls"),
                    "program": N_("Open program"),
                }[project.stage.get("mode", "program")]
            )
        )
        self.update_check()
        self.update_card()
        if reveal:
            QTimer.singleShot(0, self, self.reveal_selected)
        else:
            QTimer.singleShot(
                0,
                self.task_area,
                lambda: self.task_area.verticalScrollBar().setValue(scroll),
            )

    def reveal_selected(self):
        if self.current and self.current.stage["id"] in self.cards:
            self.task_area.ensureWidgetVisible(
                self.cards[self.current.stage["id"]]["frame"], 0, 24
            )

    def update_card(self):
        project = self.current
        if project is None:
            return
        completed = len(project.progress["completed"])
        total = len(project.lesson.stages)
        earned, available = project.score
        position = project.lesson.stages.index(project.stage) + 1
        kind = project.lesson.data.get("kind", "lesson")
        progress_label = (
            N_("Project · {position}/{total} · {completed} done")
            if kind == "project"
            else N_("Lesson · {position}/{total} · {completed} done")
        )
        self.progress_button.setText(
            tr(
                progress_label,
                position=position,
                total=total,
                completed=completed,
            )
        )
        label = tr(
            "Task {position}/{total} · {completed} done · Points {earned}/{available}",
            position=position,
            completed=completed,
            total=total,
            earned=earned,
            available=available,
        )
        self.summary.setText(label)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(completed)
        self.progress_button.setToolTip(
            localized(project.lesson.data["title"], language()) + " · " + label
        )
        self.progress_button.setAccessibleName(tr("Open task panel") + " · " + label)

    def _dock_visibility_changed(self, visible):
        if self._updating_panel:
            return
        # Tabifying Scratch can obscure this dock without collapsing the lesson.
        # The progress chip remains a way back to the task list in that case.
        self._dock_active = visible
        QTimer.singleShot(0, self, self._sync_panel_toggle)

    def _sync_panel_toggle(self):
        if not isValid(self.dock):
            return
        visible = self.overlay.isVisible() if self._narrow else self._dock_active
        self.guidance.setChecked(bool(self.current and visible))
        show_chip = bool(
            self.current and not visible and self.window.pages.currentIndex() != 5
        )
        self.progress_action.setVisible(show_chip)
        self.progress_button.setVisible(show_chip)

    def set_panel_expanded(self, expanded):
        if self.current is None:
            return
        self.current.progress["panel_expanded"] = bool(expanded)
        self._transient_hidden = False
        self.update_panel_visibility()
        self.changed()

    def _move_panel(self, narrow):
        if narrow and self.panel.parent() is not self.overlay:
            self.panel.setParent(None)
            self.dock.setWidget(QWidget())
            self.overlay.layout().addWidget(self.panel)
        elif not narrow and self.panel.parent() is self.overlay:
            self.overlay.layout().removeWidget(self.panel)
            self.panel.setParent(None)
            self.dock.setWidget(self.panel)

    def _position_overlay(self):
        workspace = self.window.workspace
        width = min(380, max(280, workspace.width() - 52))
        self.overlay.setGeometry(
            workspace.width() - width - 4, 4, width, max(80, workspace.height() - 8)
        )
        self.overlay.raise_()

    def update_panel_visibility(self):
        expanded = bool(
            self.current and self.current.progress.get("panel_expanded", True)
        )
        narrow = self.window.width() < LESSON_DOCK_MIN_WIDTH
        self._updating_panel = True
        try:
            self.dock.hide()
            self.overlay.hide()
            self._move_panel(narrow)
            visible = (
                expanded
                and not self._transient_hidden
                and self.window.pages.currentIndex() != 5
            )
            if narrow:
                self._position_overlay()
                self.overlay.setVisible(visible)
            else:
                self.dock.setVisible(visible)
            if visible and not narrow:
                self.dock.raise_()
            self._dock_active = visible
        finally:
            self._updating_panel = False
        self._sync_panel_toggle()
        QTimer.singleShot(0, self, self._sync_panel_toggle)
        if expanded and not narrow and not self._transient_hidden:
            QTimer.singleShot(
                0,
                self.window,
                lambda: self.window.resizeDocks(
                    [self.dock], [370], Qt.Orientation.Horizontal
                ),
            )

    def eventFilter(self, watched, event):
        kind = event.type()
        if watched is self.window and kind == QEvent.Type.Resize:
            narrow = self.window.width() < LESSON_DOCK_MIN_WIDTH
            if narrow != self._narrow:
                self._narrow = narrow
                self._transient_hidden = narrow
                QTimer.singleShot(0, self, self.update_panel_visibility)
        if (
            watched is self.window.workspace
            and kind == QEvent.Type.Resize
            and self.overlay.isVisible()
        ):
            self._position_overlay()
        if kind not in (
            QEvent.Type.ShortcutOverride,
            QEvent.Type.KeyPress,
            QEvent.Type.MouseButtonPress,
        ):
            return False
        if self.current and isValid(self.dock) and self._dock_active:
            surface = self.overlay if self._narrow else self.dock
            if (
                kind in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress)
                and event.key() == Qt.Key.Key_Escape
                and isinstance(watched, QWidget)
                and (watched is surface or surface.isAncestorOf(watched))
            ):
                self._collapse_for_destination()
                event.accept()
                return True
            if (
                self._narrow
                and kind == QEvent.Type.MouseButtonPress
                and isinstance(watched, QWidget)
                and watched.window() is self.window
                and watched is not surface
                and not surface.isAncestorOf(watched)
            ):
                self._collapse_for_destination()
        return False

    def toggle_guidance(self):
        self.set_panel_expanded(self.guidance.isChecked())

    def navigate_stage(self, offset):
        if self.current:
            index = self.current.lesson.stages.index(self.current.stage) + offset
            if 0 <= index < len(self.current.lesson.stages):
                self.select_stage(index)

    def select_stage(self, index):
        if self.current is None or not 0 <= index < len(self.current.lesson.stages):
            return
        self.current.progress["stage"] = self.current.lesson.stages[index]["id"]
        self.refresh(reveal=True)
        self.changed()

    def open_task(self, index):
        self.select_stage(index)
        self.show_stage()

    def _collapse_for_destination(self):
        if self.window.width() < LESSON_DOCK_MIN_WIDTH:
            self._transient_hidden = True
            self.update_panel_visibility()

    def follow_task_anchor(self, identity, url, browser):
        if self.current is None:
            return
        base = browser.document().baseUrl()
        if identity is not None and self.current.stage["id"] != identity:
            index = next(
                i
                for i, task in enumerate(self.current.lesson.stages)
                if task["id"] == identity
            )
            self.select_stage(index)
        scheme = url.scheme()
        action = url.path().lstrip("/") if scheme == "task" else ""
        if scheme == "task":
            if action == "select":
                return
            if action == "instructions":
                self.show_stage()
            elif action == "program":
                self.open_task_program()
                self._collapse_for_destination()
            elif action == "assembly":
                self.open_assembly()
                self._collapse_for_destination()
            elif action == "control":
                self.window.set_mode(1)
                self._collapse_for_destination()
            elif action == "blocks":
                self.window.set_mode(0)
                self.window.view_filter.select("lesson")
                self._collapse_for_destination()
            elif action == "starter":
                self.open_starter()
                self._collapse_for_destination()
            elif action == "hint":
                self.hint()
            elif action.startswith("extra/"):
                index = int(action.partition("/")[2])
                links = self.current.stage.get("links", [])
                if not 0 <= index < len(links):
                    raise ValueError("Unknown task link")
                self.follow_task_link(links[index])
                if links[index]["kind"] != "markdown":
                    self._collapse_for_destination()
            return
        if scheme == "program":
            self.open_program(
                url.path()
                or self.current.stage.get("program")
                or self.current.main.name
            )
            self._collapse_for_destination()
        elif scheme == "assembly":
            self.open_assembly()
            self._collapse_for_destination()
        elif scheme == "control":
            self.window.set_mode(1)
            self._collapse_for_destination()
        elif scheme == "devices":
            self.window.device_dock.show()
            self.window.device_dock.raise_()
            self._collapse_for_destination()
        elif scheme == "connect":
            self._collapse_for_destination()
            self.window.connect_hub()
        elif scheme == "scratch":
            target = (
                url.path()
                or self.current.main.relative_to(
                    self.current.root / "programs"
                ).as_posix()
            )
            self.open_program(target)
            self.window.scratch_dock.show()
            self.window.scratch_dock.raise_()
            self._collapse_for_destination()
        elif scheme in ("http", "https"):
            QDesktopServices.openUrl(url)
        elif not url.path() and url.fragment():
            browser.scrollToAnchor(url.fragment())
        elif not scheme:
            resolved = base.resolved(url)
            if resolved.isLocalFile():
                path = Path(resolved.toLocalFile()).resolve()
                if path.is_relative_to(self.current.lesson.root):
                    name = path.relative_to(self.current.lesson.root).as_posix()
                    self.window.help_page.show_lesson_material(
                        self.current.lesson,
                        name + ("#" + url.fragment() if url.fragment() else ""),
                    )
                    self.window.set_mode(2)
                    self._collapse_for_destination()

    def start_stage(self):
        if self.current:
            mode = self.current.stage.get("mode", "program")
            if mode == "assembly":
                self.open_assembly()
                return
            if mode == "program" and "program" in self.current.stage:
                self.open_program(self.current.stage["program"])
            self.window.set_mode({"program": 0, "control": 1}[mode])

    def open_task_program(self):
        if self.current is None:
            return
        name = self.current.stage.get("program")
        if name:
            self.open_program(name)
        else:
            self.window.open_document(self.current.main)
            self.window.set_mode(0)

    def open_assembly(self):
        if self.current and self.assembly:
            self.assembly_host.select_lesson()
            steps = self.current.stage.get("assembly")
            if steps and not steps[0] - 1 <= self.assembly.step < steps[1]:
                self.assembly.set_step(steps[0] - 1)
            self.window.set_mode(4)

    def hint(self):
        if self.current:
            stage = self.current.stage
            hints = self.current.progress.setdefault("hints", {})
            hints[stage["id"]] = min(
                hints.get(stage["id"], 0) + 1, len(stage.get("hints", []))
            )
            self.refresh()
            self.changed()
            self.set_panel_expanded(True)

    def open_starter(self):
        if self.current is None:
            return
        name = self.current.stage.get("starter")
        if name is None:
            self.status.setText(tr("This stage has no starter program."))
            return
        project = self.current
        identity = project.stage["id"]
        saved = project.progress.setdefault("starter_files", {})
        if identity in saved:
            destination = resource(project.root / "programs", saved[identity])
            if not destination.is_file():
                raise ValueError("The task starter program is missing")
        else:
            index = project.lesson.stages.index(project.stage) + 1
            stem = f"task_{index}_starter"
            destination = project.root / "programs" / f"{stem}.py"
            number = 2
            while destination.exists():
                destination = project.root / "programs" / f"{stem}_{number}.py"
                number += 1
            source = project.lesson.file(name).read_text(encoding="utf-8")
            atomic_write(destination, source)
            saved[identity] = destination.name
            project.pending = True
        self.window.open_document(destination)
        self.window.set_mode(0)
        self.changed()

    def connections(self, stage=None):
        if self.current is None or "robot" not in self.current.lesson.data:
            return []
        robot = read_json(
            resource(self.current.lesson.root, self.current.lesson.data["robot"])
        )
        required = (stage or self.current.stage).get("devices")
        return [
            d
            for d in robot.get("devices", [])
            if required is None or d["instance"] in required
        ]

    def check_ready(self, stage=None):
        info = self.window.hub_info
        return (
            info.connected
            and info.monitoring
            and all(
                info.ports.get(d["port"], {}).get("type") == d["type"]
                for d in self.connections(stage)
            )
        )

    def update_check(self):
        if self.current is None:
            return
        project = self.current
        done = project.stage["id"] in project.progress["completed"]
        ready = project.stage.get("check") != "devices" or self.check_ready()
        self.actions["complete"].setText(
            tr("Mark incomplete") if done else tr("Mark complete")
        )
        self.actions["complete"].setEnabled(done or ready)
        index = project.lesson.stages.index(project.stage)
        self.actions["previous"].setEnabled(index > 0)
        self.actions["next"].setEnabled(index + 1 < len(project.lesson.stages))
        available = {
            snippet.identity
            for snippet in self.window.document_page.session.available_snippets
        }
        for stage in project.lesson.stages:
            identity = stage["id"]
            widgets = self.cards[identity]
            checked = identity in project.progress["completed"]
            can_check = stage.get("check") != "devices" or self.check_ready(stage)
            checkbox = widgets["check"]
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)
            checkbox.setEnabled(checked or can_check)
            widgets["frame"].setProperty("selected", identity == project.stage["id"])
            widgets["frame"].setProperty("completed", checked)
            widgets["frame"].style().unpolish(widgets["frame"])
            widgets["frame"].style().polish(widgets["frame"])
            number = widgets["number"]
            number.setProperty("completed", checked)
            number.style().unpolish(number)
            number.style().polish(number)
            if checked:
                text = (
                    tr("Connection was verified when this task was completed.")
                    if project.progress.get("evidence", {}).get(identity) == "devices"
                    else tr("Marked complete by learner. You can keep experimenting.")
                )
            elif stage.get("check") == "devices":
                info = self.window.hub_info
                if not info.connected:
                    text = tr("Connect a hub at the top right of the window.")
                elif not info.monitoring:
                    text = tr(
                        "Open the port monitor to check the expected connections."
                    )
                elif can_check:
                    text = tr("Connections match the lesson.")
                else:
                    from .device import KINDS

                    text = tr(
                        "Check connections: {devices}",
                        devices=", ".join(
                            f"{d['port']} · {tr(KINDS.get(d['type'], 'Device'))}"
                            for d in self.connections(stage)
                            if info.ports.get(d["port"], {}).get("type") != d["type"]
                        ),
                    )
            elif identity == project.stage["id"]:
                text = tr("Complete the task, then mark it complete.")
            else:
                text = ""
            missing = set(stage.get("blocks", ())) - available
            if missing:
                text += "\n" + tr(
                    "Suggested blocks unavailable: {blocks}. Use the full catalog or Python editor.",
                    blocks=", ".join(sorted(missing)),
                )
            widgets["status"].setText(text.strip())
            checkbox.setToolTip(text.strip() or localized(stage["title"], language()))
        self.status = self.cards[project.stage["id"]]["status"]
        self.actions["complete"].setToolTip(self.status.text())

    def complete(self):
        if self.current is None:
            return
        identity = self.current.stage["id"]
        done = identity in self.current.progress["completed"]
        self.set_completion(identity, not done)

    def set_completion(self, identity, checked):
        if self.current is None:
            return
        stage = next(s for s in self.current.lesson.stages if s["id"] == identity)
        if checked and stage.get("check") == "devices" and not self.check_ready(stage):
            self.refresh()
            return
        completed = self.current.progress["completed"]
        if checked and identity not in completed:
            completed.append(identity)
            self.current.progress.setdefault("evidence", {})[identity] = (
                "devices" if stage.get("check") == "devices" else "manual"
            )
        elif not checked and identity in completed:
            completed.remove(identity)
            self.current.progress.setdefault("evidence", {}).pop(identity, None)
        self.refresh()
        self.changed()

    def palette(self):
        window = self.window
        project = self.current
        level = window.block_level
        window.level_filter.setEnabled(True)
        stage_ids = frozenset(project.stage.get("blocks", [])) if project else None
        if window.library.stage_ids != stage_ids or window.library.level != level:
            window.library.stage_ids = stage_ids
            window.library.filter(window.search.text(), level)
        view = window.editing_source
        view.expression_level = level
        view.expression_ids = None
        view.expression_operations = None

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
        self.window.set_mode(4)
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
            project = self.projects.pop(root)
            if not project.retain:
                project.discard_working_copy()

    def autosave(self):
        first_error = None
        for project in tuple(self.projects.values()):
            if project.retain:
                try:
                    self.store_documents(project)
                    project.checkpoint()
                except (OSError, ValueError) as error:
                    if first_error is None:
                        first_error = error
        if first_error is not None:
            raise first_error

    def archive_destination(self, name, title):
        selected = Path(name).resolve()
        destination = selected.with_suffix(".ltr")
        overwrite = destination.exists()
        if overwrite and destination != selected:
            answer = QMessageBox.question(
                self.window,
                title,
                tr("The file already exists. Replace it?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None
        return destination, overwrite

    def save(self, project, *, choose=False):
        path = project.path
        overwrite = False
        if choose or path is None:
            name, _ = QFileDialog.getSaveFileName(
                self.window,
                tr("Save lesson project"),
                str(path or Path.home() / "lesson.ltr"),
                "LittleTinker Rig (*.ltr)",
            )
            if not name:
                return False
            selected = self.archive_destination(name, tr("Save lesson project"))
            if selected is None:
                return False
            path, overwrite = selected
        if any(
            other is not project and other.path == path.resolve()
            for other in self.projects.values()
        ):
            raise ValueError(tr("This project is already open. Choose another file."))
        self.store_documents(project)
        project.save(path, overwrite=overwrite)
        self.window.remember_file(path)
        self.window.recovery.flush()
        return True

    def store_documents(self, project):
        workspace = {"documents": {}, "active": "main.py"}
        first_error = None
        for index in range(self.window.documents.count()):
            page = self.window.documents.widget(index)
            if getattr(page, "lesson_project", None) is project:
                project.pending |= page.dirty
                try:
                    page.save()
                except (OSError, ValueError) as error:
                    if first_error is None:
                        first_error = error
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
        if first_error is not None:
            raise first_error

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
        selected = self.archive_destination(
            name, tr("Export lesson project with resources")
        )
        if selected is None:
            return
        destination, overwrite = selected
        if any(
            p.path == destination or destination.is_relative_to(p.root)
            for p in self.projects.values()
        ):
            raise ValueError(tr("Export to a separate project file"))
        self.store_documents(project)
        project.checkpoint()
        snapshot = project.portable_snapshot()
        self.window.recovery.flush()
        self.export_job = ResourceJob(
            lambda **kwargs: project.export(
                destination, snapshot=snapshot, overwrite=overwrite, **kwargs
            )
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
