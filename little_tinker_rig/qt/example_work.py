"""Continue, autosave and relocate learner-owned example attempts."""

from datetime import datetime
from pathlib import Path
from time import time_ns

from PySide6.QtWidgets import QApplication

from little_tinker_rig.core.example_work import ExampleWork
from little_tinker_rig.core.project import Project
from little_tinker_rig.i18n import tr
from little_tinker_rig.pybricks.program import Program


class ExampleWorkspaces:
    def __init__(self, window):
        self.window = window
        self.works = {}

    def pages(self):
        return [
            self.window.documents.widget(i)
            for i in range(self.window.documents.count())
        ]

    def owner(self, path):
        for work in self.works.values():
            if work.owns(path):
                return work
        for work in ExampleWork.all():
            if work.owns(path):
                self.works[work.identity] = work
                return work
        return None

    def open(self, source=None, *, new=False, work=None):
        window = self.window
        from .app import examples_directory

        if work is None:
            identity = source.resolve().relative_to(examples_directory()).as_posix()
            work = (
                next(
                    (
                        w
                        for w in ExampleWork.all()
                        if w.data["example"] == identity and w.entry.is_file()
                    ),
                    None,
                )
                if not new
                else None
            )
            work = work or ExampleWork.create(source, examples_directory())
        # Reuse the live owner, including its unfinished text and history.
        for other in QApplication.topLevelWidgets():
            manager = getattr(other, "example_workspaces", None)
            if (
                manager
                and not getattr(getattr(other, "recovery", None), "closed", False)
                and work.identity in manager.works
            ):
                owner = manager.works[work.identity]
                if any(p.example_work is owner for p in manager.pages()):
                    work = owner
                    window = other
                    break
        if not work.entry.is_file():
            raise FileNotFoundError(work.entry)
        manager = window.example_workspaces
        manager.works[work.identity] = work
        work.data["opened"] = time_ns()
        work.save()
        page = window.open_document(work.entry)
        if hasattr(window, "pages"):
            window.set_mode(0)
            window.show()
            window.raise_()
            window.activateWindow()
        return page

    def autosave(self):
        changed = False
        for page in self.pages():
            if work := page.example_work:
                project = page.session.project
                if page.dirty or project.example_attempt != work.identity:
                    project.example_attempt = work.identity
                    project.save()
                    page.sync_text()
                    changed = True
                work.remember(project.path)
                work.save()
        if changed:
            self.window.refresh_status()

    def menu(self, menu, examples):
        current = self.window.document_page.example_work
        menu.addSeparator()
        restart = menu.addAction(tr("Start this example again"))
        restart.setEnabled(current is not None and current.source(examples).is_file())
        restart.triggered.connect(
            lambda: self.window.perform(
                lambda: self.open(current.source(examples), new=True)
            )
        )
        attempts = menu.addMenu(tr("My attempts"))
        groups = {}
        works = ExampleWork.all()
        numbers = {}
        counts = {}
        for work in sorted(
            works, key=lambda w: w.data.get("created", w.data["opened"])
        ):
            identity = work.data["example"]
            counts[identity] = counts.get(identity, 0) + 1
            numbers[work.identity] = counts[identity]
        for work in works:
            identity = work.data["example"]
            if identity not in groups:
                groups[identity] = attempts.addMenu(identity.replace("&", "&&"))
            date = datetime.fromtimestamp(work.data["opened"] / 1e9).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            action = groups[identity].addAction(
                tr(
                    "Attempt {number} · {name} · {date}",
                    number=numbers[work.identity],
                    name=work.entry.stem,
                    date=date,
                ).replace("&", "&&")
            )
            action.setToolTip(str(work.entry))
            action.setData(str(work.root))
            action.setEnabled(work.entry.is_file())
            action.triggered.connect(
                lambda checked=False, work=work: self.window.perform(
                    lambda: self.open(work=work)
                )
            )
        attempts.setEnabled(bool(groups))

    def relocation(self, page, destination):
        """Prepare all destinations before writing any imported module."""
        work = page.example_work
        old = page.session.project.path
        if work and old == work.entry:
            for other in self.pages():
                if other.example_work is work:
                    work.remember(other.session.project.path)
            try:
                program = Program(
                    old, {p.session.project.path: p.text for p in self.pages()}
                )
            except (SyntaxError, ValueError):
                # Invalid drafts still export the attempt's known modules.
                pass
            else:
                for source in program.sources:
                    work.remember(source)
                program.cleanup()
        paths = {old: destination}
        if work and destination != old and str(destination) in work.data["files"]:
            raise ValueError(tr("Choose a name different from the example's modules."))
        if work and old == work.entry and old.parent != destination.parent:
            paths.update(
                (Path(p), destination.parent / Path(p).relative_to(old.parent))
                for p in work.data["files"]
                if Path(p) != old and Path(p).is_relative_to(old.parent)
            )
        opened = {p.session.project.path: p for p in self.pages()}
        if len(set(paths.values())) != len(paths):
            raise ValueError(tr("Choose a name different from the example's modules."))
        projects = {}
        for source, target in paths.items():
            if source == old:
                continue
            if target in opened:
                raise ValueError(tr("This file is already open in another tab"))
            original = (
                opened[source].session.project
                if source in opened
                else Project(source, allow_draft=True)
            )
            copied = Project(target, allow_draft=True)
            if target.exists() and (
                copied.state != original.state
                or copied.collections != original.collections
                or copied.pins != original.pins
                or copied.example_attempt not in (None, work.identity)
            ):
                raise ValueError(
                    tr("A different module already exists: {path}", path=str(target))
                )
            copied.document = original.document
            copied.collections = original.collections
            copied.pins = original.pins
            copied.example_attempt = work.identity
            projects[source] = copied
        return paths, projects

    def relocate(self, page, paths, projects):
        for project in projects.values():
            project.path.parent.mkdir(parents=True, exist_ok=True)
            project.save()
        page.example_work.relocated(paths)
        for source, project in projects.items():
            for other in self.pages():
                if other.session.project.path == source:
                    other.session.project = project
                    other.code.path = project.path
