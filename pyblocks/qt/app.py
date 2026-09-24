"""Desktop workspaces with independent source documents and one hub connection."""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pyblocks.core.edit import target_position
from pyblocks.core.parameters import default_bindings
from pyblocks.core.snippets import LEVELS
from pyblocks.core.transfer import Transfer
from pyblocks.i18n import DEFAULT_LANGUAGE, LANGUAGES, N_, language, set_language, tr
from pyblocks.pybricks.control import ControlState
from pyblocks.pybricks.devices import HubInfo

from .controls import ControlsPage
from .device import ConnectDialog, DevicePanel
from .dialogs import EditDialog
from .document import DocumentPage
from .editor import source_offset
from .help import HelpPage
from .library import IDENTITY, LEVEL_TITLES, Library
from .localization import localize, translate_standard_dialogs
from .navigation import ModeTabs
from .scratch import ScratchPane
from .window import TitleBar, resize_edges


class Studio(QMainWindow):
    def __init__(self, path: Path, collections=()):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.settings = QSettings("PyBlocks", "Studio")
        self.setMouseTracking(True)
        self.scratch_visible = True
        self.collections = collections
        self.resize(1380, 880)
        self.setMinimumSize(930, 620)
        self.robot = None
        self.hub_info = HubInfo()
        self.hub_is_busy = False
        self.unread = 0
        self.setStyleSheet("""
            QMainWindow { background: #f3f6fa; }
            QToolBar { border: 0; spacing: 5px; padding: 5px; background: #f3f6fa; }
            QToolButton { padding: 5px 8px; border-radius: 6px; }
            QToolButton:hover { background: #dfe8f2; }
            QToolButton:checked { background: transparent; border-bottom: 2px solid #303944; border-radius: 0; }
            QTabBar::tab { background: transparent; padding: 7px 13px; border: 0; }
            QTabBar::tab:selected { border-bottom: 2px solid #303944; }
            QDockWidget { font-weight: bold; }
            QLineEdit { padding: 6px; border: 1px solid #c5d0dc; border-radius: 5px; }
            QTreeWidget, QListWidget { background: #f8fafc; border: 0; }
            QPushButton { padding: 6px 10px; }
            QStatusBar { background: #e8eef5; }
        """)
        self.documents = QTabWidget()
        self.documents.setDocumentMode(True)
        self.documents.setTabsClosable(True)
        self.documents.setMovable(True)
        self.open_document(path)
        self.library = Library(self.session.snippets)
        self.library.itemDoubleClicked.connect(self.insert_selected)
        self.search = QLineEdit()
        self.search.setPlaceholderText(N_("Find a block…"))
        self.search.textChanged.connect(self.library.filter)
        self.level_filter = QComboBox()
        self.level_filter.setToolTip(N_("Block level"))
        self.level_filter.addItem(N_("All"), "all")
        for level in LEVELS:
            self.level_filter.addItem(LEVEL_TITLES[level], level)
        saved_level = self.settings.value("blockLevel", "all")
        self.level_filter.setCurrentIndex(
            max(0, self.level_filter.findData(saved_level))
        )
        self.level_filter.currentIndexChanged.connect(self.filter_level)
        library = QWidget()
        layout = QVBoxLayout(library)
        layout.addWidget(QLabel(N_("Library · drag a block into the program")))
        layout.addWidget(self.search)
        layout.addWidget(self.level_filter)
        layout.addWidget(self.library, 1)
        insert = QPushButton(N_("＋ Add selected block"))
        insert.clicked.connect(self.insert_selected)
        layout.addWidget(insert)
        self.library_pane = library
        self.program_page = QSplitter()
        self.program_page.addWidget(library)
        self.program_page.addWidget(self.documents)
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
        self.mode_tabs = ModeTabs()
        self.mode_tabs.currentChanged.connect(self.set_mode)
        workspace = QWidget()
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(4)
        workspace_layout.addWidget(self.mode_tabs, 0, Qt.AlignmentFlag.AlignTop)
        workspace_layout.addWidget(self.pages, 1)
        self.setCentralWidget(workspace)
        self._docks()
        self._menus()
        menu = self.menuBar()
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        self.title_bar = TitleBar(self)
        header_layout.addWidget(self.title_bar)
        header_layout.addWidget(menu)
        self.setMenuWidget(header)
        self.documents.currentChanged.connect(self.document_changed)
        self.documents.tabCloseRequested.connect(self.close_document)
        self.refresh_views()
        self.update_hub(HubInfo())
        self.document_mode_changed()
        self.retranslate()
        QApplication.instance().applicationStateChanged.connect(self.application_state)
        QApplication.instance().focusChanged.connect(self.focus_changed)

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
        action.setToolTip(label)
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
        row.addWidget(QLabel(N_("Program output and messages")))
        row.addStretch()
        clear = QPushButton(N_("Clear"))
        clear.clicked.connect(self.console.clear)
        row.addWidget(clear)
        layout.addLayout(row)
        layout.addWidget(self.console)
        self.console_dock = self.dock(
            N_("Console"), console_page, Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.console_dock.visibilityChanged.connect(self.console_visibility)
        self.console_dock.hide()
        self.scratch = ScratchPane()
        self.scratch.changed.connect(self.refresh_views)
        self.scratch.failed.connect(self.error)
        self.scratch_dock = self.dock(
            N_("Scratch"), self.scratch, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.resizeDocks([self.scratch_dock], [300], Qt.Orientation.Horizontal)
        self.scratch_dock.visibilityChanged.connect(self.scratch_visibility)
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
            N_("Hub and devices"), scroll, Qt.DockWidgetArea.RightDockWidgetArea
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
        toolbar = self.addToolBar(N_("Program"))
        toolbar.setObjectName("programTools")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(23, 23))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        file = self.menuBar().addMenu(N_("File"))
        self._action(
            file,
            N_("New"),
            "Ctrl+N",
            self.new_file,
            toolbar,
            ("document-new", "SP_FileIcon"),
        )
        self._action(
            file,
            N_("Open"),
            "Ctrl+O",
            self.open_file,
            toolbar,
            ("document-open", "SP_DirOpenIcon"),
        )
        self.recent_menu = file.addMenu(N_("Open recent"))
        self.recent_menu.aboutToShow.connect(self.refresh_recent_files)
        self._action(
            file,
            N_("Save"),
            "Ctrl+S",
            self.save,
            toolbar,
            ("document-save", "SP_DialogSaveButton"),
        )
        self._action(file, N_("Save as…"), "Ctrl+Shift+S", self.save_as)
        self._action(
            file,
            N_("Close document"),
            "Ctrl+W",
            lambda: self.close_document(self.documents.currentIndex()),
        )
        toolbar.addSeparator()
        edit = self.menuBar().addMenu(N_("Edit"))
        self.undo_action = self._action(
            edit,
            N_("Undo"),
            "Ctrl+Z",
            self.undo,
            toolbar,
            ("edit-undo", "SP_ArrowBack"),
        )
        self.redo_action = self._action(
            edit,
            N_("Redo"),
            "Ctrl+Shift+Z",
            self.redo,
            toolbar,
            ("edit-redo", "SP_ArrowForward"),
        )
        toolbar.addSeparator()
        self.structural_actions = []
        for label, key, callback, icon in (
            (
                N_("Parameters"),
                "F3",
                self.edit_parameters,
                ("document-properties", "SP_FileDialogDetailedView"),
            ),
            (
                N_("Python fragment"),
                "F2",
                self.edit_python,
                ("accessories-text-editor", "SP_FileDialogContentsView"),
            ),
            (
                N_("To Scratch"),
                "Ctrl+X",
                self.to_scratch,
                ("edit-cut", "SP_ArrowRight"),
            ),
        ):
            self.structural_actions.append(
                self._action(edit, label, key, callback, icon=icon)
            )
        for label, key, callback in (
            (N_("Parent"), "Alt+Left", lambda: self.editing_session.editor.parent()),
            (N_("Child"), "Alt+Right", lambda: self.editing_session.editor.child()),
            (N_("Previous node / target"), "Alt+Up", lambda: self.navigate(-1)),
            (N_("Next node / target"), "Alt+Down", lambda: self.navigate(1)),
            (
                N_("Expand block"),
                "Ctrl+E",
                lambda: self.editing_session.toggle_expansion(),
            ),
            (N_("Start move"), "Ctrl+M", lambda: self.editing_session.begin_move()),
            (
                N_("Outdent"),
                "Ctrl+Alt+Left",
                lambda: self.editing_session.editor.navigate_move(depth=-1),
            ),
            (
                N_("Indent"),
                "Ctrl+Alt+Right",
                lambda: self.editing_session.editor.navigate_move(depth=1),
            ),
            (
                N_("Finish move"),
                "Ctrl+Return",
                lambda: self.editing_session.editor.commit_move(),
            ),
            (
                N_("Cancel move"),
                "Escape",
                lambda: self.editing_source.cancel_pointer_move(),
            ),
            (
                N_("Upgrade block"),
                "Ctrl+U",
                lambda: self.editing_session.upgrade_selected(),
            ),
            (
                N_("Fold region"),
                "Ctrl+Shift+F",
                lambda: self.editing_source.fold_selection(),
            ),
        ):
            self.structural_actions.append(self._action(edit, label, key, callback))
        self._action(edit, N_("Format Python"), "Ctrl+Alt+L", self.commit_code)
        self._action(edit, N_("Find"), "Ctrl+F", self.show_find)
        view = self.menuBar().addMenu(N_("View"))
        group = QActionGroup(self)
        self.editor_actions = []
        for index, label in enumerate((N_("Blocks"), "Python")):
            action = self._action(
                view,
                label,
                f"Ctrl+Alt+{index+1}",
                lambda mode=index: self.change_editor(mode),
            )
            action.setCheckable(True)
            group.addAction(action)
            self.editor_actions.append(action)
        self.editor_actions[int(self.code_active)].setChecked(True)
        view.addSeparator()
        languages = view.addMenu(N_("Language"))
        self.language_actions = {}
        group = QActionGroup(self)
        for code, name in LANGUAGES.items():
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(code == language())
            action.triggered.connect(
                lambda checked, value=code: self.change_language(value)
            )
            group.addAction(action)
            languages.addAction(action)
            self.language_actions[code] = action
        view.addAction(self.console_dock.toggleViewAction())
        view.addAction(self.scratch_dock.toggleViewAction())
        view.addAction(self.device_dock.toggleViewAction())
        self._action(
            view,
            N_("Full screen"),
            "F11",
            lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen(),
        )
        self._action(view, N_("Help"), "F1", self.show_help)
        self._action(view, N_("Name diagnostics"), None, self.show_diagnostics)
        toolbar.addSeparator()
        robot = self.menuBar().addMenu(N_("Hub"))
        self.upload_action = self._action(
            robot,
            N_("Upload"),
            "Shift+F5",
            self.upload_hub,
            toolbar,
            ("document-send", "SP_ArrowUp"),
        )
        self.run_action = self._action(
            robot,
            N_("Run"),
            "F5",
            self.run_hub,
            toolbar,
            ("media-playback-start", "SP_MediaPlay"),
        )
        self.stop_action = self._action(
            robot,
            N_("Stop"),
            "F6",
            self.stop_hub,
            toolbar,
            ("media-playback-stop", "SP_MediaStop"),
        )
        self._action(robot, N_("Connect…"), "F7", self.connect_hub)
        self._action(robot, N_("Disconnect"), None, self.disconnect_hub)
        self._action(robot, N_("Manual control"), None, self.show_controls)
        self.stored_action = self._action(
            robot, N_("Run stored program"), None, self.run_stored_hub
        )
        robot.addSeparator()
        self.firmware_action = self._action(
            robot, N_("Firmware…"), None, self.show_firmware
        )
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
        self.console_button.setText(N_("Console"))
        self.console_button.clicked.connect(
            lambda: self.console_dock.setVisible(not self.console_dock.isVisible())
        )
        self.statusBar().addPermanentWidget(self.console_button)
        scratch_button = self.scratch_button = QToolButton()
        scratch_button.setText(N_("Scratch"))
        scratch_button.clicked.connect(
            lambda: self.scratch_dock.setVisible(not self.scratch_dock.isVisible())
        )
        self.statusBar().addPermanentWidget(scratch_button)
        self.statusBar().addPermanentWidget(QLabel(N_("Block color")))
        intensity = QSlider(Qt.Orientation.Horizontal)
        intensity.setRange(0, 100)
        intensity.setValue(65)
        intensity.setFixedWidth(90)
        intensity.valueChanged.connect(self.set_intensity)
        self.statusBar().addPermanentWidget(intensity)

    @property
    def document_page(self):
        return self.documents.currentWidget()

    @property
    def session(self):
        return self.document_page.session

    @property
    def source(self):
        return self.document_page.source

    @property
    def code(self):
        return self.document_page.code

    @property
    def code_active(self):
        return self.document_page.code_active

    @property
    def find_bar(self):
        return self.document_page.find_bar

    @property
    def draft_dirty(self):
        return self.document_page.draft_dirty

    @property
    def editing_source(self):
        cell = self.scratch.focused_cell()
        return cell.source if cell is not None and not cell.code_active else self.source

    @property
    def editing_session(self):
        return self.editing_source.session

    def change_editor(self, index):
        self.document_page.change_mode(index)

    def filter_level(self):
        level = self.level_filter.currentData()
        self.settings.setValue("blockLevel", level)
        self.library.filter(self.search.text(), level)

    def commit_code(self):
        self.document_page.commit_code()

    def document_changed(self, *_):
        if self.document_page is None:
            return
        self.library.load(self.session.snippets)
        self.library.filter(self.search.text(), self.level_filter.currentData())
        self.help_page.snippets = self.session.snippets
        self.help_page.retranslate()
        self.document_mode_changed()
        self.refresh_views()

    def change_language(self, code):
        set_language(code)
        QSettings("PyBlocks", "Studio").setValue("language", code)
        for window in QApplication.topLevelWidgets():
            if isinstance(window, Studio):
                window.retranslate()

    def retranslate(self):
        translate_standard_dialogs()
        localize(self)
        self.title_bar.update_state()
        for index in range(self.documents.count()):
            self.documents.widget(index).update_mode()
            self.documents.widget(index).source.refresh_source()
        self.scratch.refresh(self.session)
        self.language_actions[language()].setChecked(True)
        self.library.load(self.session.snippets)
        self.library.filter(self.search.text(), self.level_filter.currentData())
        self.help_page.retranslate()
        self.update_hub(self.hub_info)
        self.refresh_status()
        self.console_button.setText(
            tr("Console · {p0}", p0=self.unread) if self.unread else tr("Console")
        )

    def document_mode_changed(self):
        if not hasattr(self, "library_pane"):
            return
        self.library_pane.setVisible(not self.code_active)
        self.editor_actions[int(self.code_active)].setChecked(True)
        self.refresh_status()

    def open_document(self, path):
        path = Path(path).resolve()
        for index in range(self.documents.count()):
            if self.documents.widget(index).session.project.path == path:
                self.documents.setCurrentIndex(index)
                self.remember_file(path)
                return self.documents.widget(index)
        page = DocumentPage(path, self.collections)
        page.changed.connect(self.refresh_views)
        page.failed.connect(self.error)
        page.snippet_dropped.connect(self.insert_snippet)
        page.mode_changed.connect(self.document_mode_changed)
        page.find_bar.returnPressed.connect(self.find_next)
        index = self.documents.addTab(page, path.name)
        self.documents.setTabToolTip(index, str(path))
        self.documents.setCurrentIndex(index)
        localize(page)
        self.remember_file(path)
        return page

    def remember_file(self, path):
        if path.is_file():
            recent = self.settings.value("recentFiles", [])
            recent = [recent] if isinstance(recent, str) else recent
            self.settings.setValue(
                "recentFiles", [str(path), *(p for p in recent if p != str(path))][:10]
            )

    def refresh_recent_files(self):
        self.recent_menu.clear()
        recent = self.settings.value("recentFiles", [])
        recent = [recent] if isinstance(recent, str) else recent
        if not recent:
            self.recent_menu.addAction(tr("No recent files")).setEnabled(False)
            return
        for index, path in enumerate(recent, 1):
            action = self.recent_menu.addAction(f'&{index}  {path.replace("&", "&&")}')
            action.setToolTip(path)
            action.setData(path)
            action.setEnabled(Path(path).is_file())
            action.triggered.connect(
                lambda checked=False, value=path: self.perform(
                    lambda: self.open_recent(value)
                )
            )
            action.setProperty("translationSources", {})
        self.recent_menu.addSeparator()
        self.recent_menu.addAction(
            tr("Clear recent files"), lambda: self.settings.remove("recentFiles")
        )

    def open_recent(self, path):
        if not Path(path).is_file():
            raise FileNotFoundError(path)
        self.open_document(path)
        self.set_mode(0)

    def mousePressEvent(self, event):
        edges = resize_edges(self, event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and edges:
            self.windowHandle().startSystemResize(edges)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        edges = resize_edges(self, event.position().toPoint())
        if edges in (
            Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
            Qt.Edge.RightEdge | Qt.Edge.BottomEdge,
        ):
            cursor = Qt.CursorShape.SizeFDiagCursor
        elif edges in (
            Qt.Edge.RightEdge | Qt.Edge.TopEdge,
            Qt.Edge.LeftEdge | Qt.Edge.BottomEdge,
        ):
            cursor = Qt.CursorShape.SizeBDiagCursor
        elif edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            cursor = Qt.CursorShape.SizeHorCursor
        elif edges:
            cursor = Qt.CursorShape.SizeVerCursor
        else:
            cursor = Qt.CursorShape.ArrowCursor
        self.setCursor(cursor)
        super().mouseMoveEvent(event)

    def confirm_close(self, page):
        if not page.dirty:
            return True
        result = QMessageBox.question(
            self,
            tr("Unsaved changes"),
            tr("Save {p0} before closing?", p0=page.session.project.path.name),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if result == QMessageBox.StandardButton.Cancel:
            return False
        if result == QMessageBox.StandardButton.Save:
            try:
                page.commit_code()
                page.session.project.save()
                self.remember_file(page.session.project.path)
            except (ValueError, SyntaxError, OSError) as error:
                self.documents.setCurrentWidget(page)
                self.error(str(error))
                return False
        return True

    def close_document(self, index):
        page = self.documents.widget(index)
        if not self.confirm_close(page):
            return
        if self.documents.count() == 1:
            self.new_file()
        self.documents.removeTab(self.documents.indexOf(page))
        page.deleteLater()

    def scratch_visibility(self, visible):
        if self.pages.currentIndex() == 0:
            self.scratch_visible = visible

    def set_mode(self, index):
        self.pages.setCurrentIndex(index)
        self.mode_tabs.setCurrentIndex(index)
        self.scratch_dock.setVisible(index == 0 and self.scratch_visible)
        self.scratch_dock.toggleViewAction().setEnabled(index == 0)
        self.scratch_button.setEnabled(index == 0)
        if index == 1:
            self.device_dock.show()
        elif index == 2:
            self.device_dock.hide()
        self.refresh_status()

    def refresh_views(self):
        if not hasattr(self, "scratch") or self.document_page is None:
            return
        self.source.refresh_source()
        self.scratch.refresh(self.session)
        self.refresh_status()

    def focus_changed(self, old, new):
        if hasattr(self, "undo_action"):
            self.refresh_status()

    def text_editor(self):
        cell = self.scratch.focused_cell()
        if cell is not None:
            return cell.code if cell.code_active else None
        return self.code if self.code_active else None

    def refresh_status(self):
        if not hasattr(self, "undo_action"):
            return
        match = self.session.selected_match()
        selection = (
            tr(match.snippet.help).splitlines()[0]
            if match and match.snippet.help
            else "Python" if self.code_active else tr("Select a block")
        )
        self.statusBar().showMessage(
            tr(
                "{p0} · warnings: {p1}",
                p0=selection,
                p1=len(self.session.analysis.diagnostics()),
            )
        )
        self.setWindowTitle(
            f'{"● " if self.document_page.dirty else ""}{self.session.project.path.name} — PyBlocks Studio'
        )
        text_editor = self.text_editor()
        self.undo_action.setEnabled(
            text_editor.document().isUndoAvailable()
            if text_editor
            else self.session.document.can_undo
        )
        self.redo_action.setEnabled(
            text_editor.document().isRedoAvailable()
            if text_editor
            else self.session.document.can_redo
        )
        for action in self.structural_actions:
            action.setEnabled(text_editor is None and self.pages.currentIndex() == 0)
        for index in range(self.documents.count()):
            page = self.documents.widget(index)
            self.documents.setTabText(
                index, ("● " if page.dirty else "") + page.session.project.path.name
            )
            self.documents.setTabToolTip(index, str(page.session.project.path))
        self.source.viewport().update()

    def perform(self, callback):
        cell = self.scratch.focused_cell()
        revision = cell.source.session.document.state if cell is not None else None
        try:
            callback()
            if (
                cell is not None
                and cell in self.scratch.cells
                and not cell.code_active
                and cell.source.session.document.state is not revision
            ):
                cell.structural_changed()
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
            self.console_button.setText(tr("Console · {p0}", p0=self.unread))

    def console_visibility(self, visible):
        if visible and hasattr(self, "console_button"):
            self.unread = 0
            self.console_button.setText(tr("Console"))

    def error(self, message):
        self.statusBar().showMessage(message, 15000)
        self.append_output(message + "\n")
        self.console_dock.show()
        self.controls.armed.setChecked(False)

    def _dialog(self, title, apply, **kwargs):
        dialog = EditDialog(self, tr(title), apply, **kwargs)
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
        syntax = self.session.document.syntax
        offset = (
            target_position(syntax, target)[0]
            if target
            else syntax.spans[self.session.editor.selection].start
        )
        try:
            self.session.insert_snippet(
                snippet, default_bindings(self.session, snippet, offset), target
            )
            self.refresh_views()
            self.source.reveal(
                self.session.document.syntax.spans[self.session.editor.selection].start
            )
        except (ValueError, SyntaxError, OSError) as error:
            self.error(str(error))

    def edit_python(self):
        cell = self.scratch.focused_cell()
        if cell is not None:
            cell.change_mode(True)
            return
        self._dialog(
            N_("Edit Python fragment"),
            self.session.edit_python,
            text=self.session.selected_text(),
        )

    def edit_parameters(self):
        self.editing_source.edit_parameters()

    def to_scratch(self):
        cell = self.scratch.focused_cell()
        if cell is not None and not cell.code_active:
            transfer = Transfer.capture(
                self.session, index=cell.index, fragment=cell.source.session
            )
            transfer.to_scratch(len(self.session.document.state.scratch))
        else:
            self.session.to_scratch()
        self.scratch_dock.show()

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
            self.append_output(tr("No unknown names found.\n"))
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
        editor = self.editing_session.editor
        editor.navigate_move(step) if editor.moving else editor.sibling(step)

    def undo(self):
        editor = self.text_editor()
        editor.undo() if editor else self.session.editor.undo()

    def redo(self):
        editor = self.text_editor()
        editor.redo() if editor else self.session.editor.redo()

    def save(self):
        self.commit_code()
        self.session.project.save()
        self.remember_file(self.session.project.path)

    def new_file(self):
        parent = self.session.project.path.parent
        paths = {
            self.documents.widget(i).session.project.path
            for i in range(self.documents.count())
        }
        index = 0
        while True:
            path = parent / ("untitled.py" if index == 0 else f"untitled_{index}.py")
            if not path.exists() and path not in paths:
                break
            index += 1
        self.open_document(path)
        self.set_mode(0)

    def open_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("Open Python"),
            str(self.session.project.path.parent),
            "Python (*.py)",
        )
        for path in paths:
            self.open_document(Path(path))
        if paths:
            self.set_mode(0)

    def save_as(self):
        self.commit_code()
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save Python"),
            str(self.session.project.path),
            "Python (*.py)",
        )
        if path:
            from pyblocks.core.project import Project

            destination = Path(path).resolve()
            for index in range(self.documents.count()):
                page = self.documents.widget(index)
                if (
                    page is not self.document_page
                    and page.session.project.path == destination
                ):
                    raise ValueError(tr("This file is already open in another tab"))
            if destination == self.session.project.path:
                self.save()
                return
            project = Project(destination, allow_draft=True)
            project.document = self.session.document
            project.draft = None
            project.collections = self.session.project.collections
            project.pins = self.session.project.pins
            project.save()
            self.session.project = project
            self.remember_file(destination)

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
        self.upload_action.setEnabled(self.hub_info.connected and not busy)
        self.stored_action.setEnabled(self.hub_info.connected and not busy)
        self.firmware_action.setEnabled(not busy)
        if busy:
            self.hub_button.setText(tr("Please wait…"))
        else:
            self.update_hub(self.hub_info)

    def update_hub(self, info):
        if info.error and info.error != self.hub_info.error:
            self.error(info.error)
        self.hub_info = info
        self.hub_button.setText(
            tr("Please wait…")
            if self.hub_is_busy
            else (
                (
                    "● "
                    + (tr("Virtual hub") if info.transport == "virtual" else info.name)
                )
                if info.connected
                else tr("＋ Connect hub")
            )
        )
        self.hub_button.setToolTip(
            tr("Hub information and port readings")
            if info.connected
            else tr("Bluetooth, USB or virtual hub")
        )
        self.run_action.setEnabled(info.connected and not self.hub_is_busy)
        self.upload_action.setEnabled(info.connected and not self.hub_is_busy)
        self.stored_action.setEnabled(info.connected and not self.hub_is_busy)
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

    def upload_hub(self):
        self.controls.armed.setChecked(False)
        self.save()
        self._robot().upload_file(self.session.project.path)

    def run_stored_hub(self):
        self.controls.armed.setChecked(False)
        self._robot().run_stored()

    def show_firmware(self):
        from .firmware import FirmwareDialog

        dialog = FirmwareDialog(self)
        dialog.exec()

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
        for index in range(self.documents.count()):
            if not self.confirm_close(self.documents.widget(index)):
                event.ignore()
                return
        self.controls.close()
        if self.robot:
            self.robot.close()
        event.accept()


def launch(path: Path, collections=()) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    code = QSettings("PyBlocks", "Studio").value("language", DEFAULT_LANGUAGE)
    set_language(code if code in LANGUAGES else DEFAULT_LANGUAGE)
    window = Studio(path, collections)
    window.show()
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(description="PyBlocks desktop editor")
    parser.add_argument("file", type=Path, nargs="?", default=Path("main.py"))
    return launch(parser.parse_args().file)
