"""Offline Markdown documentation and snippet help in one navigable workspace."""

import ast
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QKeySequence,
    QShortcut,
    QTextBlockFormat,
    QTextCursor,
    QTextDocument,
    QTextFrameFormat,
    QTextTable,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.core.snippets import snippet_groups
from little_tinker_rig.documentation import DEVELOPER_PAGES, heading_anchors
from little_tinker_rig.i18n import DEFAULT_LANGUAGE, LANGUAGES, N_, language, tr

from .library import LEVEL_TITLES, group_title, snippet_title

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
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_images()

    def style_document(self):
        document = self.document()
        document.setDefaultFont(QFont("sans-serif", 12))
        document.setDocumentMargin(32)
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
            format.setTopMargin(24 if heading else 0)
            format.setBottomMargin(12 if heading else 0 if code else 12)
            if code:
                format.setBackground(QColor("#edf2f7"))
                format.setLeftMargin(14)
                format.setRightMargin(14)
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                text_format = cursor.charFormat()
                text_format.setFont(
                    QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
                )
                text_format.setFontPointSize(10.5)
                text_format.setForeground(QColor("#24394e"))
                cursor.mergeCharFormat(text_format)
            elif heading:
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                text_format = cursor.charFormat()
                text_format.setFontPointSize(
                    25 if heading == 1 else 18 if heading == 2 else 14
                )
                text_format.setForeground(QColor("#193650"))
                text_format.setFontWeight(QFont.Weight.DemiBold)
                cursor.mergeCharFormat(text_format)
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
                format.setBorderBrush(QColor("#d8e2ec"))
                frame.setFormat(format)
                for column in range(frame.columns()):
                    cell = frame.cellAt(0, column)
                    format = cell.format()
                    format.setBackground(QColor("#eaf1f8"))
                    cell.setFormat(format)
        self.fit_images()

    def fit_images(self):
        document = self.document()
        block = document.begin()
        images = []
        while block.isValid():
            fragment = block.begin()
            while not fragment.atEnd():
                text = fragment.fragment()
                if text.charFormat().isImageFormat():
                    images.append((text.position(), text.charFormat().toImageFormat()))
                fragment += 1
            block = block.next()
        for position, format in images:
            source = document.resource(
                QTextDocument.ResourceType.ImageResource, QUrl(format.name())
            )
            if source is None or source.width() <= 0:
                continue
            width = min(
                source.width(),
                max(1, self.viewport().width() - 2 * document.documentMargin() - 4),
            )
            if format.width() == width:
                continue
            format.setWidth(width)
            format.setHeight(width * source.height() / source.width())
            cursor = QTextCursor(document)
            cursor.setPosition(position)
            cursor.movePosition(
                QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor
            )
            cursor.setCharFormat(format)


class HelpPage(QWidget):
    definition_requested = Signal(str)

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
        self.current = None
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(230)
        self.tree.setStyleSheet(
            "QTreeWidget { border: 0; background: #f3f6fa; font-size: 14px; } QTreeWidget::item { padding: 7px 5px; } QTreeWidget::item:selected { background: #dce8f2; color: #18364d; }"
        )
        self.browser = HelpBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setMaximumWidth(1120)
        self.browser.anchorClicked.connect(self.follow_link)
        self.browser.setStyleSheet(
            "QTextBrowser { border: 1px solid #e0e7ef; background: white; color: #263b4d; selection-background-color: #d2e5f5; }"
        )
        self.tree.currentItemChanged.connect(
            lambda item, old: (
                self.show_page(item.data(0, Qt.ItemDataRole.UserRole)) if item else None
            )
        )
        search = self.search = QLineEdit()
        search.setPlaceholderText(N_("Search the guide and blocks…"))
        search.setClearButtonEnabled(True)
        search.textChanged.connect(self.filter)
        clear = QShortcut(QKeySequence("Escape"), search)
        clear.setContext(Qt.ShortcutContext.WidgetShortcut)
        clear.activated.connect(search.clear)
        self.no_results = QLabel()
        self.no_results.setWordWrap(True)
        self.no_results.hide()
        back = QPushButton(N_("← Back"))
        back.clicked.connect(self.back)
        sidebar = QWidget()
        left = QVBoxLayout(sidebar)
        left.addWidget(back)
        left.addWidget(search)
        left.addWidget(self.no_results)
        left.addWidget(self.tree)
        splitter = QSplitter()
        splitter.addWidget(sidebar)
        splitter.addWidget(self.browser)
        splitter.setSizes([270, 900])
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.retranslate()

    def retranslate(self):
        current, history = self.current, self.history
        self.root = self.base_root / language()
        self.pages, self.page_paths, self.snippet_targets = {}, {}, {}
        self.groups = snippet_groups(self.snippets)
        self.current = None
        self.tree.blockSignals(True)
        self.tree.clear()
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
        developers.setExpanded(False)
        self.tree.blockSignals(False)
        self.history = [key for key in history if key.partition("#")[0] in self.pages]
        self.show_page(
            current
            if current and current.partition("#")[0] in self.pages
            else "index.md"
        )
        self.filter(self.search.text())

    def add_page(self, parent, identity, title, text):
        item = QTreeWidgetItem(parent, [title])
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
            return
        previous = self.current
        if previous:
            self.history.append(previous)
        self.current = identity
        text, item = self.pages[page]
        self.tree.blockSignals(True)
        self.tree.setCurrentItem(item)
        item.parent().setExpanded(True)
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
        if anchor:
            self.browser.scrollToAnchor(anchor)
        else:
            self.browser.verticalScrollBar().setValue(0)

    def back(self):
        if self.history:
            previous = self.history.pop()
            self.current = None
            self.show_page(previous)

    def filter(self, query):
        for identity, (text, item) in self.pages.items():
            item.setHidden(query.casefold() not in (identity + text).casefold())
        for index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(index)
            group.setHidden(
                all(group.child(i).isHidden() for i in range(group.childCount()))
            )
            if query and not group.isHidden():
                group.setExpanded(True)
        self.no_results.setText(
            tr("No matching pages. Clear the search to browse all topics.")
        )
        self.no_results.setVisible(
            not any(not item.isHidden() for _, item in self.pages.values())
        )

    def follow_link(self, url):
        if url.scheme() == "little-tinker-rig-definition":
            self.definition_requested.emit(url.path())
            return
        if url.scheme() in {"https", "http"}:
            QDesktopServices.openUrl(url)
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
