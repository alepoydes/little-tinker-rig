"""Offline Markdown documentation and snippet help in one navigable workspace."""

import ast
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pyblocks.i18n import LANGUAGES, language, tr


class HelpBrowser(QTextBrowser):
    def resizeEvent(self, event):
        super().resizeEvent(event)
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
            width = min(source.width(), max(1, self.viewport().width() - 20))
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
    def __init__(self, snippets):
        super().__init__()
        repository = Path(__file__).resolve().parents[2] / "doc"
        self.base_root = (
            repository
            if repository.is_dir()
            else Path(str(files("pyblocks") / "help_pages"))
        )
        self.root = self.base_root
        self.snippets = snippets
        self.pages = {}
        self.history = []
        self.current = None
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(230)
        self.browser = HelpBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.follow_link)
        self.browser.setStyleSheet(
            "QTextBrowser { padding: 22px; border: 0; background: white; font-size: 15px; }"
        )
        self.tree.currentItemChanged.connect(
            lambda item, old: (
                self.show_page(item.data(0, Qt.ItemDataRole.UserRole)) if item else None
            )
        )
        search = QLineEdit()
        search.setPlaceholderText("Поиск в руководстве и блоках…")
        search.textChanged.connect(self.filter)
        back = QPushButton("← Назад")
        back.clicked.connect(self.back)
        sidebar = QWidget()
        left = QVBoxLayout(sidebar)
        left.addWidget(back)
        left.addWidget(search)
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
        self.root = (
            self.base_root if language() == "ru" else self.base_root / language()
        )
        self.pages = {}
        self.current = None
        self.tree.blockSignals(True)
        self.tree.clear()
        documents = QTreeWidgetItem(self.tree, [tr("Руководство")])
        for path in sorted(self.root.rglob("*.md")):
            if path.relative_to(self.root).parts[0] in LANGUAGES:
                continue
            text = path.read_text(encoding="utf-8")
            title = text.splitlines()[0].lstrip("# ")
            self.add_page(documents, str(path.relative_to(self.root)), title, text)
        templates = QTreeWidgetItem(self.tree, [tr("Библиотека блоков")])
        for snippet in self.snippets:
            if snippet.historical:
                continue
            parameters = "\n".join(
                f"| `{p.name}` | {p.annotation or 'Python'} | `{p.default or '—'}` |"
                for p in snippet.parameters
            )
            source = (
                ast.unparse(snippet.body)
                if snippet.expression
                else "\n".join(ast.unparse(node) for node in snippet.body)
            )
            text = (
                f"# {snippet.identity}\n\n{tr(snippet.help)}\n\n## {tr('Параметры')}\n\n"
                f"| {tr('Имя')} | {tr('Единица / тип')} | {tr('По умолчанию')} |\n|---|---|---|\n{parameters}\n\n"
                f"## Python\n\n```python\n{source}\n```\n"
            )
            self.add_page(
                templates, snippet.identity, snippet.identity.rsplit("/", 1)[-1], text
            )
        self.tree.expandAll()
        self.tree.blockSignals(False)
        self.history = [key for key in history if key in self.pages]
        self.show_page(current if current in self.pages else "tutorial/first.md")

    def add_page(self, parent, identity, title, text):
        item = QTreeWidgetItem(parent, [title])
        item.setData(0, Qt.ItemDataRole.UserRole, identity)
        self.pages[identity] = (text, item)

    def show_page(self, identity):
        if identity not in self.pages or identity == self.current:
            return
        if self.current:
            self.history.append(self.current)
        self.current = identity
        text, item = self.pages[identity]
        self.tree.blockSignals(True)
        self.tree.setCurrentItem(item)
        self.tree.blockSignals(False)
        base = (
            self.root / identity
            if identity.endswith(".md")
            else self.root / "snippets.md"
        )
        self.browser.document().setBaseUrl(QUrl.fromLocalFile(str(base)))
        self.browser.setMarkdown(text)
        self.browser.fit_images()

    def back(self):
        if self.history:
            previous = self.history.pop()
            self.current = None
            self.show_page(previous)

    def filter(self, query):
        for identity, (text, item) in self.pages.items():
            item.setHidden(query.casefold() not in (identity + text).casefold())

    def follow_link(self, url):
        if url.scheme() in {"https", "http"}:
            QDesktopServices.openUrl(url)
            return
        if not url.path():
            self.browser.scrollToAnchor(url.fragment())
            return
        base = (
            self.root / self.current
            if self.current and self.current.endswith(".md")
            else self.root / "snippets.md"
        )
        path = (
            Path(url.toLocalFile()) if url.isLocalFile() else base.parent / url.path()
        )
        try:
            identity = str(path.resolve().relative_to(self.root.resolve()))
        except ValueError:
            return
        self.show_page(identity)
        if url.fragment():
            self.browser.scrollToAnchor(url.fragment())
