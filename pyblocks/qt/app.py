"""Desktop workspaces over one source document and one active hub connection."""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTabBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pyblocks.core.session import Session
from pyblocks.pybricks.control import ControlState
from pyblocks.pybricks.devices import HubInfo

from .code import CodeEdit
from .controls import ControlsPage
from .device import ConnectDialog, DevicePanel
from .dialogs import EditDialog
from .editor import SourceView, source_offset
from .help import HelpPage
from .library import IDENTITY, Library


class Studio(QMainWindow):
    def __init__(self, path: Path, collections=()):
        super().__init__()
        self.session = Session(path, collections, allow_draft=True)
        self.session.editor.select(0)
        self.resize(1380, 880)
        self.setMinimumSize(930, 620)
        self.robot = None
        self.hub_info = HubInfo()
        self.hub_is_busy = False
        self.code_active = False
        self.unread = 0
        self.child_windows = []
        self.setStyleSheet("""
            QMainWindow { background: #f3f6fa; }
            QToolBar { border: 0; spacing: 5px; padding: 5px; background: #f3f6fa; }
            QToolButton { padding: 5px 8px; border-radius: 6px; }
            QToolButton:hover { background: #dfe8f2; }
            QToolButton:checked { background: #d0e8e4; color: #155d57; }
            QDockWidget { font-weight: bold; }
            QLineEdit { padding: 6px; border: 1px solid #c5d0dc; border-radius: 5px; }
            QTreeWidget, QListWidget { background: #f8fafc; border: 0; }
            QPushButton { padding: 6px 10px; }
            QStatusBar { background: #e8eef5; }
        """)
        self.source = SourceView(self.session)
        self.source.selected.connect(self.refresh_status)
        self.source.changed.connect(self.refresh_views)
        self.source.failed.connect(self.error)
        self.source.snippet_dropped.connect(self.insert_snippet)
        self.code = CodeEdit()
        self.code.textChanged.connect(self.refresh_status)
        self.editor_stack = QStackedWidget()
        self.editor_stack.addWidget(self.source)
        self.editor_stack.addWidget(self.code)
        self.editor_tabs = QTabBar()
        self.editor_tabs.addTab("Блоки")
        self.editor_tabs.addTab("Python")
        self.editor_tabs.currentChanged.connect(self.change_editor)
        self.code_message = QLabel(
            "Выберите блок, чтобы изменить параметры. Перетаскивайте блоки мышью."
        )
        self.code_message.setWordWrap(True)
        self.find_bar = QLineEdit()
        self.find_bar.setPlaceholderText(
            "Найти в программе · Enter — следующее совпадение"
        )
        self.find_bar.returnPressed.connect(self.find_next)
        self.find_bar.hide()
        program = QWidget()
        layout = QVBoxLayout(program)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.addWidget(self.editor_tabs)
        layout.addWidget(self.code_message)
        layout.addWidget(self.find_bar)
        layout.addWidget(self.editor_stack, 1)
        self.library = Library(self.session.snippets)
        self.library.itemDoubleClicked.connect(self.insert_selected)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Найти блок…")
        self.search.textChanged.connect(self.library.filter)
        library = QWidget()
        layout = QVBoxLayout(library)
        layout.addWidget(QLabel("Библиотека · перетащите блок в программу"))
        layout.addWidget(self.search)
        layout.addWidget(self.library, 1)
        insert = QPushButton("＋ Добавить выбранный блок")
        insert.clicked.connect(self.insert_selected)
        layout.addWidget(insert)
        self.library_pane = library
        self.program_page = QSplitter()
        self.program_page.addWidget(library)
        self.program_page.addWidget(program)
        self.program_page.setSizes([320, 1060])
        self.controls = ControlsPage()
        self.controls.monitor_requested.connect(self.start_monitor)
        self.controls.drive_requested.connect(
            lambda commands: self._robot().drive(commands)
        )
        self.controls.input_requested.connect(lambda state: self._robot().send(state))
        self.controls.failed.connect(self.error)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.controls)
        self.help_page = HelpPage(self.session.snippets)
        self.pages = QStackedWidget()
        for page in (self.program_page, scroll, self.help_page):
            self.pages.addWidget(page)
        self.setCentralWidget(self.pages)
        self._docks()
        self._menus()
        self._modes()
        self.refresh_views()
        self.update_hub(HubInfo())
        if self.session.project.draft is not None:
            self.editor_tabs.setCurrentIndex(1)
            self.code.setPlainText(self.session.project.draft)
            self.code_message.setText(
                "В файле есть незавершённый Python. Исправьте его перед сохранением или переходом к блокам."
            )
        QApplication.instance().applicationStateChanged.connect(self.application_state)

    def _icon(self, theme, fallback):
        return QIcon.fromTheme(
            theme, self.style().standardIcon(getattr(QStyle.StandardPixmap, fallback))
        )

    def _action(self, menu, label, shortcut, callback, toolbar=None, icon=None):
        action = QAction(label, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if icon:
            action.setIcon(self._icon(*icon))
        action.setToolTip(label + (f" · {shortcut}" if shortcut else ""))
        action.triggered.connect(lambda checked=False: self.perform(callback))
        menu.addAction(action)
        if toolbar:
            toolbar.addAction(action)
        return action

    def _docks(self):
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(5000)
        console_page = QWidget()
        layout = QVBoxLayout(console_page)
        row = QHBoxLayout()
        row.addWidget(QLabel("Вывод программы и сообщения"))
        row.addStretch()
        clear = QPushButton("Очистить")
        clear.clicked.connect(self.console.clear)
        row.addWidget(clear)
        layout.addLayout(row)
        layout.addWidget(self.console)
        self.console_dock = self.dock(
            "Консоль", console_page, Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.console_dock.visibilityChanged.connect(self.console_visibility)
        self.console_dock.hide()
        self.scratch = QListWidget()
        self.scratch.itemDoubleClicked.connect(self.edit_scratch)
        scratch = QWidget()
        layout = QVBoxLayout(scratch)
        note = QLabel("Здесь можно оставить незаконченный код и запасные блоки.")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addWidget(self.scratch)
        for label, callback in (
            ("＋ Новый фрагмент", self.new_scratch),
            ("Редактировать", self.edit_scratch),
            ("Вернуть в программу", self.restore_scratch),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            layout.addWidget(button)
        self.scratch_dock = self.dock(
            "Черновики · Scratch", scratch, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.scratch_dock.hide()
        self.device_panel = DevicePanel()
        self.device_panel.monitor_requested.connect(self.start_monitor)
        self.device_panel.disconnect_requested.connect(self.disconnect_hub)
        self.device_panel.configure_requested.connect(
            lambda port, kind, value: self._robot().configure(port, kind, value)
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.device_panel)
        self.device_dock = self.dock(
            "Хаб и устройства", scroll, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.device_dock.setMinimumWidth(285)
        self.device_dock.hide()

    def dock(self, title, widget, area):
        dock = QDockWidget(title, self)
        dock.setObjectName(title)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock

    def _menus(self):
        toolbar = self.addToolBar("Программа")
        toolbar.setObjectName("programTools")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(23, 23))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        file = self.menuBar().addMenu("Файл")
        self._action(
            file,
            "Новый",
            "Ctrl+N",
            self.new_file,
            toolbar,
            ("document-new", "SP_FileIcon"),
        )
        self._action(
            file,
            "Открыть",
            "Ctrl+O",
            self.open_file,
            toolbar,
            ("document-open", "SP_DirOpenIcon"),
        )
        self._action(
            file,
            "Сохранить",
            "Ctrl+S",
            self.save,
            toolbar,
            ("document-save", "SP_DialogSaveButton"),
        )
        self._action(file, "Сохранить как…", "Ctrl+Shift+S", self.save_as)
        toolbar.addSeparator()
        edit = self.menuBar().addMenu("Правка")
        self.undo_action = self._action(
            edit,
            "Отменить",
            "Ctrl+Z",
            self.undo,
            toolbar,
            ("edit-undo", "SP_ArrowBack"),
        )
        self.redo_action = self._action(
            edit,
            "Повторить",
            "Ctrl+Shift+Z",
            self.redo,
            toolbar,
            ("edit-redo", "SP_ArrowForward"),
        )
        toolbar.addSeparator()
        self.structural_actions = []
        for label, key, callback, icon in (
            (
                "Параметры",
                "F3",
                self.edit_parameters,
                ("document-properties", "SP_FileDialogDetailedView"),
            ),
            (
                "Фрагмент Python",
                "F2",
                self.edit_python,
                ("accessories-text-editor", "SP_FileDialogContentsView"),
            ),
            ("В черновики", "Ctrl+X", self.to_scratch, ("edit-cut", "SP_ArrowRight")),
        ):
            self.structural_actions.append(
                self._action(edit, label, key, callback, toolbar, icon)
            )
        for label, key, callback in (
            ("Родитель", "Alt+Left", self.session.editor.parent),
            ("Потомок", "Alt+Right", self.session.editor.child),
            ("Предыдущий узел / цель", "Alt+Up", lambda: self.navigate(-1)),
            ("Следующий узел / цель", "Alt+Down", lambda: self.navigate(1)),
            ("Раскрыть блок", "Ctrl+E", self.session.toggle_expansion),
            ("Начать перенос", "Ctrl+M", self.session.begin_move),
            (
                "Наружу",
                "Ctrl+Alt+Left",
                lambda: self.session.editor.navigate_move(depth=-1),
            ),
            (
                "Внутрь",
                "Ctrl+Alt+Right",
                lambda: self.session.editor.navigate_move(depth=1),
            ),
            ("Завершить перенос", "Ctrl+Return", self.session.editor.commit_move),
            ("Отменить перенос", "Escape", self.session.editor.cancel_move),
            ("Обновить блок", "Ctrl+U", self.session.upgrade_selected),
            ("Свернуть область", "Ctrl+Shift+F", self.source.fold_selection),
        ):
            self.structural_actions.append(self._action(edit, label, key, callback))
        self._action(edit, "Форматировать Python", "Ctrl+Alt+L", self.commit_code)
        self._action(edit, "Найти", "Ctrl+F", self.show_find)
        view = self.menuBar().addMenu("Вид")
        view.addAction(self.console_dock.toggleViewAction())
        view.addAction(self.scratch_dock.toggleViewAction())
        view.addAction(self.device_dock.toggleViewAction())
        self._action(view, "Справка", "F1", self.show_help)
        self._action(view, "Диагностика имён", None, self.show_diagnostics)
        toolbar.addSeparator()
        robot = self.menuBar().addMenu("Хаб")
        self.run_action = self._action(
            robot,
            "Запустить",
            "F5",
            self.run_hub,
            toolbar,
            ("media-playback-start", "SP_MediaPlay"),
        )
        self.stop_action = self._action(
            robot,
            "Стоп",
            "F6",
            self.stop_hub,
            toolbar,
            ("media-playback-stop", "SP_MediaStop"),
        )
        self._action(robot, "Подключить…", "F7", self.connect_hub)
        self._action(robot, "Отключить", None, self.disconnect_hub)
        self._action(robot, "Ручное управление", None, self.show_controls)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.hub_button = QToolButton()
        self.hub_button.setIcon(self._icon("network-connect", "SP_ComputerIcon"))
        self.hub_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.hub_button.clicked.connect(
            lambda: (
                self.device_dock.setVisible(not self.device_dock.isVisible())
                if self.hub_info.connected
                else self.connect_hub()
            )
        )
        toolbar.addWidget(self.hub_button)
        self.console_button = QToolButton()
        self.console_button.setIcon(
            self._icon("utilities-terminal", "SP_FileDialogListView")
        )
        self.console_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.console_button.setText("Консоль")
        self.console_button.clicked.connect(
            lambda: self.console_dock.setVisible(not self.console_dock.isVisible())
        )
        self.statusBar().addPermanentWidget(self.console_button)
        scratch_button = QToolButton()
        scratch_button.setText("Черновики")
        scratch_button.clicked.connect(
            lambda: self.scratch_dock.setVisible(not self.scratch_dock.isVisible())
        )
        self.statusBar().addPermanentWidget(scratch_button)
        self.statusBar().addPermanentWidget(QLabel("Цвет блоков"))
        intensity = QSlider(Qt.Orientation.Horizontal)
        intensity.setRange(0, 100)
        intensity.setValue(65)
        intensity.setFixedWidth(90)
        intensity.valueChanged.connect(self.set_intensity)
        self.statusBar().addPermanentWidget(intensity)

    def _modes(self):
        toolbar = QToolBar("Режимы", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(27, 27))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        toolbar.setObjectName("modes")
        group = QActionGroup(self)
        self.mode_actions = []
        for index, (label, icon) in enumerate(
            (
                ("Программа", ("text-x-script", "SP_FileIcon")),
                ("Управление", ("input-gaming", "SP_ComputerIcon")),
                ("Помощь", ("help-contents", "SP_DialogHelpButton")),
            )
        ):
            action = QAction(self._icon(*icon), label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, i=index: self.set_mode(i))
            group.addAction(action)
            toolbar.addAction(action)
            self.mode_actions.append(action)
        self.mode_actions[0].setChecked(True)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

    @property
    def draft_dirty(self):
        return (
            self.code_active
            and self.code.toPlainText() != self.session.document.state.source
        )

    def change_editor(self, index):
        try:
            if index == 0:
                self.commit_code()
            else:
                self.code.setPlainText(self.session.document.state.source)
            self.code_active = bool(index)
            self.editor_stack.setCurrentIndex(index)
            self.library_pane.setVisible(not index)
            self.code_message.setText(
                "Обычный Python · форматирование при сохранении · Ctrl+Space — дополнение · Ctrl+Alt+L — форматировать"
                if index
                else "Выберите блок, чтобы изменить параметры. Перетаскивайте блоки мышью."
            )
            self.refresh_views()
            (self.code if index else self.source).setFocus()
        except (ValueError, SyntaxError, OSError) as error:
            self.editor_tabs.blockSignals(True)
            self.editor_tabs.setCurrentIndex(1)
            self.editor_tabs.blockSignals(False)
            self.code_message.setText(str(error))
            self.error(str(error))

    def commit_code(self):
        if self.code_active:
            self.session.editor.commit(self.code.toPlainText())
            self.session.project.draft = None
            self.code.replace_formatted(self.session.document.state.source)
            self.source.refresh_source()

    def set_mode(self, index):
        self.pages.setCurrentIndex(index)
        self.mode_actions[index].setChecked(True)
        if index == 1:
            self.device_dock.show()
        elif index == 2:
            self.device_dock.hide()
            self.scratch_dock.hide()
        self.refresh_status()

    def refresh_views(self):
        self.source.refresh_source()
        selected = self.scratch.currentRow()
        self.scratch.clear()
        for index, text in enumerate(self.session.document.state.scratch):
            self.scratch.addItem(
                f'{index + 1}: {text.strip().splitlines()[0] if text.strip() else "(пустой фрагмент)"}'
            )
            self.scratch.item(index).setToolTip(text)
        if 0 <= selected < self.scratch.count():
            self.scratch.setCurrentRow(selected)
        self.refresh_status()

    def refresh_status(self):
        if not hasattr(self, "undo_action"):
            return
        match = self.session.selected_match()
        selection = (
            match.snippet.help.splitlines()[0]
            if match and match.snippet.help
            else "Python" if self.code_active else "Выберите блок"
        )
        self.statusBar().showMessage(
            f"{selection} · предупреждений: {len(self.session.analysis.diagnostics())}"
        )
        self.setWindowTitle(
            f'{"● " if self.session.project.dirty or self.draft_dirty else ""}{self.session.project.path.name} — PyBlocks Studio'
        )
        self.undo_action.setEnabled(
            self.code.document().isUndoAvailable()
            if self.code_active
            else self.session.document.can_undo
        )
        self.redo_action.setEnabled(
            self.code.document().isRedoAvailable()
            if self.code_active
            else self.session.document.can_redo
        )
        for action in self.structural_actions:
            action.setEnabled(not self.code_active and self.pages.currentIndex() == 0)
        self.source.viewport().update()

    def perform(self, callback):
        try:
            callback()
            self.refresh_views()
        except (ValueError, SyntaxError, OSError, ImportError) as error:
            self.error(str(error))

    def append_output(self, text):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()
        if not self.console_dock.isVisible() and text:
            self.unread += max(1, text.count("\n"))
            self.console_button.setText(f"Консоль · {self.unread}")

    def console_visibility(self, visible):
        if visible and hasattr(self, "console_button"):
            self.unread = 0
            self.console_button.setText("Консоль")

    def error(self, message):
        self.statusBar().showMessage(message, 15000)
        self.append_output(message + "\n")
        self.console_dock.show()
        self.controls.armed.setChecked(False)

    def _dialog(self, title, apply, **kwargs):
        dialog = EditDialog(self, title, apply, **kwargs)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_views()

    def insert_selected(self, *_):
        item = self.library.currentItem()
        if item and item.data(0, IDENTITY):
            self.insert_snippet(item.data(0, IDENTITY))

    def insert_snippet(self, identity, target=None):
        snippet = next(
            s
            for s in self.session.snippets
            if s.identity == identity and not s.historical
        )
        offset = self.session.document.syntax.spans[self.session.editor.selection].start
        self._dialog(
            snippet.help.splitlines()[0] if snippet.help else identity,
            lambda values: self.session.insert_snippet(snippet, values, target),
            snippet=snippet,
            names=self.session.analysis.available(offset),
        )

    def edit_python(self):
        self._dialog(
            "Редактировать фрагмент Python",
            self.session.edit_python,
            text=self.session.selected_text(),
        )

    def edit_parameters(self):
        match = self.session.selected_match()
        if match is None:
            raise ValueError(
                "Выберите блок из библиотеки или распознанный блок программы"
            )
        self._dialog(
            (
                match.snippet.help.splitlines()[0]
                if match.snippet.help
                else match.snippet.identity
            ),
            self.session.edit_parameters,
            snippet=match.snippet,
            bindings=match.bindings,
            names=self.session.analysis.available(match.span.start),
        )

    def to_scratch(self):
        self.session.to_scratch()
        self.scratch_dock.show()

    def new_scratch(self):
        self._dialog(
            "Новый черновик", lambda text: self.session.set_scratch(None, text), text=""
        )

    def edit_scratch(self, *_):
        index = self.scratch.currentRow()
        if index >= 0:
            self._dialog(
                "Черновик",
                lambda text: self.session.set_scratch(index, text),
                text=self.session.document.state.scratch[index],
            )

    def restore_scratch(self):
        index = self.scratch.currentRow()
        if index >= 0:
            self.perform(lambda: self.session.restore_scratch(index))

    def show_help(self):
        item = self.library.currentItem() if self.library.hasFocus() else None
        identity = item.data(0, IDENTITY) if item else None
        match = self.session.selected_match()
        self.help_page.show_page(
            identity or (match.snippet.identity if match else "tutorial/first.md")
        )
        self.set_mode(2)

    def show_diagnostics(self):
        self.commit_code()
        diagnostics = self.session.analysis.diagnostics()
        for diagnostic in diagnostics:
            line, column = self.session.document.syntax.position(diagnostic.span.start)
            self.append_output(f"{line}:{column}: {diagnostic.message}\n")
        if not diagnostics:
            self.append_output("Неизвестных имён не найдено.\n")
        self.console_dock.show()

    def show_find(self):
        self.set_mode(0)
        self.find_bar.show()
        self.find_bar.setFocus()
        self.find_bar.selectAll()

    def find_next(self):
        editor = self.code if self.code_active else self.source
        if not editor.find(self.find_bar.text()):
            editor.moveCursor(QTextCursor.MoveOperation.Start)
            editor.find(self.find_bar.text())
        if not self.code_active:
            self.session.editor.select(
                source_offset(
                    editor.toPlainText(), editor.textCursor().selectionStart()
                )
            )
            self.refresh_status()

    def set_intensity(self, value):
        self.source.intensity = value / 100
        self.source.viewport().update()

    def navigate(self, step):
        editor = self.session.editor
        editor.navigate_move(step) if editor.moving else editor.sibling(step)

    def undo(self):
        self.code.undo() if self.code_active else self.session.editor.undo()

    def redo(self):
        self.code.redo() if self.code_active else self.session.editor.redo()

    def save(self):
        self.commit_code()
        self.session.project.save()

    def _open_window(self, path):
        window = Studio(path)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.child_windows.append(window)
        window.destroyed.connect(lambda: self.child_windows.remove(window))
        window.show()

    def new_file(self):
        path = self.session.project.path.parent / "untitled.py"
        index = 1
        while path.exists():
            path = path.with_name(f"untitled_{index}.py")
            index += 1
        self._open_window(path)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть Python",
            str(self.session.project.path.parent),
            "Python (*.py)",
        )
        if path:
            self._open_window(Path(path))

    def save_as(self):
        self.commit_code()
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить Python", str(self.session.project.path), "Python (*.py)"
        )
        if path:
            from pyblocks.core.project import Project

            project = Project(Path(path), allow_draft=True)
            project.document = self.session.document
            project.draft = None
            project.collections = self.session.project.collections
            project.pins = self.session.project.pins
            project.save()
            self.session.project = project

    def _robot(self):
        if self.robot is None:
            from .robot import Robot

            self.robot = Robot(self)
            self.robot.output.connect(self.append_output)
            self.robot.failed.connect(self.error)
            self.robot.updated.connect(self.update_hub)
            self.robot.busy_changed.connect(self.hub_busy)
        return self.robot

    def hub_busy(self, busy):
        self.hub_is_busy = busy
        self.hub_button.setEnabled(not busy)
        self.run_action.setEnabled(self.hub_info.connected and not busy)
        if busy:
            self.hub_button.setText("Подождите…")
        else:
            self.update_hub(self.hub_info)

    def update_hub(self, info):
        if info.error and info.error != self.hub_info.error:
            self.error(info.error)
        self.hub_info = info
        self.hub_button.setText(
            "Подождите…"
            if self.hub_is_busy
            else ("● " + info.name) if info.connected else "＋ Подключить хаб"
        )
        self.hub_button.setToolTip(
            "Информация о хабе и показания портов"
            if info.connected
            else "Bluetooth, USB или виртуальный хаб"
        )
        self.run_action.setEnabled(info.connected and not self.hub_is_busy)
        self.stop_action.setEnabled(info.connected)
        self.device_panel.update_info(info)
        self.controls.update_info(info)

    def connect_hub(self):
        dialog = ConnectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._robot().connect_hub(
                dialog.name.text() or None,
                dialog.transport.currentData(),
                dialog.model.currentData(),
            )
            self.device_dock.show()

    def run_hub(self):
        self.controls.armed.setChecked(False)
        self.save()
        self._robot().run_file(self.session.project.path)

    def stop_hub(self):
        self.controls.armed.setChecked(False)
        self._robot().stop_program()

    def start_monitor(self):
        self.controls.armed.setChecked(False)
        self._robot().start_monitor()
        self.device_dock.show()

    def disconnect_hub(self):
        self.controls.armed.setChecked(False)
        if self.robot:
            self.robot.disconnect_hub()

    def show_controls(self):
        self.set_mode(1)

    def application_state(self, state):
        if state != Qt.ApplicationState.ApplicationActive:
            self.controls.armed.setChecked(False)
            self.controls.controller.display(ControlState())

    def closeEvent(self, event):
        if self.session.project.dirty or self.draft_dirty:
            result = QMessageBox.question(
                self,
                "Несохранённые изменения",
                "Сохранить программу перед закрытием?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if result == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if result == QMessageBox.StandardButton.Save:
                try:
                    self.save()
                except (ValueError, SyntaxError, OSError) as error:
                    self.error(str(error))
                    event.ignore()
                    return
        self.controls.close()
        if self.robot:
            self.robot.close()
        event.accept()


def launch(path: Path, collections=()) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = Studio(path, collections)
    window.show()
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(description="PyBlocks desktop editor")
    parser.add_argument("file", type=Path, nargs="?", default=Path("main.py"))
    return launch(parser.parse_args().file)
