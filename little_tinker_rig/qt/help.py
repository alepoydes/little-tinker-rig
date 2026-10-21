"""Offline Markdown documentation and snippet help in one navigable workspace."""

import ast
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QImage,
    QKeySequence,
    QPainter,
    QShortcut,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QTextFrameFormat,
    QTextImageFormat,
    QTextTable,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.core.lessons import localized, resource
from little_tinker_rig.core.snippets import snippet_groups
from little_tinker_rig.documentation import DEVELOPER_PAGES, heading_anchors
from little_tinker_rig.i18n import DEFAULT_LANGUAGE, LANGUAGES, N_, language, tr

from .library import LEVEL_TITLES, group_title, snippet_title
from .markdown import fit_images
from .theme import colors, recolor_document_links

GUIDE_ORDER = (
    "index.md",
    "tutorial/first.md",
    "INSTALL.md",
    "learning.md",
    "lessons.md",
    "usage.md",
    "robotics.md",
    "usb.md",
    "examples.md",
    "snippets.md",
    "block-editor.md",
    "tui.md",
)


def group_document(identity, snippets):
    def title(snippet):
        label = snippet_title(snippet)
        if snippet.family:
            label += " · " + (
                tr(snippet.variant)
                if snippet.variant
                else snippet.identity.rsplit("/", 1)[1]
            )
        return label

    parts = [
        f"# {group_title(identity, snippets)}",
        "\n".join(tr(snippets[0].group_help).splitlines()[1:]) if snippets else "",
        "\n".join(
            f"- [{title(snippet)}](#{snippet.identity.rsplit('/', 1)[1]})"
            for snippet in snippets
        ),
    ]
    for snippet in snippets:
        name = snippet.identity.rsplit("/", 1)[1]
        help = tr(snippet.help).splitlines()
        parts.append(
            f'<a name="{name}"></a>\n\n## {title(snippet)}\n\n'
            + tr(LEVEL_TITLES[snippet.level])
            + "\n\n"
            + "\n".join(help if snippet.title else help[1:])
        )
        if snippet.parameters:
            parameters = "\n".join(
                f"| `{p.name}` | {p.annotation or 'Python'} | `{p.default or '—'}` |"
                for p in snippet.parameters
            )
            parts.append(
                f"### {tr('Parameters')}\n\n| {tr('Name')} | {tr('Unit / type')} | {tr('Default')} |\n|---|---|---|\n{parameters}"
            )
        if snippet.result_type and snippet.result_type not in {"statement", "loop"}:
            parts.append(f"**{tr('Result')}:** `{snippet.result_type}`")
        if snippet.names:
            parts.append(
                f"**{tr('Editable names')}:** "
                + ", ".join(f"`{name}`" for name in snippet.names)
            )
        source = snippet.definition or (
            ast.unparse(snippet.body)
            if snippet.expression
            else "\n".join(ast.unparse(node) for node in snippet.body)
        )
        parts.append(f"### Python\n\n```python\n{source}\n```")
        parts.append(
            f"[{tr('Open definition')}](little-tinker-rig-definition:{snippet.identity})"
        )
    return "\n\n".join(parts) + "\n"


class HelpBrowser(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.lesson_numbers = {}
        self._compact_document = self.width() < 440

    def lesson_number_image(self, number):
        c = colors()
        image = QImage(26, 26, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(c["accent"]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(1, 1, 24, 24))
        font = QFont("sans-serif", 10)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(c["accent_text"]))
        painter.drawText(
            QRectF(1, 1, 24, 24), Qt.AlignmentFlag.AlignCenter, str(number)
        )
        painter.end()
        return image

    def lesson_number_badge(self, number, href=None):
        document = self.document()
        url = QUrl(f"lesson-number:{number}")
        document.addResource(
            document.ResourceType.ImageResource,
            url,
            self.lesson_number_image(number),
        )
        badge = QTextImageFormat()
        badge.setName(url.toString())
        badge.setWidth(26)
        badge.setHeight(26)
        badge.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignMiddle)
        badge.setToolTip(str(number))
        if href:
            badge.setAnchor(True)
            badge.setAnchorHref(href)
        return badge

    def decorate_lesson_index(self, numbers):
        document = self.document()
        seen = set()
        block = document.begin()
        while block.isValid() and len(seen) < len(numbers):
            following = block.next()
            if block.blockFormat().headingLevel() == 2:
                break
            fragment = block.begin()
            while not fragment.atEnd():
                href = fragment.fragment().charFormat().anchorHref()
                anchor = href.removeprefix("#")
                if href.startswith("#") and anchor in numbers and anchor not in seen:
                    cursor = QTextCursor(block)
                    cursor.setPosition(block.position())
                    cursor.insertImage(self.lesson_number_badge(numbers[anchor], href))
                    cursor.insertText("  ")
                    seen.add(anchor)
                    break
                fragment += 1
            block = following

    def decorate_lesson_headings(self, numbers):
        document = self.document()
        block = document.begin()
        while block.isValid():
            following = block.next()
            if block.blockFormat().headingLevel() == 2:
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                title_format = cursor.charFormat()
                number = next(
                    (
                        numbers[name]
                        for name in title_format.anchorNames()
                        if name in numbers
                    ),
                    None,
                )
                if number is not None:
                    cursor.clearSelection()
                    cursor.setPosition(block.position())
                    cursor.insertImage(self.lesson_number_badge(number))
                    cursor.insertText("  ", title_format)
            block = following

    def refresh_lesson_numbers(self):
        document = self.document()
        for number in self.lesson_numbers.values():
            document.addResource(
                document.ResourceType.ImageResource,
                QUrl(f"lesson-number:{number}"),
                self.lesson_number_image(number),
            )
        self.viewport().update()

    def resizeEvent(self, event):
        # Keep a readable text column while letting the page occupy its pane.
        inset = max(0, (self.width() - 1120) // 2)
        if self.viewportMargins().left() != inset:
            self.setViewportMargins(inset, 0, inset, 0)
        super().resizeEvent(event)
        compact = self.width() < 440
        if compact != self._compact_document:
            scroll = self.verticalScrollBar().value()
            self._compact_document = compact
            self.style_document()
            self.verticalScrollBar().setValue(scroll)
        else:
            self.fit_images()

    def style_document(self):
        c = colors()
        document = self.document()
        document.setDefaultFont(QFont("sans-serif", 12))
        document.setDocumentMargin(14 if self._compact_document else 32)
        block = document.begin()
        while block.isValid():
            cursor = QTextCursor(block)
            format = block.blockFormat()
            heading = format.headingLevel()
            code = format.nonBreakableLines()
            format.setLineHeight(
                145 if code else 155,
                QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
            )
            format.setTopMargin(
                (12 if self._compact_document else 24) if heading else 0
            )
            bottom_margin = 0 if code else 12
            if heading and self._compact_document:
                bottom_margin = 8
            format.setBottomMargin(bottom_margin)
            if code:
                format.setBackground(QColor(c["raised"]))
                format.setLeftMargin(14)
                format.setRightMargin(14)
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                text_format = cursor.charFormat()
                text_format.setFont(
                    QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
                )
                text_format.setFontPointSize(10.5)
                text_format.setForeground(QColor(c["text"]))
                cursor.mergeCharFormat(text_format)
            elif heading:
                if heading == 1:
                    heading_size = 19 if self._compact_document else 25
                elif heading == 2:
                    heading_size = 16 if self._compact_document else 18
                else:
                    heading_size = 14
                start = block.position() + (
                    1 if block.text().startswith("\ufffc") else 0
                )
                end = block.position() + len(block.text())
                fragments = []
                item = block.begin()
                while not item.atEnd():
                    fragment = item.fragment()
                    first = max(start, fragment.position())
                    last = min(end, fragment.position() + fragment.length())
                    if first < last:
                        text_format = fragment.charFormat()
                        text_format.clearProperty(
                            QTextFormat.Property.FontSizeAdjustment
                        )
                        text_format.setFontPointSize(heading_size)
                        text_format.setForeground(QColor(c["text"]))
                        text_format.setFontWeight(QFont.Weight.DemiBold)
                        fragments.append((first, last, text_format))
                    item += 1
                for first, last, text_format in fragments:
                    cursor.setPosition(first)
                    cursor.setPosition(last, QTextCursor.MoveMode.KeepAnchor)
                    cursor.setCharFormat(text_format)
            cursor.clearSelection()
            cursor.setPosition(block.position())
            cursor.setBlockFormat(format)
            block = block.next()
        for frame in document.rootFrame().childFrames():
            if isinstance(frame, QTextTable):
                format = frame.format()
                format.setCellPadding(9)
                format.setCellSpacing(0)
                format.setBorder(1)
                format.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
                format.setBorderBrush(QColor(c["border"]))
                frame.setFormat(format)
                for column in range(frame.columns()):
                    cell = frame.cellAt(0, column)
                    format = cell.format()
                    format.setBackground(QColor(c["raised"]))
                    cell.setFormat(format)
        recolor_document_links(document)
        self.fit_images()

    def fit_images(self):
        fit_images(self)


class HelpPage(QWidget):
    definition_requested = Signal(str)
    lesson_action_requested = Signal(QUrl)

    def __init__(self, snippets):
        super().__init__()
        repository = Path(__file__).resolve().parents[2] / "doc"
        self.base_root = (
            repository
            if repository.is_dir()
            else Path(str(files("little_tinker_rig") / "help_pages"))
        )
        self.root = self.base_root
        self.snippets = snippets
        self.pages = {}
        self.history = []
        self.recent_pages = []
        self.current = None
        self.lesson = None
        self.lesson_group = None
        self.lesson_item = None
        self.lesson_page_names = {}
        self.lesson_page_titles = {}
        self._search_expanded = None
        self._search_selected = None
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(230)
        self.browser = HelpBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.follow_link)
        self.find_matches = []
        self.find_index = -1
        self.find_field = QLineEdit()
        self.find_field.setPlaceholderText(N_("Find in document…"))
        self.find_field.setAccessibleName(N_("Find in document"))
        self.find_field.setMinimumWidth(240)
        self.find_field.setMaximumWidth(360)
        self.find_field.setClearButtonEnabled(True)
        self.find_field.textChanged.connect(self.find_in_document)
        self.find_field.returnPressed.connect(lambda: self.next_match(1))
        self.find_previous = QToolButton()
        self.find_previous.setText("↑")
        self.find_previous.setToolTip(N_("Previous match"))
        self.find_previous.setAccessibleName(N_("Previous match"))
        self.find_previous.clicked.connect(lambda: self.next_match(-1))
        self.find_next = QToolButton()
        self.find_next.setText("↓")
        self.find_next.setToolTip(N_("Next match"))
        self.find_next.setAccessibleName(N_("Next match"))
        self.find_next.clicked.connect(lambda: self.next_match(1))
        self.find_count = QLabel()
        find_row = QHBoxLayout()
        find_row.setContentsMargins(4, 3, 4, 3)
        find_row.addStretch(1)
        find_row.addWidget(self.find_field)
        find_row.addWidget(self.find_previous)
        find_row.addWidget(self.find_next)
        find_row.addWidget(self.find_count)
        self.find_count.hide()
        article = QWidget()
        article_layout = QVBoxLayout(article)
        article_layout.setContentsMargins(0, 0, 0, 0)
        article_layout.setSpacing(0)
        article_layout.addLayout(find_row)
        article_layout.addWidget(self.browser, 1)
        escape_find = QShortcut(QKeySequence("Escape"), self.find_field)
        escape_find.setContext(Qt.ShortcutContext.WidgetShortcut)
        escape_find.activated.connect(self.close_find)
        self.tree.currentItemChanged.connect(
            lambda item, old: (
                self.show_page(item.data(0, Qt.ItemDataRole.UserRole)) if item else None
            )
        )
        self.tree.itemClicked.connect(
            lambda item: (
                self.show_lesson_home(self.lesson)
                if self.lesson and item is self.lesson_item
                else None
            )
        )
        search = self.search = QLineEdit()
        search.setPlaceholderText(N_("Search help…"))
        search.setToolTip(N_("Search the guide and blocks…"))
        search.setAccessibleName(N_("Search the guide and blocks…"))
        search.setClearButtonEnabled(True)
        search.textChanged.connect(self.filter)
        clear = QShortcut(QKeySequence("Escape"), search)
        clear.setContext(Qt.ShortcutContext.WidgetShortcut)
        clear.activated.connect(search.clear)
        self.no_results = QLabel()
        self.no_results.setWordWrap(True)
        self.no_results.hide()
        self.back_button = QToolButton()
        self.back_button.setText("←")
        self.back_button.clicked.connect(self.back)
        self.recent_button = QToolButton()
        self.recent_button.setText("▾")
        self.recent_menu = QMenu(self.recent_button)
        self.recent_button.setMenu(self.recent_menu)
        self.recent_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        navigation = QHBoxLayout()
        navigation.setContentsMargins(0, 0, 0, 0)
        navigation.setSpacing(3)
        navigation.addWidget(self.back_button)
        navigation.addWidget(self.recent_button)
        navigation.addWidget(search, 1)
        sidebar = self.sidebar = QWidget()
        sidebar.setMinimumWidth(230)
        left = QVBoxLayout(sidebar)
        left.addLayout(navigation)
        left.addWidget(self.no_results)
        left.addWidget(self.tree)
        splitter = QSplitter()
        splitter.addWidget(sidebar)
        splitter.addWidget(article)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([270, 900])
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self._overlay_clearance = 0
        self.apply_theme()
        self.retranslate()

    def set_overlay_clearance(self, width):
        width = max(0, width)
        if width == self._overlay_clearance:
            return
        self._overlay_clearance = width
        self.sidebar.setVisible(not width)
        self.find_field.setMinimumWidth(160 if width else 240)
        self.layout().setContentsMargins(0, 0, width + 8 if width else 0, 0)

    def apply_theme(self):
        c = colors()
        self.tree.setStyleSheet(
            f"QTreeWidget {{ border: 0; background: {c['raised']}; "
            f"color: {c['text']}; font-size: 14px; }}"
            "QTreeWidget::item { padding: 7px 5px; }"
            f"QTreeWidget::item:selected {{ background: {c['selected']}; "
            f"color: {c['text']}; }}"
        )
        self.browser.setStyleSheet(
            f"QTextBrowser {{ border: 1px solid {c['border']}; "
            f"background: {c['panel']}; color: {c['text']}; "
            f"selection-background-color: {c['selected']}; "
            f"selection-color: {c['text']}; }}"
        )
        self.browser.document().setDefaultStyleSheet(f"a {{ color: {c['link']}; }}")
        scroll = self.browser.verticalScrollBar().value()
        self.browser.style_document()
        if self.current and self.current.startswith("lesson/instructions"):
            self.browser.refresh_lesson_numbers()
        self.browser.verticalScrollBar().setValue(scroll)

    def set_lesson(self, lesson):
        if lesson is self.lesson:
            return
        self.lesson = lesson
        self.history = [key for key in self.history if not key.startswith("lesson/")]
        self.recent_pages = [
            key for key in self.recent_pages if not key.startswith("lesson/")
        ]
        if self.current and self.current.partition("#")[0].startswith("lesson/"):
            self.current = None
        self.retranslate()

    def add_lesson_material(self, name, title=None):
        logical, _, _ = name.partition("#")
        identity = (
            "lesson/instructions"
            if logical == self.lesson_page_names.get("lesson/instructions")
            else "lesson/resource/" + logical
        )
        if identity not in self.pages:
            text = self.lesson.material(logical)
            self.pages[identity] = (text, self.lesson_item)
            self.page_paths[identity] = self.lesson.file(logical)
            self.lesson_page_names[identity] = logical
            if identity != "lesson/instructions":
                self.lesson_page_titles[identity] = self._lesson_material_title(
                    name, text
                )
        if title and identity != "lesson/instructions":
            self.lesson_page_titles[identity] = title
        return identity

    def _lesson_material_title(self, name, text):
        logical, _, _ = name.partition("#")
        links = [
            (
                localized(link["target"], language()),
                localized(link["label"], language()),
            )
            for stage in self.lesson.stages
            for link in stage.get("links", [])
            if link["kind"] == "markdown"
        ]
        for labels in (
            {label for target, label in links if target == name},
            {label for target, label in links if target.partition("#")[0] == logical},
        ):
            if len(labels) == 1:
                return labels.pop()
        heading = next(
            (line[2:].strip() for line in text.splitlines() if line.startswith("# ")),
            None,
        )
        return heading or Path(logical).stem

    def show_lesson_home(self, lesson):
        if lesson is None:
            return
        self.set_lesson(lesson)
        self.show_page("lesson/instructions")

    def show_lesson_material(self, lesson, name, title=None):
        self.set_lesson(lesson)
        identity = self.add_lesson_material(name, title)
        _, _, anchor = name.partition("#")
        self.show_page(identity + ("#" + anchor if anchor else ""))

    def show_lesson_stage(self, lesson, stage):
        self.set_lesson(lesson)
        anchor = lesson.instructions_anchor(stage, language())
        self.show_page("lesson/instructions" + ("#" + anchor if anchor else ""))

    def _translated_lesson_key(self, key, old_names, old_language):
        """Map open lesson pages through task IDs and translated resource links."""
        if not key or not self.lesson or not key.startswith("lesson/"):
            return key
        page, _, anchor = key.partition("#")
        if page == "lesson/instructions":
            if anchor:
                for stage in self.lesson.stages:
                    if self.lesson.instructions_anchor(stage, old_language) == anchor:
                        anchor = self.lesson.instructions_anchor(stage, language())
                        break
            return page + ("#" + anchor if anchor else "")
        logical = old_names.get(page)
        if logical is None:
            return None
        old_name = logical + ("#" + anchor if anchor else "")
        links = [
            (
                localized(link["target"], old_language),
                localized(link["target"], language()),
            )
            for stage in self.lesson.stages
            for link in stage.get("links", [])
            if link["kind"] == "markdown"
        ]
        target = next((new for old, new in links if old == old_name), None)
        if target is None:
            paths = {
                new.partition("#")[0]
                for old, new in links
                if old.partition("#")[0] == logical
            }
            target = (
                paths.pop() + ("#" + anchor if anchor else "")
                if len(paths) == 1
                else old_name
            )
        try:
            translated_page = self.add_lesson_material(target)
        except (OSError, ValueError):
            return None
        _, _, translated_anchor = target.partition("#")
        return translated_page + ("#" + translated_anchor if translated_anchor else "")

    def retranslate(self):
        current, history, recent = self.current, self.history, self.recent_pages
        old_names = self.lesson_page_names.copy()
        old_language = self.root.name
        self._search_expanded = None
        self._search_selected = None
        self.root = self.base_root / language()
        self.pages, self.page_paths, self.snippet_targets = {}, {}, {}
        self.lesson_page_names = {}
        self.lesson_page_titles = {}
        self.lesson_group = None
        self.lesson_item = None
        self.groups = snippet_groups(self.snippets)
        self.current = None
        self.tree.blockSignals(True)
        self.tree.clear()
        if self.lesson:
            project_activity = self.lesson.data.get("kind") == "project"
            self.lesson_group = QTreeWidgetItem(
                [tr("This project") if project_activity else tr("This lesson")]
            )
            self.tree.insertTopLevelItem(0, self.lesson_group)
            title = localized(self.lesson.data["title"], language())
            text, name = self.lesson.instructions_document(language())
            tasks = []
            for stage in self.lesson.stages:
                anchor = self.lesson.instructions_anchor(stage, language())
                if anchor:
                    stage_title = localized(stage["title"], language())
                    tasks.append(f"[{stage_title}](#{anchor})")
            if tasks:
                lines = text.splitlines(keepends=True)
                heading_end = 1 if lines and lines[0].startswith("# ") else 0
                contents = (
                    "\n**"
                    + (
                        tr("Activities in this project")
                        if project_activity
                        else tr("Tasks in this lesson")
                    )
                    + "**\n\n"
                )
                text = (
                    "".join(lines[:heading_end])
                    + contents
                    + "\n\n".join(tasks)
                    + "\n\n"
                    + "".join(lines[heading_end:])
                )
            self.add_page(self.lesson_group, "lesson/instructions", title, text)
            self.lesson_item = self.pages["lesson/instructions"][1]
            self.page_paths["lesson/instructions"] = self.lesson.file(name)
            self.lesson_page_names["lesson/instructions"] = name
        documents = QTreeWidgetItem(self.tree, [tr("Guide")])
        templates = QTreeWidgetItem(self.tree, [tr("Block library")])
        developers = QTreeWidgetItem(self.tree, [tr("Developer reference")])
        english = self.base_root / DEFAULT_LANGUAGE
        identities = {
            str(path.relative_to(root))
            for root in (english, self.root)
            for path in root.rglob("*.md")
        }
        for identity in (*GUIDE_ORDER, *sorted(identities - set(GUIDE_ORDER))):
            if identity not in identities:
                continue
            path = self.root / identity
            if not path.is_file():
                path = english / identity
            text = path.read_text(encoding="utf-8")
            self.add_page(
                developers if Path(identity) in DEVELOPER_PAGES else documents,
                identity,
                text.splitlines()[0].lstrip("# "),
                text,
            )
            self.page_paths[identity] = path
        for group, members in self.groups.items():
            identity = "library/" + group
            self.add_page(
                templates,
                identity,
                group_title(group, members),
                group_document(group, members),
            )
            self.page_paths[identity] = self.root / "snippets.md"
            for snippet in members:
                self.snippet_targets[snippet.identity] = (
                    identity + "#" + snippet.identity.rsplit("/", 1)[1]
                )
        self.tree.expandAll()
        if self.lesson:
            documents.setExpanded(False)
            templates.setExpanded(False)
            self.lesson_group.setExpanded(True)
        developers.setExpanded(False)
        self.tree.blockSignals(False)
        mapped_history = [
            self._translated_lesson_key(key, old_names, old_language) for key in history
        ]
        mapped_recent = [
            self._translated_lesson_key(key, old_names, old_language) for key in recent
        ]
        self.history = [
            key for key in mapped_history if key and key.partition("#")[0] in self.pages
        ]
        self.recent_pages = [
            key for key in mapped_recent if key and key.partition("#")[0] in self.pages
        ]
        self.back_button.setToolTip(tr("Back"))
        self.back_button.setAccessibleName(tr("Back"))
        self.recent_button.setToolTip(tr("Recent pages"))
        self.recent_button.setAccessibleName(tr("Recent pages"))
        self.search.setPlaceholderText(tr("Search help…"))
        self.search.setToolTip(tr("Search the guide and blocks…"))
        self.search.setAccessibleName(tr("Search the guide and blocks…"))
        self.find_field.setPlaceholderText(tr("Find in document…"))
        self.find_field.setAccessibleName(tr("Find in document"))
        self.find_previous.setToolTip(tr("Previous match"))
        self.find_previous.setAccessibleName(tr("Previous match"))
        self.find_next.setToolTip(tr("Next match"))
        self.find_next.setAccessibleName(tr("Next match"))
        destination = self._translated_lesson_key(current, old_names, old_language)
        if not destination or destination.partition("#")[0] not in self.pages:
            destination = (
                "lesson/instructions"
                if self.lesson and current and current.startswith("lesson/")
                else "index.md"
            )
        self.show_page(destination)
        self.filter(self.search.text())

    def add_page(self, parent, identity, title, text):
        item = QTreeWidgetItem(parent, [title])
        item.setToolTip(0, title)
        item.setData(0, Qt.ItemDataRole.UserRole, identity)
        self.pages[identity] = (text, item)

    def show_page(self, identity):
        if identity is None:
            return
        identity = self.snippet_targets.get(identity, identity)
        page, _, anchor = identity.partition("#")
        if page not in self.pages:
            return
        if self.pages[page][1].isHidden():
            self.search.clear()
        if identity == self.current:
            if anchor:
                self.browser.scrollToAnchor(anchor)
            else:
                self.browser.verticalScrollBar().setValue(0)
            self.find_in_document(self.find_field.text(), focus_first=False)
            return
        previous = self.current
        if previous and previous.partition("#")[0] != page:
            self.history.append(previous)
        self.current = identity
        self.recent_pages = [identity] + [
            key for key in self.recent_pages if key.partition("#")[0] != page
        ][:9]
        self._refresh_navigation()
        text, item = self.pages[page]
        self.tree.blockSignals(True)
        self.tree.setCurrentItem(item)
        item.parent().setExpanded(True)
        if page.startswith("lesson/"):
            for index in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(index)
                if group is not self.lesson_group:
                    group.setExpanded(False)
        self.tree.scrollToItem(item)
        self.tree.blockSignals(False)
        if previous is None or previous.partition("#")[0] != page:
            self.browser.document().setBaseUrl(
                QUrl.fromLocalFile(str(self.page_paths[page]))
            )
            self.browser.setMarkdown(text)
            # Qt's Markdown importer omits named anchors. Attach the same section
            # names used by the documentation checker, including stable block IDs.
            names = iter(heading_anchors(text))
            block = self.browser.document().begin()
            while block.isValid():
                if block.blockFormat().headingLevel():
                    cursor = QTextCursor(block)
                    cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                    format = cursor.charFormat()
                    format.setAnchor(True)
                    format.setAnchorNames(next(names, []))
                    cursor.mergeCharFormat(format)
                block = block.next()
            self.browser.style_document()
            self.browser.lesson_numbers = {}
            if page == "lesson/instructions":
                self.browser.lesson_numbers = {
                    stage_anchor: index
                    for index, stage in enumerate(self.lesson.stages, 1)
                    if (
                        stage_anchor := self.lesson.instructions_anchor(
                            stage, language()
                        )
                    )
                }
                self.browser.decorate_lesson_index(self.browser.lesson_numbers)
                self.browser.decorate_lesson_headings(self.browser.lesson_numbers)
        if anchor:
            self.browser.scrollToAnchor(anchor)
        else:
            self.browser.verticalScrollBar().setValue(0)
        self.find_in_document(self.find_field.text(), focus_first=False)

    def back(self):
        if self.history:
            previous = self.history.pop()
            self.current = None
            self.show_page(previous)

    def _refresh_navigation(self):
        self.back_button.setEnabled(bool(self.history))
        self.recent_menu.clear()
        current_page = self.current.partition("#")[0] if self.current else None
        for identity in self.recent_pages:
            page = identity.partition("#")[0]
            if page == current_page or page not in self.pages:
                continue
            title = self.pages[page][1].text(0)
            if page == "lesson/instructions":
                title = f"{self.lesson_group.text(0)} · {title}"
            elif page.startswith("lesson/resource/"):
                title = f"{title} · {self.lesson_page_titles[page]}"
            action = self.recent_menu.addAction(title)
            action.setData(identity)
            action.triggered.connect(
                lambda checked=False, key=identity: self.show_page(key)
            )
        self.recent_button.setEnabled(bool(self.recent_menu.actions()))

    def open_find(self):
        self.find_field.setFocus()
        self.find_field.selectAll()

    def close_find(self):
        self.find_field.clear()
        self.browser.setFocus()

    def find_in_document(self, query, *, focus_first=True):
        self.find_matches = []
        self.find_index = -1
        self.browser.setExtraSelections([])
        if query:
            position = 0
            document = self.browser.document()
            while True:
                cursor = document.find(query, position)
                if cursor.isNull():
                    break
                self.find_matches.append(cursor)
                position = cursor.selectionEnd()
            if self.find_matches:
                self.find_index = 0 if focus_first else -1
                self._show_find_match()
        self._update_find_count()

    def next_match(self, direction):
        if not self.find_matches:
            return
        if self.find_index < 0:
            self.find_index = 0 if direction > 0 else len(self.find_matches) - 1
        else:
            self.find_index = (self.find_index + direction) % len(self.find_matches)
        self._show_find_match()
        self._update_find_count()

    def _update_find_count(self):
        total = len(self.find_matches)
        self.find_count.setText(f"{self.find_index + 1 if total else 0}/{total}")
        self.find_count.setVisible(bool(self.find_field.text()))
        self.find_next.setEnabled(bool(total))
        self.find_previous.setEnabled(bool(total))

    def _show_find_match(self):
        selections = []
        for index, cursor in enumerate(self.find_matches):
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = QTextCharFormat()
            selection.format.setBackground(
                QColor("#facc15" if index == self.find_index else "#fef08a")
            )
            selection.format.setForeground(QColor("#172033"))
            selections.append(selection)
        self.browser.setExtraSelections(selections)
        if self.find_index >= 0:
            cursor = QTextCursor(self.find_matches[self.find_index])
            cursor.setPosition(cursor.selectionStart())
            self.browser.setTextCursor(cursor)
            self.browser.ensureCursorVisible()

    def filter(self, query):
        needle = query.strip().casefold()
        searching = bool(needle)
        if searching and self._search_expanded is None:
            self._search_expanded = {
                index: self.tree.topLevelItem(index).isExpanded()
                for index in range(self.tree.topLevelItemCount())
            }
            self._search_selected = self.tree.currentItem()
        for identity, (text, item) in self.pages.items():
            if identity.startswith("lesson/resource/"):
                continue
            if identity == "lesson/instructions":
                text += "".join(
                    content
                    for key, (content, _) in self.pages.items()
                    if key.startswith("lesson/resource/")
                )
            item.setHidden(needle not in (identity + text).casefold())
        for index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(index)
            group.setHidden(
                all(group.child(i).isHidden() for i in range(group.childCount()))
            )
            if searching and not group.isHidden():
                group.setExpanded(True)
        if not searching and self._search_expanded is not None:
            for index in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(index)
                group.setExpanded(self._search_expanded.get(index, group.isExpanded()))
            selected = self.tree.currentItem()
            if selected is not None and selected is not self._search_selected:
                ancestor = selected.parent()
                while ancestor is not None:
                    ancestor.setExpanded(True)
                    ancestor = ancestor.parent()
            self._search_expanded = None
            self._search_selected = None
        self.no_results.setText(
            tr("No matching pages. Clear the search to browse all topics.")
        )
        self.no_results.setVisible(
            searching
            and not any(not item.isHidden() for _, item in self.pages.values())
        )

    def follow_link(self, url):
        if url.scheme() == "little-tinker-rig-definition":
            self.definition_requested.emit(url.path())
            return
        if url.scheme() in {"https", "http"}:
            QDesktopServices.openUrl(url)
            return
        if self.current and self.current.partition("#")[0].startswith("lesson/"):
            if url.scheme() in {
                "program",
                "assembly",
                "control",
                "devices",
                "connect",
                "scratch",
                "lesson",
            }:
                self.lesson_action_requested.emit(url)
                return
            if url.scheme():
                return
            page = self.current.partition("#")[0]
            if not url.path():
                self.show_page(page + ("#" + url.fragment() if url.fragment() else ""))
                return
            logical = self.lesson_page_names[page]
            try:
                target = resource(
                    self.lesson.root, str(Path(logical).parent / url.path())
                )
            except ValueError:
                return
            name = target.relative_to(self.lesson.root).as_posix()
            if self.lesson.file(name).is_file():
                self.show_lesson_material(
                    self.lesson, name + ("#" + url.fragment() if url.fragment() else "")
                )
            return
        page = self.current.partition("#")[0]
        base = self.page_paths[page]
        path = (
            Path(url.toLocalFile()) if url.isLocalFile() else base.parent / url.path()
        )
        if not url.path() or path.resolve() == base.resolve() and url.fragment():
            identity = page
        else:
            try:
                relative = path.resolve().relative_to(self.base_root.resolve())
            except ValueError:
                return
            if relative.parts[0] not in LANGUAGES:
                return
            identity = str(Path(*relative.parts[1:]))
        self.show_page(identity + ("#" + url.fragment() if url.fragment() else ""))
