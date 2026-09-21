"""Desktop application; widgets translate gestures into core operations."""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pyblocks.core.session import Session

from .dialogs import EditDialog
from .editor import SourceView


class Library(QTreeWidget):
    def mimeData(self, items):
        data = QMimeData()
        if items and items[0].data(0, Qt.ItemDataRole.UserRole):
            data.setData(
                "application/x-pyblocks-snippet",
                items[0].data(0, Qt.ItemDataRole.UserRole).encode(),
            )
        return data


class Studio(QMainWindow):
    def __init__(self, path: Path, collections=()):
        super().__init__()
        self.session = Session(path, collections)
        self.resize(1250, 800)
        self.robot = None
        self.source = SourceView(self.session)
        self.source.selected.connect(self.refresh_status)
        self.source.changed.connect(self.refresh_views)
        self.source.failed.connect(self.error)
        self.source.snippet_dropped.connect(self.insert_snippet)
        self.library = Library()
        self.library.setHeaderHidden(True)
        self.library.setDragEnabled(True)
        self.library.itemDoubleClicked.connect(self.insert_selected)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search Library")
        self.search.textChanged.connect(self.filter_library)
        library = QWidget()
        layout = QVBoxLayout(library)
        layout.addWidget(QLabel("Library"))
        layout.addWidget(self.search)
        layout.addWidget(self.library)
        insert = QPushButton("Insert selected snippet")
        insert.clicked.connect(self.insert_selected)
        layout.addWidget(insert)
        self.scratch = QListWidget()
        self.scratch.itemDoubleClicked.connect(self.edit_scratch)
        scratch = QWidget()
        layout = QVBoxLayout(scratch)
        layout.addWidget(QLabel("Scratch · unfinished code"))
        layout.addWidget(self.scratch)
        for label, callback in (
            ("New fragment", self.new_scratch),
            ("Edit fragment", self.edit_scratch),
            ("Restore at selection", self.restore_scratch),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            layout.addWidget(button)
        splitter = QSplitter()
        for widget in (library, self.source, scratch):
            splitter.addWidget(widget)
        splitter.setSizes([250, 750, 250])
        self.setCentralWidget(splitter)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(5000)
        dock = QDockWidget("Console", self)
        dock.setWidget(self.console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self.help_view = QTextBrowser()
        self.help_dock = QDockWidget("Help", self)
        self.help_dock.setWidget(self.help_view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.help_dock)
        self.help_dock.hide()
        self._menus()
        self._library()
        self.refresh_views()

    def _action(self, menu, label, shortcut, callback, toolbar=None):
        action = QAction(label, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda checked=False: self.perform(callback))
        menu.addAction(action)
        if toolbar:
            toolbar.addAction(action)
        return action

    def _menus(self):
        toolbar = self.addToolBar("Editor")
        file = self.menuBar().addMenu("File")
        self._action(file, "Open…", "Ctrl+O", self.open_file)
        self._action(
            file, "Save", "Ctrl+S", lambda: self.session.project.save(), toolbar
        )
        self._action(file, "Save as…", "Ctrl+Shift+S", self.save_as)
        edit = self.menuBar().addMenu("Edit")
        for label, key, callback in (
            ("Undo", "Ctrl+Z", self.session.editor.undo),
            ("Redo", "Ctrl+Shift+Z", self.session.editor.redo),
            ("Parent", "Alt+Left", self.session.editor.parent),
            ("Child", "Alt+Right", self.session.editor.child),
            ("Edit as Python…", "F2", self.edit_python),
            ("Parameters…", "F3", self.edit_parameters),
            ("Expand / collapse snippet", "Ctrl+E", self.session.toggle_expansion),
            ("To Scratch", "Ctrl+X", self.session.to_scratch),
            ("Upgrade snippet", "Ctrl+U", self.session.upgrade_selected),
        ):
            self._action(
                edit,
                label,
                key,
                callback,
                toolbar if key in {"F2", "F3", "Ctrl+X"} else None,
            )
        move = self.menuBar().addMenu("Move")
        for label, key, callback in (
            ("Begin move", "Ctrl+M", self.session.begin_move),
            (
                "Previous target / sibling",
                "Alt+Up",
                lambda: self.navigate(-1),
            ),
            ("Next target / sibling", "Alt+Down", lambda: self.navigate(1)),
            (
                "Outward",
                "Ctrl+Alt+Left",
                lambda: self.session.editor.navigate_move(depth=-1),
            ),
            (
                "Inward",
                "Ctrl+Alt+Right",
                lambda: self.session.editor.navigate_move(depth=1),
            ),
            ("Commit move", "Ctrl+Return", self.session.editor.commit_move),
            ("Cancel move", "Escape", self.session.editor.cancel_move),
        ):
            self._action(move, label, key, callback)
        view = self.menuBar().addMenu("View")
        self._action(view, "Fold selection", "Ctrl+F", self.source.fold_selection)
        self._action(view, "Help", "F1", self.show_help, toolbar)
        self._action(view, "Name diagnostics", None, self.show_diagnostics)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Structure "))
        intensity = QSlider(Qt.Orientation.Horizontal)
        intensity.setRange(0, 100)
        intensity.setValue(65)
        intensity.setFixedWidth(100)
        intensity.valueChanged.connect(self.set_intensity)
        toolbar.addWidget(intensity)
        robot = self.menuBar().addMenu("Robot")
        for label, key, callback in (
            ("Connect…", "F7", self.connect_hub),
            ("Run", "F5", self.run_hub),
            ("Stop", "F6", self.stop_hub),
            ("Disconnect", None, self.disconnect_hub),
            ("Controls", None, self.show_controls),
        ):
            self._action(robot, label, key, callback, toolbar if key else None)

    def _library(self):
        groups = {}
        for snippet in self.session.snippets:
            if snippet.historical:
                continue
            group, name = snippet.identity.rsplit("/", 1)
            if group not in groups:
                groups[group] = QTreeWidgetItem(self.library, [group])
                groups[group].setFlags(
                    groups[group].flags() & ~Qt.ItemFlag.ItemIsDragEnabled
                )
            item = QTreeWidgetItem(groups[group], [name])
            item.setData(0, Qt.ItemDataRole.UserRole, snippet.identity)
            item.setToolTip(0, snippet.help.splitlines()[0] if snippet.help else "")
        self.library.expandAll()

    def filter_library(self, search):
        for index in range(self.library.topLevelItemCount()):
            group = self.library.topLevelItem(index)
            visible = False
            for child_index in range(group.childCount()):
                item = group.child(child_index)
                match = (
                    search.casefold()
                    in (item.text(0) + item.toolTip(0) + group.text(0)).casefold()
                )
                item.setHidden(not match)
                visible |= match
            group.setHidden(not visible)

    def refresh_views(self):
        self.source.refresh_source()
        selected = self.scratch.currentRow()
        self.scratch.clear()
        for index, text in enumerate(self.session.document.state.scratch):
            first = text.strip().splitlines()[0] if text.strip() else "(empty)"
            self.scratch.addItem(f"{index}: {first}")
            self.scratch.item(index).setToolTip(text)
        if 0 <= selected < self.scratch.count():
            self.scratch.setCurrentRow(selected)
        self.refresh_status()

    def refresh_status(self):
        match = self.session.selected_match()
        selection = (
            match.snippet.identity
            if match
            else type(self.session.editor.selection).__name__
        )
        self.statusBar().showMessage(
            f"{selection} · {len(self.session.analysis.diagnostics())} name warning(s)"
        )
        self.setWindowTitle(
            f"{'* ' if self.session.project.dirty else ''}{self.session.project.path.name} — PyBlocks Studio"
        )
        self.source.viewport().update()

    def perform(self, callback):
        try:
            callback()
            self.refresh_views()
        except (ValueError, SyntaxError, OSError, ImportError) as error:
            self.error(str(error))

    def error(self, message):
        self.statusBar().showMessage(message, 15000)
        self.console.appendPlainText(message)

    def _dialog(self, title, apply, **kwargs):
        dialog = EditDialog(self, title, apply, **kwargs)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_views()

    def insert_selected(self, *_):
        item = self.library.currentItem()
        if item and item.data(0, Qt.ItemDataRole.UserRole):
            self.insert_snippet(item.data(0, Qt.ItemDataRole.UserRole), None)

    def insert_snippet(self, identity, target=None):
        snippet = next(
            s
            for s in self.session.snippets
            if s.identity == identity and not s.historical
        )
        offset = self.session.document.syntax.spans[self.session.editor.selection].start
        self._dialog(
            identity,
            lambda values: self.session.insert_snippet(snippet, values, target),
            snippet=snippet,
            names=self.session.analysis.available(offset),
        )

    def edit_python(self):
        self._dialog(
            "Edit as Python",
            self.session.edit_python,
            text=self.session.selected_text(),
        )

    def edit_parameters(self):
        match = self.session.selected_match()
        if match is None:
            raise ValueError("Select a recognized snippet first")
        self._dialog(
            match.snippet.identity,
            self.session.edit_parameters,
            snippet=match.snippet,
            bindings=match.bindings,
            names=self.session.analysis.available(match.span.start),
        )

    def new_scratch(self):
        self._dialog(
            "New Scratch fragment",
            lambda text: self.session.set_scratch(None, text),
            text="",
        )

    def edit_scratch(self, *_):
        index = self.scratch.currentRow()
        if index >= 0:
            self._dialog(
                "Edit Scratch",
                lambda text: self.session.set_scratch(index, text),
                text=self.session.document.state.scratch[index],
            )

    def restore_scratch(self):
        index = self.scratch.currentRow()
        if index >= 0:
            self.perform(lambda: self.session.restore_scratch(index))

    def show_help(self):
        item = self.library.currentItem() if self.library.hasFocus() else None
        identity = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        match = self.session.selected_match()
        snippet = (
            next(
                (
                    s
                    for s in self.session.snippets
                    if s.identity == identity and not s.historical
                ),
                None,
            )
            if identity
            else match.snippet if match else None
        )
        text = (
            f"# {snippet.identity}\n\n{snippet.help}"
            if snippet
            else "# PyBlocks Studio\n\nSelect Python code to work with its structure. Alt+Left/Right selects a parent/child. Drag a statement to a green insertion line.\n\nDouble-click a Library snippet to insert it. F3 changes parameters; F2 edits ordinary Python. Invalid text stays in the dialog until corrected or cancelled.\n\nScratch holds unfinished fragments. Ctrl+X moves code there; Restore inserts a selected fragment. Ctrl+S saves, Ctrl+Z undoes.\n\nRobot: F7 connects, F5 uploads/runs, F6 stops."
        )
        self.help_view.setMarkdown(text)
        self.help_dock.show()

    def show_diagnostics(self):
        diagnostics = self.session.analysis.diagnostics()
        for diagnostic in diagnostics:
            line, column = self.session.document.syntax.position(diagnostic.span.start)
            self.console.appendPlainText(f"{line}:{column}: {diagnostic.message}")
        if not diagnostics:
            self.console.appendPlainText("No undefined names found.")

    def set_intensity(self, value):
        self.source.intensity = value / 100
        self.source.viewport().update()

    def navigate(self, step):
        editor = self.session.editor
        if editor.moving:
            editor.navigate_move(step)
        else:
            editor.sibling(step)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Python", str(self.session.project.path.parent), "Python (*.py)"
        )
        if path:
            window = Studio(Path(path))
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            window.show()
            QApplication.instance().windows.append(window)

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Python", str(self.session.project.path), "Python (*.py)"
        )
        if path:
            from pyblocks.core.project import Project

            project = Project(Path(path))
            project.document = self.session.document
            project.collections = self.session.project.collections
            project.pins = self.session.project.pins
            project.save()
            self.session.project = project

    def _robot(self):
        if self.robot is None:
            from .robot import Robot

            self.robot = Robot(self)
            self.robot.output.connect(self.console.insertPlainText)
            self.robot.failed.connect(self.error)
            self.robot.status.connect(self.statusBar().showMessage)
        return self.robot

    def connect_hub(self):
        name, accepted = QInputDialog.getText(
            self, "Connect hub", "Bluetooth name (empty: first available)"
        )
        if accepted:
            self._robot().connect_hub(name or None)

    def run_hub(self):
        self.session.project.save()
        self._robot().run_file(self.session.project.path)

    def stop_hub(self):
        self._robot().stop_program()

    def disconnect_hub(self):
        if self.robot:
            self.robot.disconnect_hub()

    def show_controls(self):
        self._robot().show_controls()

    def closeEvent(self, event):
        if self.session.project.dirty:
            result = QMessageBox.question(
                self,
                "Unsaved changes",
                "Save changes before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if result == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if result == QMessageBox.StandardButton.Save:
                try:
                    self.session.project.save()
                except (ValueError, OSError) as error:
                    self.error(str(error))
                    event.ignore()
                    return
        if self.robot:
            self.robot.close()
        event.accept()


def launch(path: Path, collections=()) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = Studio(path, collections)
    app.windows = [window]
    window.show()
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(description="PyBlocks desktop editor")
    parser.add_argument("file", type=Path, nargs="?", default=Path("main.py"))
    return launch(parser.parse_args().file)
