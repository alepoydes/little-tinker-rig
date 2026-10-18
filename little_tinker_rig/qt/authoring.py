"""Static block authoring with the document renderer above a Python editor."""

import ast
import keyword
import tomllib
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.core.analysis import Scopes
from little_tinker_rig.core.authoring import (
    BUILTINS,
    STARTERS,
    DefinitionDraft,
    collection_root,
    copy_definition,
)
from little_tinker_rig.core.block_metadata import change_property, decorator
from little_tinker_rig.core.imports import import_entries
from little_tinker_rig.core.migration import migrate_module
from little_tinker_rig.core.session import Session
from little_tinker_rig.core.snippets import LEVELS, instantiate, load_module
from little_tinker_rig.core.structure import name_span, rename
from little_tinker_rig.core.syntax import Syntax
from little_tinker_rig.core.versions import next_version
from little_tinker_rig.i18n import N_, tr

from .appearance import AppearanceChoice
from .catalog_properties import CatalogProperties
from .code import CodeEdit
from .editor import SourceView, qt_offset
from .library import LEVEL_TITLES, Library, group_title, snippet_title
from .localization import localize
from .navigation import tool_button
from .theme import colors, svg_icon


class DefinitionCode(CodeEdit):
    """Python highlighting plus template meaning; no program name diagnostics."""

    def __init__(self, draft):
        self.semantic = []
        self.problem = None
        self.references = []
        super().__init__(draft.path)
        self.draft = draft
        self.tree = None
        self.snippets = ()
        self.syntax = None
        self.setAcceptDrops(False)
        self.setPlainText(draft.source)
        self.setReadOnly(draft.read_only)

    def highlight_line(self):
        super().highlight_line()
        selections = self.extraSelections()
        source = self.toPlainText()
        for span, color, background in self.semantic + self.references:
            color = colors().get(color, color)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(self.document())
            selection.cursor.setPosition(qt_offset(source, span.start))
            selection.cursor.setPosition(
                qt_offset(source, span.end), QTextCursor.MoveMode.KeepAnchor
            )
            if background:
                selection.format.setBackground(QColor(color))
            else:
                selection.format.setForeground(QColor(color))
                selection.format.setFontWeight(600)
            selections.append(selection)
        if self.problem is not None:
            block = self.document().findBlockByNumber(self.problem - 1)
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.cursor = QTextCursor(block)
                selection.cursor.select(QTextCursor.SelectionType.LineUnderCursor)
                selection.format.setUnderlineColor(QColor(colors()["danger"]))
                selection.format.setUnderlineStyle(
                    QTextCharFormat.UnderlineStyle.WaveUnderline
                )
                selections.append(selection)
        self.setExtraSelections(selections)

    def inspect(self):
        self.semantic = []
        self.references = []
        self.problem = None
        try:
            self.tree, self.snippets = self.draft.inspect()
            self.syntax = Syntax(self.draft.source, fragment=True)
            for node in self.syntax.tree.body:
                if not isinstance(node, ast.FunctionDef):
                    continue
                if decorator(node) is None:
                    continue
                for item in node.decorator_list:
                    self.semantic.append((self.syntax.spans[item], "code_keyword", False))
                self.semantic.append((name_span(self.syntax, node), "code_keyword", False))
                for arg in (
                    *node.args.posonlyargs,
                    *node.args.args,
                    *node.args.kwonlyargs,
                ):
                    self.semantic.append(
                        (name_span(self.syntax, arg), "accent", False)
                    )
                    if arg.annotation:
                        self.semantic.append(
                            (self.syntax.spans[arg.annotation], "code_number", False)
                        )
                for value in ast.walk(node):
                    annotation = (
                        value.annotation
                        if isinstance(value, ast.AnnAssign)
                        else (
                            value.returns
                            if isinstance(value, ast.FunctionDef)
                            else None
                        )
                    )
                    if annotation is not None:
                        self.semantic.append(
                            (self.syntax.spans[annotation], "code_number", False)
                        )
            return None
        except (ValueError, SyntaxError) as error:
            self.tree = self.syntax = None
            self.snippets = ()
            self.problem = getattr(error, "lineno", None) or 1
            return error
        finally:
            self.highlight_line()

    def goto(self, span):
        cursor = self.textCursor()
        cursor.setPosition(qt_offset(self.toPlainText(), span.start))
        cursor.setPosition(
            qt_offset(self.toPlainText(), span.end), QTextCursor.MoveMode.KeepAnchor
        )
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()


class BlockPreview(SourceView):
    block_drop_target = False

    parameter_clicked = Signal(str)
    description_clicked = Signal()

    def __init__(self):
        super().__init__(Session.fragment("", ()))
        self.setAcceptDrops(False)

    def mousePressEvent(self, event):
        point = event.position().toPoint()
        slot = self.parameter_at(point)
        if slot and slot.match:
            self.parameter_clicked.emit(slot.parameter.name)
        elif self.note_at(point):
            self.description_clicked.emit()
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def contextMenuEvent(self, event):
        event.accept()

    def keyPressEvent(self, event):
        event.ignore()


class BlockEditor(QWidget):
    """Keep module buffers/undo and preview values independent of saved defaults."""

    saved = Signal(object, object)
    failed = Signal(str)
    changed = Signal()

    def __init__(self, ensure_collection, validate):
        super().__init__()
        self.ensure_collection = ensure_collection
        self.validate_collection = validate
        self.buffers = {}
        self.module_items = {}
        self.selected_name = None
        self.preview_snippet = None
        self.preview_key = None
        self.test_values = {}
        self.snippets = ()
        self.roots = ()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.check)
        self.search = QLineEdit()
        self.search.setPlaceholderText(N_("Find a definition…"))
        self.search.textChanged.connect(self.filter)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.currentItemChanged.connect(self.browse)
        self.starters = QComboBox()
        for label, key in (
            (N_("Action"), "action"),
            (N_("Expression"), "expression"),
            (N_("Multi-command action"), "sequence"),
        ):
            self.starters.addItem(label, key)
        self.module_name = QLineEdit("custom")
        self.module_name.setPlaceholderText(N_("Group / module"))
        self.module_name.setToolTip(
            N_("Module in your collection; its functions share a help page.")
        )
        self.new_button = QPushButton(N_("New block"))
        self.new_button.setObjectName("blockEditorNew")
        self.new_button.clicked.connect(
            lambda: self.attempt(
                lambda: self.create(STARTERS[self.starters.currentData()])
            )
        )
        left = QWidget()
        layout = QVBoxLayout(left)
        layout.addWidget(self.search)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.module_name)
        layout.addWidget(self.starters)
        layout.addWidget(self.new_button)
        self.folder_button = QPushButton(N_("Open blocks folder"))
        self.folder_button.clicked.connect(
            lambda: self.attempt(
                lambda: QDesktopServices.openUrl(
                    QUrl.fromLocalFile(str(self.ensure_collection()))
                )
            )
        )
        layout.addWidget(self.folder_button)
        self.version_button = QPushButton(N_("Start next version…"))
        self.version_button.clicked.connect(lambda: self.attempt(self.start_version))
        layout.addWidget(self.version_button)
        self.copy_button = tool_button(
            N_("Copy to my collection"), "duplicate"
        )
        self.copy_button.clicked.connect(lambda: self.attempt(self.copy_block))
        self.save_button = tool_button(
            N_("Save and apply"), "document-save"
        )
        self.save_button.clicked.connect(lambda: self.attempt(self.save))
        self.reopen_button = tool_button(
            N_("Reopen saved"), "edit-redo"
        )
        self.reopen_button.setToolTip(
            N_("Discard this module draft and reload its saved definition")
        )
        self.reopen_button.clicked.connect(lambda: self.attempt(self.reopen))
        self.level = QComboBox()
        self.level.setToolTip(N_("Block level · stored in the decorator"))
        for level in LEVELS:
            self.level.addItem(LEVEL_TITLES[level], level)
        self.level.currentIndexChanged.connect(self.change_level)
        self.icon = AppearanceChoice()
        self.icon.setToolTip(N_("Block icon · stored in the decorator"))
        self.icon.changed.connect(
            lambda value: self.attempt(lambda: self.change_metadata("icon", value))
        )
        self.color = AppearanceChoice(color=True)
        self.color.setToolTip(N_("Palette role or #RRGGBB · stored in the decorator"))
        self.color.changed.connect(
            lambda value: self.attempt(lambda: self.change_metadata("color", value))
        )
        self.catalog_button = QToolButton()
        self.catalog_button.setIcon(svg_icon("catalog"))
        self.catalog_button.setToolTip(N_("Catalog properties…"))
        self.catalog_button.setAccessibleName(N_("Catalog properties…"))
        self.catalog_button.clicked.connect(lambda: self.attempt(self.edit_catalog))
        self.caption = QLabel()
        self.caption.setProperty("translationSources", {})
        self.caption.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.status = QLabel()
        self.status.setProperty("translationSources", {})
        self.status.setWordWrap(True)
        self.status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status.mousePressEvent = lambda event: self.goto_error()
        self.hint = QLabel()
        self.hint.setProperty("translationSources", {})
        self.hint.setWordWrap(True)
        self.preview = BlockPreview()
        self.preview.parameter_clicked.connect(self.goto_parameter)
        self.preview.description_clicked.connect(self.goto_description)
        self.card = Library(())
        self.card.setDragEnabled(False)
        self.card.setRootIsDecorated(False)
        self.card.setIndentation(0)
        self.preview_stack = QStackedWidget()
        self.preview_stack.setMinimumHeight(90)
        self.preview_stack.addWidget(self.preview)
        self.preview_stack.addWidget(self.card)
        self.preview_mode = QComboBox()
        self.preview_mode.addItems([N_("In the program"), N_("In the library")])
        self.preview_mode.currentIndexChanged.connect(
            self.preview_stack.setCurrentIndex
        )
        self.preview_more = QLabel()
        self.preview_more.setProperty("translationSources", {})
        self.preview_more.setFixedHeight(self.fontMetrics().height())
        self.expand = tool_button(
            N_("Expand preview"), "expand-all"
        )
        self.expand.setCheckable(True)
        self.expand.toggled.connect(self.resize_preview)
        self.tests = tool_button(
            N_("Test values"), "test-values"
        )
        self.tests.setCheckable(True)
        self.test_panel = QScrollArea()
        self.test_panel.setWidgetResizable(True)
        self.test_panel.setMaximumHeight(160)
        self.test_panel.hide()
        self.tests.toggled.connect(self.test_panel.setVisible)
        self.reset_tests = tool_button(
            N_("Reset test values"), "edit-redo"
        )
        self.reset_tests.clicked.connect(self.reset_values)
        self.test_fields = {}
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(self.preview_mode)
        row.addWidget(self.expand)
        row.addWidget(self.tests)
        row.addWidget(self.reset_tests)
        row.addStretch()
        top_layout.addLayout(row)
        top_layout.addWidget(self.preview_stack, 1)
        top_layout.addWidget(self.preview_more)
        top_layout.addWidget(self.test_panel)
        self.code_stack = QStackedWidget()
        self.code_stack.setMinimumHeight(110)
        self.empty = CodeEdit()
        self.empty.setReadOnly(True)
        self.code_stack.addWidget(self.empty)
        self.preview_splitter = QSplitter(Qt.Orientation.Vertical)
        self.preview_splitter.addWidget(top)
        self.preview_splitter.addWidget(self.code_stack)
        self.preview_splitter.setChildrenCollapsible(False)
        self.preview_splitter.setStretchFactor(0, 0)
        self.preview_splitter.setStretchFactor(1, 1)
        self.preview_splitter.setSizes([160, 600])
        right = QWidget()
        layout = QVBoxLayout(right)
        row = QHBoxLayout()
        row.addWidget(self.copy_button)
        row.addWidget(self.level)
        row.addWidget(self.icon)
        row.addWidget(self.color)
        row.addWidget(self.catalog_button)
        row.addStretch()
        row.addWidget(self.reopen_button)
        row.addWidget(self.save_button)
        layout.addLayout(row)
        layout.addWidget(self.caption)
        layout.addWidget(self.preview_splitter, 1)
        layout.addWidget(self.hint)
        layout.addWidget(self.status)
        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([290, 1000])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.update_status()
        self.apply_theme()

    def apply_theme(self):
        self.new_button.setIcon(
            svg_icon("document-new", tint=colors()["accent_text"])
        )
        self.catalog_button.setIcon(svg_icon("catalog"))
        self.preview.apply_theme()
        self.card.itemDelegate().apply_theme()
        self.card.viewport().update()
        for editor in self.findChildren(CodeEdit):
            editor.apply_theme()

    @property
    def code(self):
        widget = self.code_stack.currentWidget()
        return widget if isinstance(widget, DefinitionCode) else None

    def attempt(self, callback):
        try:
            return callback()
        except (ValueError, SyntaxError, OSError) as error:
            self.failed.emit(str(error))
            return None

    def configure(self, snippets, roots):
        self.snippets = tuple(
            s for s in snippets if not s.historical and s.source_path is not None
        )
        self.roots = tuple(roots)
        self.rebuild_tree()
        if self.code is None and self.snippets:
            self.open_definition(self.snippets[0])

    def rebuild_tree(self):
        expanded = {
            str(item.data(0, Qt.ItemDataRole.UserRole)[0]): item.isExpanded()
            for item in getattr(self, "module_items", {}).values()
        }
        self.tree.blockSignals(True)
        self.tree.clear()
        groups = {}
        modules = {}
        self.module_items = modules
        paths = {s.source_path for s in self.snippets}
        for root in self.roots:
            manifest = tomllib.loads(
                (Path(root) / "collection.toml").read_text(encoding="utf-8")
            )
            history = [
                (Path(root) / item["path"]).resolve()
                for item in manifest.get("history", [])
            ]
            paths.update(
                path
                for path in Path(root).rglob("*.py")
                if path.name != "__init__.py"
                and not any(path.is_relative_to(directory) for directory in history)
            )
            drafts = Path(root) / ".drafts"
            paths.update(
                Path(root) / path.relative_to(drafts).as_posix().removesuffix(".json")
                for path in drafts.rglob("*.py.json")
            )
        paths.update(
            path
            for path, code in self.buffers.items()
            if code.draft.root in self.roots or code.draft.read_only
        )
        for path in sorted(paths):
            root = collection_root(path)
            group = groups.get(root)
            if group is None:
                builtin = path.is_relative_to(BUILTINS)
                title = (
                    tr("Built-in · {name}", name=root.name)
                    if builtin
                    else tr("My collection · {name}", name=root.name)
                )
                group = groups[root] = QTreeWidgetItem(self.tree, [title])
                group.setToolTip(0, str(root))
                group.setExpanded(True)
            item = modules[path] = QTreeWidgetItem(
                group, [path.relative_to(root).as_posix()]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, (str(path), ""))
            item.setExpanded(expanded.get(str(path), False))
        for snippet in self.snippets:
            item = QTreeWidgetItem(
                modules[snippet.source_path], [snippet.identity.rsplit("/", 1)[1]]
            )
            item.setToolTip(0, snippet_title(snippet) + "\n" + tr(snippet.help))
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                (str(snippet.source_path), snippet.identity.rsplit("/", 1)[1]),
            )
        self.tree.blockSignals(False)
        for code in self.buffers.values():
            self.update_module(code)
        self.select_tree()
        self.filter(self.search.text())

    def update_module(self, code):
        item = self.module_items.get(code.draft.path)
        if item is None or code.tree is None:
            return
        self.tree.blockSignals(True)
        item.takeChildren()
        for snippet in code.snippets:
            name = snippet.identity.rsplit("/", 1)[1]
            child = QTreeWidgetItem(item, [name])
            child.setToolTip(0, snippet_title(snippet) + "\n" + tr(snippet.help))
            child.setData(0, Qt.ItemDataRole.UserRole, (str(code.draft.path), name))
        self.tree.blockSignals(False)

    def select_tree(self):
        item = self.module_items.get(self.code.draft.path) if self.code else None
        if item is None:
            return
        self.tree.blockSignals(True)
        item.setExpanded(True)
        selected = next(
            (
                item.child(i)
                for i in range(item.childCount())
                if item.child(i).text(0) == self.selected_name
            ),
            item,
        )
        self.tree.setCurrentItem(selected)
        self.tree.scrollToItem(selected)
        self.tree.blockSignals(False)

    def filter(self, text):
        words = text.casefold().split()

        def visit(item, parent_text=""):
            content = parent_text + " " + item.text(0) + " " + item.toolTip(0)
            own = all(word in content.casefold() for word in words)
            children = [visit(item.child(i), content) for i in range(item.childCount())]
            visible = own or any(children)
            item.setHidden(not visible)
            if words and visible:
                item.setExpanded(True)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(i))

    def browse(self, item, old):
        data = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if data:
            self.attempt(lambda: self.open_path(Path(data[0]), data[1]))

    def open_definition(self, snippet):
        if snippet.source_path:
            self.open_path(snippet.source_path, snippet.identity.rsplit("/", 1)[1])

    def open_path(self, path, name=""):
        if self.code:
            self.code.selected_name = self.selected_name
        self.flush()
        path = path.resolve()
        if path not in self.buffers:
            code = DefinitionCode(DefinitionDraft(path))
            code.textChanged.connect(lambda: self.edited(code))
            code.cursorPositionChanged.connect(self.cursor_changed)
            self.buffers[path] = code
            self.code_stack.addWidget(code)
        self.code_stack.setCurrentWidget(self.buffers[path])
        self.selected_name = name or getattr(self.code, "selected_name", None)
        self.preview_key = None
        self.preview_snippet = None
        self.preview.session = Session.fragment("", ())
        self.preview.refresh_source()
        self.card.load(())
        self.check()
        if not self.code.tree and self.code.draft.preview_source:
            self.restore_preview()
        if self.code.tree:
            function = next(
                (
                    n
                    for n in self.code.syntax.tree.body
                    if isinstance(n, ast.FunctionDef) and (not name or n.name == name)
                ),
                None,
            )
            if function:
                self.code.goto(name_span(self.code.syntax, function))
        self.update_status(keep_message=True)
        self.select_tree()

    def edited(self, code):
        code.draft.source = code.toPlainText()
        code.semantic = []
        code.references = []
        code.problem = None
        code.tree = code.syntax = None
        code.snippets = ()
        code.highlight_line()
        if code is self.code:
            self.timer.start()
            self.status.setText(tr("Checking… · showing the last valid preview"))
            self.update_status(keep_message=True)
        self.changed.emit()

    def flush(self):
        self.timer.stop()
        for code in self.buffers.values():
            code.draft.persist()

    def check(self):
        self.timer.stop()
        code = self.code
        if code is None:
            return
        if not code.draft.read_only:
            try:
                migrated = code.draft.migrated_source()
            except (SyntaxError, ValueError):
                migrated = code.toPlainText()
            if migrated != code.toPlainText():
                self.replace_source(migrated)
        error = code.inspect()
        self.attempt(code.draft.persist)
        if error:
            self.status.setStyleSheet(f"color: {colors()['danger']};")
            self.status.setText(
                tr(
                    "Line {line}: {error} · showing the last valid preview",
                    line=code.problem,
                    error=getattr(error, "msg", str(error)),
                )
            )
        else:
            self.status.setStyleSheet("")
            self.status.setText(tr("Preview only; template code is never executed."))
            self.cursor_changed()
            self.update_preview()
            self.update_module(code)
            self.select_tree()
        self.update_status(keep_message=True)

    def restore_preview(self):
        """Recover the last checked preview while leaving the invalid draft intact."""
        draft = self.code.draft
        snippets = load_module(draft.preview_source, draft.identity, draft.version)
        snippet = next(
            (s for s in snippets if s.identity.rsplit("/", 1)[1] == self.selected_name),
            snippets[0] if snippets else None,
        )
        if snippet:
            self.preview_snippet = snippet
            expansion = instantiate(
                snippet,
                {p.name: p.name for p in snippet.parameters if p.default is None},
            )
            self.preview.session = Session.fragment(expansion.source + "\n", (snippet,))
            self.preview.refresh_source()
            self.limit_preview()
            self.card.load((replace(snippet, family=""),))
            heading = self.card.takeTopLevelItem(0)
            self.card.addTopLevelItem(heading.takeChild(0))

    def function(self):
        if not self.code or not self.code.syntax:
            return None
        return next(
            (
                n
                for n in self.code.syntax.tree.body
                if isinstance(n, ast.FunctionDef) and n.name == self.selected_name
            ),
            None,
        )

    def cursor_changed(self):
        code = self.code
        if not code or not code.syntax:
            return
        row = code.textCursor().blockNumber() + 1
        helper = next(
            (
                node
                for node in code.syntax.tree.body
                if isinstance(node, ast.FunctionDef)
                and decorator(node) is None
                and node.lineno <= row <= node.end_lineno
            ),
            None,
        )
        if helper:
            self.hint.setText(
                tr(
                    "Helper: shared ordinary Python; it does not appear in the block library."
                )
            )
            return
        function = next(
            (
                n
                for n in code.syntax.tree.body
                if isinstance(n, ast.FunctionDef)
                and decorator(n)
                and (n.decorator_list[0].lineno if n.decorator_list else n.lineno)
                <= row
                <= n.end_lineno
            ),
            None,
        )
        if function and function.name != self.selected_name:
            self.selected_name = function.name
            self.preview_key = None
            self.update_preview()
            self.select_tree()
        function = function or self.function()
        if function:
            label = tr("Body: the Python inserted into the program.")
            if self.preview_snippet and self.preview_snippet.mode == "function":
                label = tr(
                    "Body: an ordinary helper function with private local variables."
                )
            if row < function.body[0].lineno:
                label = tr(
                    "Signature: block name, parameters, defaults and units/types."
                )
            if row < function.lineno:
                label = tr(
                    "Decorator: insertion mode, level, appearance and editable names."
                )
            for node in function.body:
                if node.lineno <= row <= node.end_lineno:
                    if node is function.body[0] and ast.get_docstring(function):
                        label = tr("Docstring: the block description and search text.")
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        label = tr(
                            "Imports: dependencies added automatically on insertion."
                        )
            self.hint.setText(label)
        self.changed.emit()

    def update_preview(self):
        code = self.code
        if not code or not code.tree:
            return
        snippet = next(
            (
                s
                for s in code.snippets
                if s.identity.rsplit("/", 1)[1] == self.selected_name
            ),
            None,
        )
        if snippet is None and code.snippets:
            snippet = code.snippets[0]
            self.selected_name = snippet.identity.rsplit("/", 1)[1]
        if snippet is None:
            self.preview_snippet = None
            self.selected_name = None
            self.preview.session = Session.fragment("", ())
            self.preview.refresh_source()
            self.card.load(())
            self.limit_preview()
            self.level.setEnabled(False)
            return
        key = (code.draft.path, snippet.identity)
        values = self.test_values.setdefault(key, {})
        values = {
            p.name: values[p.name] for p in snippet.parameters if p.name in values
        }
        self.test_values[key] = values
        defaults = {
            p.name: p.default if p.default is not None else p.name
            for p in snippet.parameters
        }
        try:
            expansion = instantiate(snippet, defaults | values)
        except (ValueError, SyntaxError) as error:
            self.status.setStyleSheet(f"color: {colors()['danger']};")
            self.status.setText(
                tr(
                    "Invalid test value: {error} · showing the last valid preview",
                    error=str(error),
                )
            )
            return
        level = snippet.level
        self.preview_snippet = snippet
        self.preview.session = Session.fragment(expansion.source + "\n", (snippet,))
        self.preview.refresh_source()
        self.limit_preview()
        self.card.load((replace(snippet, family=""),))
        # Display the same library card without a redundant group heading.
        heading = self.card.takeTopLevelItem(0)
        self.card.addTopLevelItem(heading.takeChild(0))
        fields_key = (key, snippet.parameters)
        if self.preview_key != fields_key:
            self.preview_key = fields_key
            form_widget = QWidget()
            form = QFormLayout(form_widget)
            self.test_fields = {}
            for parameter in snippet.parameters:
                field = QLineEdit(values.get(parameter.name, defaults[parameter.name]))
                field.setToolTip(
                    N_("Preview value only; does not change the definition default.")
                )
                localize(field)
                field.editingFinished.connect(
                    lambda name=parameter.name, entry=field: self.test_value(
                        name, entry.text()
                    )
                )
                form.addRow(
                    parameter.name
                    + (f" · {parameter.annotation}" if parameter.annotation else ""),
                    field,
                )
                self.test_fields[parameter.name] = field
            old = self.test_panel.takeWidget()
            if old:
                old.deleteLater()
            self.test_panel.setWidget(form_widget)
        self.level.blockSignals(True)
        self.level.setCurrentIndex(self.level.findData(level))
        self.level.blockSignals(False)
        self.icon.set_value(snippet.icon or "▶")
        self.color.set_value(snippet.color or "snippet")
        self.update_status(keep_message=True)

    def test_value(self, name, value):
        if self.code and self.code.tree and self.preview_snippet:
            key = (self.code.draft.path, self.preview_snippet.identity)
            self.test_values.setdefault(key, {})[name] = value
            self.status.setStyleSheet("")
            self.status.setText(tr("Preview only; template code is never executed."))
            self.update_preview()

    def reset_values(self):
        if self.code and self.preview_snippet:
            self.test_values.pop(
                (self.code.draft.path, self.preview_snippet.identity), None
            )
            self.preview_key = None
            self.check()

    def goto_parameter(self, name):
        function = self.function()
        if not function:
            return
        syntax = self.code.syntax
        path = name.split(".")
        owner_node = function
        for part in path[:-1]:
            owner_node = next(
                (
                    n
                    for n in owner_node.body
                    if isinstance(n, ast.FunctionDef) and n.name == part
                ),
                None,
            )
            if owner_node is None:
                return
        name = path[-1]
        parameter = next(
            (
                p
                for p in (
                    *owner_node.args.posonlyargs,
                    *owner_node.args.args,
                    *owner_node.args.kwonlyargs,
                )
                if p.arg == name
            ),
            None,
        )
        scopes = Scopes(syntax.tree)
        owner = scopes.defined_scopes[owner_node]
        if parameter is None:
            parameter = next(
                (
                    n
                    for n in ast.walk(owner_node)
                    if (
                        isinstance(n, ast.Name)
                        and isinstance(n.ctx, ast.Store)
                        and n.id == name
                        or isinstance(n, ast.FunctionDef)
                        and n is not owner_node
                        and n.name == name
                    )
                    and scopes.resolve(n, name) is owner
                ),
                None,
            )
        if parameter:
            self.code.references = [
                (syntax.spans[n], "#ffe09a", True)
                for n in ast.walk(function)
                if isinstance(n, ast.Name)
                and n.id == name
                and scopes.resolve(n, name) is owner
            ]
            self.code.goto(name_span(syntax, parameter))
            self.code.highlight_line()

    def goto_description(self):
        function = self.function()
        if function and ast.get_docstring(function):
            self.code.goto(self.code.syntax.spans[function.body[0]])

    def goto_error(self):
        if self.code and self.code.problem:
            block = self.code.document().findBlockByNumber(self.code.problem - 1)
            self.code.setTextCursor(QTextCursor(block))
            self.code.setFocus()

    def change_level(self):
        if self.code and not self.code.draft.read_only and self.selected_name:
            self.attempt(
                lambda: self.change_metadata("level", self.level.currentData())
            )

    def replace_source(self, source):
        """One ordinary text edit, retaining the buffer's undo history."""
        previous = self.code.toPlainText()
        if source == previous:
            return
        start = 0
        while (
            start < min(len(previous), len(source)) and previous[start] == source[start]
        ):
            start += 1
        end = 0
        while (
            end < min(len(previous), len(source)) - start
            and previous[-end - 1] == source[-end - 1]
        ):
            end += 1
        cursor = QTextCursor(self.code.document())
        cursor.beginEditBlock()
        cursor.setPosition(qt_offset(previous, start))
        cursor.setPosition(
            qt_offset(previous, len(previous) - end), QTextCursor.MoveMode.KeepAnchor
        )
        cursor.insertText(source[start : len(source) - end])
        cursor.endEditBlock()

    def change_metadata(self, name, value):
        if self.code and not self.code.draft.read_only and self.function():
            self.replace_source(
                change_property(
                    self.code.toPlainText(), self.selected_name, name, value
                )
            )
            self.check()

    def edit_catalog(self):
        code = self.code
        if (
            not code
            or not code.tree
            or code.draft.read_only
            or not self.preview_snippet
        ):
            return
        original = code.toPlainText()
        dialog = CatalogProperties(
            original, self.preview_snippet, (*self.snippets, *code.snippets), self
        )
        accepted = dialog.exec()
        result = dialog.source
        dialog.deleteLater()
        if accepted:
            if self.code is not code or code.toPlainText() != original:
                raise ValueError(tr("Document changed; choose the block again"))
            self.replace_source(result)
            self.check()

    def update_status(self, *, keep_message=False):
        code = self.code
        editable = code is not None and not code.draft.read_only
        self.save_button.setEnabled(editable)
        self.reopen_button.setEnabled(editable)
        self.version_button.setEnabled(editable)
        self.level.setEnabled(editable and self.function() is not None)
        self.icon.setEnabled(editable and self.function() is not None)
        self.color.setEnabled(editable and self.function() is not None)
        self.catalog_button.setEnabled(
            bool(editable and code.tree and self.preview_snippet)
        )
        self.copy_button.setEnabled(self.function() is not None)
        if code:
            state = (
                tr("Read-only")
                if code.draft.read_only
                else tr("Draft") if code.draft.dirty else tr("Saved")
            )
            kind = (
                tr("Expression")
                if self.preview_snippet and self.preview_snippet.expression
                else tr("Action")
            )
            self.caption.setText(
                f"{code.draft.path.name} · {group_title(code.draft.identity, code.snippets)} · {kind} · {state}"
            )
            self.caption.setToolTip(str(code.draft.path))
        else:
            self.caption.setText(tr("Choose a block to inspect its definition."))
        if not keep_message:
            self.status.setText(tr("Preview only; template code is never executed."))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        orientation = (
            Qt.Orientation.Horizontal
            if event.size().height() < 430
            else Qt.Orientation.Vertical
        )
        if self.preview_splitter.orientation() != orientation:
            self.preview_splitter.setOrientation(orientation)
            self.resize_preview(self.expand.isChecked())

    def resize_preview(self, expanded):
        total = sum(self.preview_splitter.sizes())
        size = (
            320
            if expanded
            else (
                230
                if self.preview_splitter.orientation() == Qt.Orientation.Horizontal
                else 160
            )
        )
        self.preview_splitter.setSizes([size, max(200, total - size)])
        self.limit_preview()

    def limit_preview(self):
        expanded = self.expand.isChecked()
        document = self.preview.document()
        block = document.begin()
        while block.isValid():
            block.setVisible(expanded or block.blockNumber() < 4)
            block = block.next()
        document.markContentsDirty(0, document.characterCount())
        self.preview.viewport().update()
        remaining = max(0, len(self.preview.toPlainText().splitlines()) - 4)
        self.preview_more.setText(
            tr("… {count} more lines", count=remaining)
            if remaining and not expanded
            else ""
        )

    def create(self, source, *, level=None):
        root = self.ensure_collection()
        module = self.module_name.text().strip()
        if (
            not module
            or not all(
                part.isidentifier() and not keyword.iskeyword(part)
                for part in module.split("/")
            )
            or module.endswith("__init__")
            or module.split("/")[0] == "history"
        ):
            raise ValueError(
                tr("Use a Python module name, for example custom or robots/motors.")
            )
        path = root / (module + ".py")
        source = migrate_module(
            source,
            root.name + "/" + module,
            "1",
            (
                {
                    node.name: level
                    for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef)
                }
                if level
                else None
            ),
        )
        self.open_path(path)
        if self.code.tree is None:
            raise ValueError(
                tr(
                    "Correct this module's draft or choose another group before adding a block."
                )
            )
        names = set(Scopes(self.code.tree).root.bindings)
        copied = Session.fragment(source, ())

        def imports(tree):
            return dict(
                import_entries(
                    node
                    for node in tree.body
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                )
            )

        existing = imports(self.code.tree)
        conflicts = {
            name
            for name, text in imports(copied.document.syntax.tree).items()
            if name in names and existing.get(name) != text
        }
        if conflicts:
            raise ValueError(
                tr(
                    "Import names conflict: {names}. Choose another group or use aliases.",
                    names=", ".join(sorted(conflicts)),
                )
            )
        functions = [
            n
            for n in copied.document.syntax.tree.body
            if isinstance(n, ast.FunctionDef)
        ]
        reserved = names | {n.name for n in functions}
        added = []
        for original in functions:
            function = next(
                n
                for n in copied.document.syntax.tree.body
                if isinstance(n, ast.FunctionDef) and n.name == original.name
            )
            name = function.name
            index = 2
            while name in names or name != function.name and name in reserved:
                name = f"{function.name}_{index}"
                index += 1
            names.add(name)
            reserved.add(name)
            if name != function.name:
                copied.editor.commit(rename(copied, function, name))
            if decorator(function):
                added.append(name)
        source = copied.document.state.source
        cursor = self.code.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(("\n\n" if self.code.toPlainText().strip() else "") + source)
        self.code.setTextCursor(cursor)
        self.selected_name = added[-1] if added else None
        self.check()
        self.rebuild_tree()
        function = self.function()
        if function:
            self.code.goto(name_span(self.code.syntax, function))
        self.code.setFocus()

    def copy_block(self):
        function = self.function()
        if function:
            source = self.code.draft.source
            level = self.preview_snippet.level
            self.create(copy_definition(source, function.name), level=level)

    def save(self):
        if self.code:
            self.check()
            snippets = self.code.draft.save(self.validate_collection)
            self.saved.emit(self.code.draft.root, snippets)
            self.update_status()
            self.changed.emit()

    def start_version(self):
        if not self.code or self.code.draft.read_only:
            return
        self.flush()
        root = self.code.draft.root
        old = tomllib.loads((root / "collection.toml").read_text())["collection"][
            "version"
        ]
        major, minor, _ = map(int, old.split("."))
        version, accepted = QInputDialog.getText(
            self,
            tr("Start next version"),
            tr(
                "Archive saved version {version} before editing the next version. Save or discard every draft first.",
                version=old,
            ),
            text=f"{major}.{minor + 1}.0",
        )
        if not accepted:
            return
        snippets = next_version(root, version.strip(), self.validate_collection)
        for code in self.buffers.values():
            if code.draft.root == root and not code.draft.historical:
                code.draft = DefinitionDraft(code.draft.path)
        self.saved.emit(root, snippets)
        self.check()
        self.changed.emit()

    def reopen(self):
        if self.code:
            from PySide6.QtWidgets import QMessageBox

            code = self.code
            if (
                code.draft.dirty
                and QMessageBox.question(
                    self,
                    tr("Discard draft"),
                    tr(
                        "Discard this module's changes and reopen the saved definition?"
                    ),
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            path = code.draft.path
            code.draft.draft_path.unlink(missing_ok=True)
            self.timer.stop()
            del self.buffers[path]
            self.code_stack.removeWidget(code)
            code.deleteLater()
            self.open_path(path)

    def retranslate(self):
        localize(self)
        self.icon.retranslate()
        self.color.retranslate()
        self.rebuild_tree()
        self.check()
