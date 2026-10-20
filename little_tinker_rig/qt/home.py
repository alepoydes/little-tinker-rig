"""A compact start workspace for continuing work and choosing a first activity."""

import json
from pathlib import Path
from time import time_ns
from zipfile import BadZipFile, ZipFile

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.core.example_work import ExampleWork
from little_tinker_rig.core.lessons import StudentProject, lessons_directory, localized
from little_tinker_rig.examples import examples_directory
from little_tinker_rig.i18n import language, tr

from .theme import colors, svg_pixmap


class HomeCard(QFrame):
    activated = Signal()

    def __init__(self):
        super().__init__()
        self._pressed = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._pressed and self.rect().contains(event.position().toPoint()):
                self.activated.emit()
            self._pressed = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class HomePage(QScrollArea):
    """Only explicit actions open examples or create learner attempts."""

    @staticmethod
    def _recent_folders(paths):
        names = {}
        for path in paths:
            names.setdefault(path.name.casefold(), []).append(path)
        labels = {}
        for group in names.values():
            if len(group) < 2:
                continue
            parents = [path.parent.parts for path in group]
            for depth in range(1, max(map(len, parents)) + 1):
                suffixes = [parts[-depth:] for parts in parents]
                if len(set(suffixes)) == len(group):
                    break
            labels.update(
                (path, str(Path(*suffix)))
                for path, suffix in zip(group, suffixes, strict=True)
            )
        return labels

    @staticmethod
    def _archive_attempt_id(path):
        if path.suffix != ".ltr":
            return None
        try:
            with ZipFile(path) as archive:
                info = archive.getinfo("project.json")
                if info.file_size > 65536:
                    return None
                data = json.loads(archive.read(info))
                return data.get("id") if isinstance(data, dict) else None
        except (BadZipFile, KeyError, OSError, RuntimeError, ValueError):
            return None

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setObjectName("homePage")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = self.body = QWidget()
        body.setObjectName("homeBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 26, 28, 28)
        layout.setSpacing(18)
        self.heading = QLabel()
        self.heading.setObjectName("homeHeading")
        layout.addWidget(self.heading)
        self.intro = QLabel()
        self.intro.setObjectName("homeIntro")
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)
        actions = QHBoxLayout()
        actions.setSpacing(9)
        self.new_button = self._button(actions, window.new_file, primary=True)
        self.open_button = self._button(actions, window.open_file)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.recent_title = QLabel()
        self.recent_title.setObjectName("homeSection")
        layout.addWidget(self.recent_title)
        self.recent_host = QWidget()
        self.recent_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.recent_layout = QVBoxLayout(self.recent_host)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setSpacing(7)
        layout.addWidget(self.recent_host)
        self.projects_title = QLabel()
        self.projects_title.setObjectName("homeSection")
        layout.addWidget(self.projects_title)
        self.projects_intro = QLabel()
        self.projects_intro.setObjectName("homeIntro")
        self.projects_intro.setWordWrap(True)
        layout.addWidget(self.projects_intro)
        self.kit = QComboBox()
        self.kit.setObjectName("homeKit")
        self.kit.setMinimumWidth(220)
        self.kit.setMaximumWidth(310)
        self.kit.currentIndexChanged.connect(self._kit_changed)
        layout.addWidget(self.kit, alignment=Qt.AlignmentFlag.AlignLeft)
        self.project_host = QWidget()
        self.project_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.project_layout = QGridLayout(self.project_host)
        self.project_layout.setContentsMargins(0, 0, 0, 0)
        self.project_layout.setSpacing(12)
        layout.addWidget(self.project_host)
        more = QHBoxLayout()
        more.setSpacing(9)
        self.all_lessons = self._button(
            more, lambda: self._open_menu(window.lessons.menu, self.all_lessons)
        )
        self.all_examples = self._button(
            more, lambda: self._open_menu(window.examples_menu, self.all_examples)
        )
        more.addStretch(1)
        layout.addLayout(more)
        layout.addStretch(1)
        self._project_columns = 0
        self.setWidget(body)
        self.retranslate()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = 1 if self.viewport().width() < 1100 else 2
        if self._project_columns != columns:
            self.refresh_projects()

    def _button(self, layout, callback, *, primary=False):
        button = QPushButton()
        button.setObjectName("homePrimary" if primary else "homeButton")
        button.setMinimumHeight(38)
        button.clicked.connect(lambda: self.window.perform(callback))
        layout.addWidget(button)
        return button

    def _open_menu(self, menu, button):
        menu.popup(button.mapToGlobal(button.rect().bottomLeft()))

    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def _card(
        self, title, description, action, callback, *, icon=None, detail=None, tip=None
    ):
        card = HomeCard()
        card.setObjectName("homeCard")
        card.activated.connect(lambda: self.window.perform(callback))
        if tip:
            card.setToolTip(tip)
        card.setMinimumHeight(120 if icon else 72)
        box = QHBoxLayout(card)
        box.setContentsMargins(17, 14, 17, 14)
        box.setSpacing(14)
        if icon:
            picture = QLabel()
            picture.setObjectName("homePicture")
            picture.setPixmap(svg_pixmap(icon, QSize(54, 54)))
            picture.setFixedSize(68, 68)
            picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(picture)
        words = QVBoxLayout()
        words.setSpacing(4)
        name = QLabel(title)
        name.setObjectName("homeCardTitle")
        name.setWordWrap(True)
        words.addWidget(name)
        if description:
            summary = QLabel(description)
            summary.setObjectName("homeCardDescription")
            summary.setWordWrap(True)
            words.addWidget(summary)
        if detail:
            meta = QLabel(detail)
            meta.setObjectName("homeCardDetail")
            meta.setWordWrap(True)
            words.addWidget(meta)
        box.addLayout(words, 1)
        button = QPushButton(action)
        button.setObjectName("homeCardAction")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAccessibleName(f"{action}: {title}")
        if tip:
            button.setToolTip(tip)
        button.clicked.connect(lambda: self.window.perform(callback))
        box.addWidget(button, alignment=Qt.AlignmentFlag.AlignVCenter)
        return card

    def _kit_changed(self):
        value = self.kit.currentData()
        if value is not None:
            self.window.settings.setValue("homeKit", value)
            self.refresh_projects()

    def retranslate(self):
        self.heading.setText(tr("Make something today"))
        self.intro.setText(
            tr("Continue your work or pick a small project. Your programs stay yours.")
        )
        self.new_button.setText(tr("New program"))
        self.open_button.setText(tr("Open a file…"))
        self.recent_title.setText(tr("Continue working"))
        self.projects_title.setText(tr("Choose a project"))
        self.projects_intro.setText(
            tr(
                "Start with Python, then try a robot. Open a card to create or resume your own copy."
            )
        )
        self.all_lessons.setText(tr("All lessons…"))
        self.all_examples.setText(tr("All examples…"))
        selected = self.kit.currentData() or self.window.settings.value(
            "homeKit", "all"
        )
        self.kit.blockSignals(True)
        self.kit.clear()
        for key, label in (
            ("all", tr("All equipment")),
            ("none", tr("No robot needed")),
            ("spike", tr("SPIKE Prime 45678")),
            ("inventor", tr("Robot Inventor 51515")),
        ):
            self.kit.addItem(label, key)
        self.kit.setCurrentIndex(max(0, self.kit.findData(selected)))
        self.kit.setAccessibleName(tr("Filter projects by equipment"))
        self.kit.blockSignals(False)
        self.refresh()

    def refresh(self):
        self._clear(self.recent_layout)
        entries = []
        works = ExampleWork.all()
        attempts = [
            self.window.lessons.projects.get(attempt.root, attempt)
            for attempt in StudentProject.attempts()
        ]
        attempt_ids = {
            attempt.data["id"]
            for attempt in attempts
            if isinstance(attempt.data.get("id"), str)
        }
        groups = {}
        for attempt in attempts:
            groups.setdefault(attempt.data.get("origin"), []).append(attempt)
        numbers = {}
        for group in groups.values():
            group.sort(
                key=lambda attempt: (
                    1 if type(attempt.data.get("created")) is int else 0,
                    (
                        attempt.data["created"]
                        if type(attempt.data.get("created")) is int
                        else 0
                    ),
                    str(attempt.root),
                )
            )
            for number, attempt in enumerate(group, 1):
                numbers[attempt.root] = number
        activity = self.window.settings.value("recentActivity", {})
        activity = activity if isinstance(activity, dict) else {}
        recent = self.window.settings.value("recentFiles", [])
        recent = [recent] if isinstance(recent, str) else recent or []
        ordinary_files = []
        for value in recent:
            if not isinstance(value, str):
                continue
            path = Path(value)
            if not path.is_file():
                continue
            resolved = path.resolve()
            if (
                any(work.owns(resolved) for work in works)
                or any(resolved.is_relative_to(attempt.root) for attempt in attempts)
                or any(attempt.path == resolved for attempt in attempts)
                or self._archive_attempt_id(resolved) in attempt_ids
            ):
                continue
            try:
                opened = int(activity.get(str(path)) or path.stat().st_mtime_ns)
            except (OSError, TypeError, ValueError):
                continue
            ordinary_files.append((opened, path))
        folders = self._recent_folders([path for _, path in ordinary_files])
        for opened, path in ordinary_files:
            detail = (
                tr("Lesson project")
                if path.suffix in (".ltr", ".pyblocks")
                else tr("Python program")
            )
            if folder := folders.get(path):
                detail += f" · {folder}"
            entries.append(
                (
                    opened,
                    path.name,
                    detail,
                    lambda path=path: self.window.open_recent(path),
                    str(path),
                )
            )
        for work in works:
            if work.entry.is_file():
                try:
                    source = work.source(examples_directory())
                except (OSError, ValueError):
                    continue
                title = source.stem.replace("_", " ")
                entries.append(
                    (
                        work.data["opened"],
                        title,
                        tr("Example attempt"),
                        lambda work=work: self.window.example_workspaces.open(
                            work=work
                        ),
                        None,
                    )
                )
        for attempt in attempts:
            title = localized(attempt.lesson.data["title"], language())
            earned, total = attempt.score
            group = groups[attempt.data.get("origin")]
            detail = (
                tr(
                    "Lesson · attempt {number} · {earned}/{total} points",
                    number=numbers[attempt.root],
                    earned=earned,
                    total=total,
                )
                if len(group) > 1
                else tr("Lesson · {earned}/{total} points", earned=earned, total=total)
            )
            entries.append(
                (
                    attempt.data["opened"],
                    title,
                    detail,
                    lambda attempt=attempt: self.window.lessons.open(
                        Path(attempt.data["origin"]), attempt=attempt
                    ),
                    None,
                )
            )
        current = self.window.document_page
        if (
            current.unnamed
            and current.lesson_project is None
            and current.example_work is None
            and not self.window._unused_startup_placeholder()
        ):
            entries.append(
                (
                    time_ns(),
                    tr("Untitled program"),
                    tr("Open in this window"),
                    lambda: self.window.set_mode(0),
                    None,
                )
            )
        entries.sort(key=lambda entry: entry[0], reverse=True)
        self.recent_title.setVisible(bool(entries))
        self.recent_host.setVisible(bool(entries))
        for _, title, detail, callback, tip in entries[:3]:
            self.recent_layout.addWidget(
                self._card(title, detail, tr("Continue"), callback, tip=tip)
            )
        self.recent_host.setMinimumHeight(
            72 * min(3, len(entries)) + 7 * max(0, min(3, len(entries)) - 1)
        )
        self.refresh_projects()
        self.apply_theme()

    def refresh_projects(self):
        self._clear(self.project_layout)
        columns = self._project_columns = 1 if self.viewport().width() < 1100 else 2
        selection = self.kit.currentData()
        projects = [
            (
                "none",
                tr("First Python program"),
                tr("Change a message, repeat it, and see the result in Console."),
                tr("No robot needed · about 10 minutes"),
                "home-code",
                lessons_directory() / "first_python",
            ),
            (
                "spike",
                tr("First robot drive"),
                tr("Build a rolling base and make it travel a measured distance."),
                tr("SPIKE Prime 45678 · motors A and B"),
                "home-drive",
                lessons_directory() / "first_drive",
            ),
            (
                "inventor",
                tr("Exploration Rover"),
                tr("Explore a ready-made rover program and change its behaviour."),
                tr("Robot Inventor 51515 · Exploration Rover model"),
                "home-rover",
                lessons_directory() / "pybricks" / "inventor_51515_exploration_rover",
            ),
        ]
        visible = [item for item in projects if selection in (None, "all", item[0])]
        for index, (_, title, description, detail, icon, path) in enumerate(visible):
            attempt = StudentProject.latest(path)
            card = self._card(
                title,
                description,
                tr("Continue") if attempt else tr("Start project"),
                lambda path=path: self.window.lessons.open(path),
                icon=icon,
                detail=detail,
            )
            self.project_layout.addWidget(card, index // columns, index % columns)
        rows = (len(visible) + columns - 1) // columns
        self.project_host.setMinimumHeight(rows * 120 + max(0, rows - 1) * 12)
        self.project_layout.setColumnStretch(0, 1)
        self.project_layout.setColumnStretch(1, 1 if columns == 2 else 0)

    def apply_theme(self):
        c = colors()
        self.setStyleSheet(
            f"#homePage, #homeBody {{ background: {c['window']}; color: {c['text']}; }}"
            f"#homeHeading {{ color: {c['text']}; font-size: 26px; font-weight: 800; }}"
            f"#homeSection {{ color: {c['text']}; font-size: 18px; font-weight: 750; }}"
            f"#homeIntro, #homeCardDescription, #homeCardDetail {{ color: {c['muted']}; }}"
            f"#homeCard {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 13px; }}"
            f"#homeCard:hover {{ border-color: {c['accent']}; }}"
            f"#homeCardTitle {{ color: {c['text']}; font-size: 15px; font-weight: 700; }}"
            f"#homePicture {{ background: {c['selected']}; border-radius: 12px; }}"
            f"#homePrimary {{ background: {c['accent']}; color: {c['accent_text']}; border: 0; border-radius: 9px; padding: 7px 16px; font-weight: 700; }}"
            f"#homeButton, #homeCardAction {{ background: {c['raised']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 7px 12px; }}"
            f"#homeButton:hover, #homeCardAction:hover {{ background: {c['hover']}; }}"
            f"#homeKit {{ background: {c['panel']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 6px 9px; }}"
        )
