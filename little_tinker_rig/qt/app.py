"""Desktop workspaces with independent source documents and one hub connection."""

import argparse
import ast
import re
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.core.authoring import template_from_source, user_collection
from little_tinker_rig.core.edit import target_position
from little_tinker_rig.core.expressions import navigate as navigate_expression
from little_tinker_rig.core.lessons import localized
from little_tinker_rig.core.parameters import default_bindings
from little_tinker_rig.core.snippets import LEVELS, load_collection
from little_tinker_rig.core.transfer import Transfer
from little_tinker_rig.examples import examples_directory
from little_tinker_rig.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    N_,
    language,
    set_language,
    tr,
)
from little_tinker_rig.pybricks.control import ControlState
from little_tinker_rig.pybricks.devices import HubInfo

from .authoring import BlockEditor
from .console import HubInput, capture_output
from .controls import ControlsPage
from .device import ConnectDialog, DevicePanel
from .dialogs import EditDialog
from .document import DocumentPage
from .editor import source_offset
from .help import HelpPage
from .lessons import Lessons
from .library import IDENTITY, LEVEL_TITLES, REFERENCE, VIEW_TITLES, Library
from .localization import localize, translate_standard_dialogs
from .navigation import ChoiceButtons, ModeList
from .recovery import Recovery
from .runtime import RuntimePanel
from .scratch import ScratchPane
from .window import TitleBar, resize_edges


def application_settings():
    settings = QSettings("LittleTinker", "Rig")
    if not settings.allKeys():
        previous = QSettings("PyBlocks", "Studio")
        for key in previous.allKeys():
            settings.setValue(key, previous.value(key))
    return settings


class Studio(QMainWindow):
    def __init__(self, path: Path | None = None, collections=()):
        super().__init__()
        lesson_path = (
            path if path and path.suffix in {".ltr", ".pylesson", ".pyblocks"} else None
        )
        if lesson_path:
            path = None
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.settings = application_settings()
        self.setMouseTracking(True)
        self.scratch_visible = True
        self.collections = collections
        available = self.screen().availableGeometry().size()
        self.setMinimumSize(QSize(930, 620).boundedTo(available))
        self.resize(QSize(1380, 880).boundedTo(available))
        self.robot = None
        self.hub_info = HubInfo()
        self.hub_is_busy = False
        self.unread = 0
        self.setStyleSheet("""
            QMainWindow { background: #f3f6fa; }
            QToolBar { border: 0; spacing: 5px; padding: 2px; background: #f3f6fa; }
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
        self.open_document(path or self.new_document_path(), unnamed=path is None)
        self.library = Library(self.session.available_snippets, self.settings)
        self.library.set_scope(self.session.project.path)
        self.library.definition_requested.connect(self.open_definition)
        self.library.itemDoubleClicked.connect(self.insert_selected)
        self.search = QLineEdit()
        self.search.setPlaceholderText(N_("Find a block…"))
        self.search.textChanged.connect(self.library.filter)
        self.level_filter = ChoiceButtons({**LEVEL_TITLES, "all": N_("All")}, columns=2)
        self.level_filter.setAccessibleName(N_("Block level"))
        saved_level = self.settings.value("blockLevel", "beginner")
        if saved_level == "standard":
            saved_level = "intermediate"
            self.settings.setValue("blockLevel", saved_level)
        self.level_filter.select(
            saved_level if saved_level in (*LEVELS, "all") else "beginner"
        )
        self.block_level = self.level_filter.value
        self.level_filter.changed.connect(self.filter_level)
        self.view_filter = ChoiceButtons(VIEW_TITLES)
        self.view_filter.setAccessibleName(N_("Library view"))
        self.view_filter.changed.connect(self.library.set_view)
        self.view_filter.changed.connect(
            lambda value: self.settings.setValue("blockView", value)
        )
        library = QWidget()
        layout = QVBoxLayout(library)
        layout.addWidget(QLabel(N_("Library · drag a block into the program")))
        layout.addWidget(self.search)
        layout.addWidget(self.level_filter)
        layout.addWidget(self.view_filter)
        self.library_status = QLabel()
        self.library_status.setWordWrap(True)
        self.library_status.setProperty("translationSources", {})
        self.library.status_changed.connect(self.library_status.setText)
        self.library.status_changed.connect(
            lambda text: self.library_status.setVisible(bool(text))
        )
        layout.addWidget(self.library_status)
        self.whole_blocks = QPushButton(N_("← Back to whole blocks"))
        self.whole_blocks.setToolTip(
            N_(
                "The library is showing blocks for the selected input. Select its containing block to add the next action."
            )
        )
        self.whole_blocks.clicked.connect(
            lambda: self.editing_source.select_statement()
        )
        self.whole_blocks.hide()
        layout.addWidget(self.whole_blocks)
        layout.addWidget(self.library, 1)
        self.variant_filter = QComboBox()
        self.variant_filter.setAccessibleName(N_("Variant"))
        self.variant_filter.setToolTip(N_("Variant"))
        self.variant_filter.setProperty(
            "translationSources",
            {"toolTip": N_("Variant"), "accessibleName": N_("Variant")},
        )
        self.variant_filter.currentIndexChanged.connect(
            lambda _: self.library.select_variant(self.variant_filter.currentData())
        )
        layout.addWidget(self.variant_filter)
        row = QHBoxLayout()
        self.favorite_button = QToolButton()
        self.favorite_button.setText("☆")
        self.favorite_button.setCheckable(True)
        self.favorite_button.setProperty("translationSources", {})
        self.favorite_button.clicked.connect(self.library.toggle_favorite)
        row.addWidget(self.favorite_button)
        insert = QPushButton(N_("＋ Add selected block"))
        insert.clicked.connect(self.insert_selected)
        row.addWidget(insert, 1)
        layout.addLayout(row)
        self.clear_usage = QPushButton()
        self.clear_usage.setProperty("translationSources", {})
        self.clear_usage.clicked.connect(self.library.clear_history)
        layout.addWidget(self.clear_usage)
        self.library.variants_changed.connect(self.update_library_controls)
        self.view_filter.select(self.settings.value("blockView", "catalog"))
        self.update_library_controls()
        self.library_pane = library
        self.program_page = QSplitter()
        self.program_page.addWidget(library)
        self.program_documents = QWidget()
        program_layout = QVBoxLayout(self.program_documents)
        program_layout.setContentsMargins(0, 0, 0, 0)
        program_layout.addWidget(self.documents, 1)
        self.program_page.addWidget(self.program_documents)
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
        self.help_page = HelpPage(self.session.available_snippets)
        self.help_page.definition_requested.connect(self.open_definition)
        self.block_editor = BlockEditor(
            self.ensure_user_collection, self.validate_collection
        )
        self.block_editor.saved.connect(self.collection_saved)
        self.block_editor.failed.connect(self.error)
        self.block_editor.changed.connect(self.refresh_status)
        self.pages = QStackedWidget()
        for page in (self.program_page, scroll, self.help_page, self.block_editor):
            self.pages.addWidget(page)
        self.modes = ModeList()
        self.modes.currentRowChanged.connect(self.set_mode)
        workspace = QWidget()
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(4)
        workspace_layout.addWidget(self.modes)
        self.workspace_body = QVBoxLayout()
        self.workspace_body.setContentsMargins(0, 0, 0, 0)
        self.workspace_body.addWidget(self.pages, 1)
        workspace_layout.addLayout(self.workspace_body, 1)
        self.setCentralWidget(workspace)
        self._docks()
        self._menus()
        self.lessons = Lessons(self)
        self.block_editor.configure(
            self.session.snippets, self.session.collection_paths
        )
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
        self.recovery = Recovery(self)
        self.documents.tabBar().tabMoved.connect(lambda *_: self.recovery.schedule())
        self.recovery.schedule()
        QTimer.singleShot(0, self.recovery.offer)
        if geometry := self.settings.value("windowGeometry", b""):
            self.restoreGeometry(geometry)
        if lesson_path:
            self.perform(lambda: self.lessons.open(lesson_path))

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
        self.console_return = False
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(5000)
        console_page = QWidget()
        layout = QVBoxLayout(console_page)
        row = QHBoxLayout()
        row.addWidget(QLabel(N_("Program output and messages")))
        row.addStretch()
        self.last_error = ""
        self.copy_error = QPushButton(N_("Copy error"))
        self.copy_error.clicked.connect(
            lambda: QApplication.clipboard().setText(self.last_error)
        )
        self.copy_error.hide()
        row.addWidget(self.copy_error)
        self.connection_help = QPushButton(N_("USB connection help"))
        self.connection_help.clicked.connect(self.show_usb_help)
        self.connection_help.hide()
        row.addWidget(self.connection_help)
        clear = QPushButton(N_("Clear"))
        clear.clicked.connect(self.console.clear)
        clear.clicked.connect(self.copy_error.hide)
        clear.clicked.connect(self.connection_help.hide)
        row.addWidget(clear)
        layout.addLayout(row)
        self.runtime_panel = RuntimePanel(self)
        layout.addWidget(self.runtime_panel)
        layout.addWidget(self.console)
        self.hub_input = HubInput()
        self.hub_input.sent.connect(
            lambda data: self.robot and self.robot.write_input(data)
        )
        self.hub_input.setEnabled(False)
        layout.addWidget(self.hub_input)
        self.console_dock = self.dock(
            N_("Console"), console_page, Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.console_dock.visibilityChanged.connect(self.console_visibility)
        self.console_dock.hide()
        self.scratch = ScratchPane()
        self.scratch.changed.connect(self.refresh_views)
        self.scratch.failed.connect(self.error)
        self.scratch.snippet_inserted.connect(self.library.record_use)
        self.scratch.definition_requested.connect(self.open_definition)
        self.scratch.help_requested.connect(self.open_block_help)
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
        self.tabifyDockWidget(self.scratch_dock, self.device_dock)
        self.scratch_dock.raise_()

    def dock(self, title, widget, area):
        dock = QDockWidget(title, self)
        dock.setObjectName(title)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock

    def toggle_dock(self, dock):
        if dock.isVisible() and not dock.visibleRegion().isEmpty():
            dock.hide()
        else:
            dock.show()
            dock.raise_()

    def _menus(self):
        toolbar = self.addToolBar(N_("Program"))
        toolbar.setObjectName("programTools")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        file = self.menuBar().addMenu(N_("File"))
        self.file_menu = file
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
        self.examples_menu = file.addMenu(N_("Examples"))
        self.examples_menu.aboutToShow.connect(self.refresh_examples)
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
            (
                N_("Parent"),
                "Alt+Left",
                lambda: navigate_expression(self.editing_session, "parent"),
            ),
            (
                N_("Child"),
                "Alt+Right",
                lambda: navigate_expression(self.editing_session, "child"),
            ),
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
                lambda: self.editing_source.cancel_interaction(),
            ),
            (
                N_("Upgrade block"),
                "Ctrl+U",
                self.upgrade_block,
            ),
            (
                N_("Fold region"),
                "Ctrl+Shift+F",
                lambda: self.editing_source.fold_selection(),
            ),
        ):
            self.structural_actions.append(self._action(edit, label, key, callback))
        self._action(edit, N_("Format Python"), "Ctrl+Alt+L", self.commit_code)
        self.structural_actions.append(
            self._action(edit, N_("Import module…"), None, self.import_module)
        )
        self._action(edit, N_("Find"), "Ctrl+F", self.show_find)
        self.create_block_action = self._action(
            edit,
            N_("Create block from selection"),
            None,
            self.create_block_from_selection,
        )
        self.view_menu = view = self.menuBar().addMenu(N_("View"))
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
        self._action(view, N_("Block Editor"), "Ctrl+Alt+3", lambda: self.set_mode(3))
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
        self.hub_button.clicked.connect(self.connect_hub)
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
        self.hub_progress = QProgressBar()
        self.hub_progress.setRange(0, 0)
        self.hub_progress.setFixedWidth(130)
        self.hub_progress.setToolTip(N_("Hub operation in progress"))
        self.hub_progress.hide()
        self.statusBar().addPermanentWidget(self.hub_progress)
        self.statusBar().addPermanentWidget(self.console_button)
        scratch_button = self.scratch_button = QToolButton()
        scratch_button.setText(N_("Scratch"))
        scratch_button.clicked.connect(lambda: self.toggle_dock(self.scratch_dock))
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
    def editing_source(self):
        cell = self.scratch.focused_cell()
        return cell.source if cell is not None and not cell.code_active else self.source

    @property
    def editing_session(self):
        return self.editing_source.session

    def change_editor(self, index):
        self.document_page.change_mode(index)

    def filter_level(self, *_):
        level = self.level_filter.value
        self.block_level = level
        self.settings.setValue("blockLevel", level)
        self.library.filter(self.search.text(), level)
        if hasattr(self, "scratch"):
            self.editing_source.expression_level = level
        if hasattr(self, "lessons"):
            self.lessons.palette()

    def update_library_controls(self):
        choices = self.library.current_choices()
        item = self.library.currentItem()
        self.variant_filter.blockSignals(True)
        self.variant_filter.clear()
        for snippet in choices:
            self.variant_filter.addItem(
                (
                    tr(snippet.variant)
                    if snippet.variant
                    else tr(snippet.help).splitlines()[0]
                ),
                snippet.identity,
            )
        if item:
            self.variant_filter.setCurrentIndex(
                self.variant_filter.findData(item.data(0, IDENTITY))
            )
        self.variant_filter.blockSignals(False)
        self.variant_filter.setVisible(len(choices) > 1)
        key = item.data(0, REFERENCE) if item else None
        favorite = key in self.library.history.favorites
        self.favorite_button.setEnabled(key is not None)
        self.favorite_button.setChecked(favorite)
        self.favorite_button.setText("★" if favorite else "☆")
        title = tr("Remove from Favorites") if favorite else tr("Add to Favorites")
        self.favorite_button.setToolTip(title)
        self.favorite_button.setAccessibleName(title)
        self.clear_usage.setVisible(self.library.view in ("recent", "frequent"))
        self.clear_usage.setText(
            tr("Clear recent")
            if self.library.view == "recent"
            else tr("Reset usage history")
        )

    def commit_code(self):
        if self.pages.currentIndex() == 3:
            code = self.block_editor.code
            if code and not code.isReadOnly():
                from little_tinker_rig.core.formatting import format_source

                code.replace_formatted(format_source(code.toPlainText()))
            return
        self.document_page.commit_code()

    def document_changed(self, *_):
        if self.document_page is None:
            return
        self.library.set_scope(self.session.project.path)
        self.library.load(self.session.available_snippets)
        self.library.filter(self.search.text(), self.level_filter.value)
        self.help_page.snippets = self.session.available_snippets
        self.help_page.retranslate()
        self.block_editor.configure(
            self.session.snippets, self.session.collection_paths
        )
        self.document_mode_changed()
        if hasattr(self, "lessons"):
            self.lessons.activate()
        self.refresh_views()

    def change_language(self, code):
        set_language(code)
        application_settings().setValue("language", code)
        for window in QApplication.topLevelWidgets():
            if isinstance(window, Studio):
                window.retranslate()

    def retranslate(self):
        translate_standard_dialogs()
        localize(self)
        self.level_filter.retranslate()
        self.view_filter.retranslate()
        for action in self.findChild(QToolBar, "programTools").actions():
            shortcut = action.shortcut().toString(
                QKeySequence.SequenceFormat.NativeText
            )
            action.setToolTip(action.text() + (f" ({shortcut})" if shortcut else ""))
        self.title_bar.update_state()
        for index in range(self.documents.count()):
            self.documents.widget(index).update_mode()
            self.documents.widget(index).source.refresh_source()
        self.scratch.refresh(self.session)
        self.language_actions[language()].setChecked(True)
        self.library.set_scope(self.session.project.path)
        self.library.load(self.session.available_snippets)
        self.library.filter(self.search.text(), self.level_filter.value)
        self.help_page.retranslate()
        self.block_editor.retranslate()
        self.lessons.refresh()
        self.lessons.assembly_host.retranslate()
        self.runtime_panel.retranslate()
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

    def open_document(self, path, *, unnamed=False):
        path = Path(path).resolve()
        if path.suffix in {".pylesson", ".ltr", ".pyblocks"} and hasattr(
            self, "lessons"
        ):
            return self.lessons.open(path)
        for index in range(self.documents.count()):
            if self.documents.widget(index).session.project.path == path:
                self.documents.setCurrentIndex(index)
                self.remember_file(path)
                return self.documents.widget(index)
        project = None
        if hasattr(self, "lessons"):
            project = next(
                (
                    p
                    for p in self.lessons.projects.values()
                    if path.is_relative_to(p.root / "programs")
                ),
                None,
            )
        collections = self.collections
        if project and "collection" in project.lesson.data:
            from little_tinker_rig.core.lessons import resource

            collections = (
                *collections,
                resource(project.lesson.root, project.lesson.data["collection"]),
            )
        page = DocumentPage(path, collections)
        page.lesson_project = project
        page.unnamed = unnamed
        page.changed.connect(self.refresh_views)
        page.failed.connect(self.error)
        page.snippet_dropped.connect(self.insert_snippet)
        page.definition_requested.connect(self.open_definition)
        page.help_requested.connect(self.open_block_help)
        page.mode_changed.connect(self.document_mode_changed)
        page.find_bar.returnPressed.connect(self.find_next)
        index = self.documents.addTab(page, path.name)
        self.documents.setTabToolTip(index, str(path))
        self.documents.setCurrentIndex(index)
        localize(page)
        self.remember_file(path)
        return page

    def remember_file(self, path):
        if hasattr(self, "lessons") and any(
            path.is_relative_to(p.root) for p in self.lessons.projects.values()
        ):
            return
        if path.is_file():
            recent = self.settings.value("recentFiles", [])
            recent = [recent] if isinstance(recent, str) else recent
            self.settings.setValue(
                "recentFiles", [str(path), *(p for p in recent if p != str(path))][:10]
            )

    def refresh_examples(self):
        def populate(menu, directory):
            for action in menu.actions():
                if submenu := action.menu():
                    submenu.deleteLater()
            menu.clear()
            for path in sorted(
                directory.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.casefold(), p.name),
            ):
                if (
                    path.name.startswith(".")
                    or path.name == "__pycache__"
                    or path.is_symlink()
                ):
                    continue
                if path.is_dir():
                    submenu = menu.addMenu(path.name.replace("&", "&&"))
                    populate(submenu, path)
                    if not submenu.actions():
                        menu.removeAction(submenu.menuAction())
                        submenu.deleteLater()
                elif path.suffix == ".py":
                    action = menu.addAction(path.name.replace("&", "&&"))
                    action.setData(str(path))
                    action.setToolTip(str(path))
                    action.triggered.connect(
                        lambda checked=False, p=path: self.perform(
                            lambda: self.open_recent(p)
                        )
                    )

        try:
            populate(self.examples_menu, examples_directory())
        except OSError as error:
            self.error(str(error))
        if not self.examples_menu.actions():
            self.examples_menu.addAction(tr("No examples found")).setEnabled(False)

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
        if Path(path).suffix == ".py":
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
        project = page.lesson_project
        pages = (
            [
                self.documents.widget(i)
                for i in range(self.documents.count())
                if self.documents.widget(i).lesson_project is project
            ]
            if project
            else [page]
        )
        if not any(p.dirty for p in pages) and not (project and project.dirty):
            return True
        message = (
            tr(
                "Save lesson project {name} before closing? Saving includes all open programs in this project.",
                name=(
                    project.path.name
                    if project.path
                    else localized(project.lesson.data["title"], language())
                ),
            )
            if project
            else tr("Save {p0} before closing?", p0=page.session.project.path.name)
        )
        result = QMessageBox.question(
            self,
            tr("Unsaved changes"),
            message,
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if result == QMessageBox.StandardButton.Cancel:
            return False
        if result == QMessageBox.StandardButton.Save:
            try:
                if not self.save_document(page):
                    return False
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
        if self.recovery.flush():
            self.lessons.release_unused()

    def scratch_visibility(self, visible):
        if self.pages.currentIndex() == 0:
            # An inactive dock tab emits visibilityChanged(False) without being
            # closed. Preserve the user's choice when switching tabs or modes.
            self.scratch_visible = not self.scratch_dock.isHidden()

    def set_mode(self, index):
        if index < 0 or self.modes.item(index).isHidden():
            return
        self.pages.setCurrentIndex(index)
        if self.document_page.lesson_project:
            self.document_page.lesson_project.progress["mode"] = index
            if hasattr(self, "recovery"):
                self.recovery.schedule()
        self.modes.blockSignals(True)
        self.modes.setCurrentRow(index)
        self.modes.blockSignals(False)
        if hasattr(self, "lessons"):
            self.lessons.update_card()
        self.scratch_dock.setVisible(index == 0 and self.scratch_visible)
        self.scratch_dock.toggleViewAction().setEnabled(index == 0)
        self.scratch_button.setEnabled(index == 0)
        if index in (0, 1):
            self.device_dock.show()
            if index == 1:
                self.device_dock.raise_()
        else:
            self.device_dock.hide()
        if index == 3:
            self.block_editor.configure(
                self.session.snippets, self.session.collection_paths
            )
        self.update_hub(self.hub_info)
        self.refresh_status()

    def refresh_views(self):
        if not hasattr(self, "scratch") or self.document_page is None:
            return
        self.source.refresh_source()
        if self.library.update_functions(self.session.available_snippets):
            self.help_page.snippets = self.session.available_snippets
            self.help_page.retranslate()
        self.scratch.refresh(self.session)
        self.refresh_status()
        if hasattr(self, "recovery"):
            self.recovery.schedule()

    def focus_changed(self, old, new):
        if hasattr(self, "undo_action"):
            self.refresh_status()

    def text_editor(self):
        if self.pages.currentIndex() == 3:
            return self.block_editor.code or self.block_editor.empty
        cell = self.scratch.focused_cell()
        if cell is not None:
            return cell.code if cell.code_active else None
        return self.code if self.code_active else None

    def refresh_status(self):
        if not hasattr(self, "undo_action"):
            return
        self.editing_source.expression_level = self.level_filter.value
        if hasattr(self, "lessons"):
            self.lessons.palette()
        self.library.set_scope(self.session.project.path)
        self.library.set_context(self.editing_session)
        self.whole_blocks.setVisible(
            isinstance(self.editing_session.editor.selection, ast.expr)
        )
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
        project = self.document_page.lesson_project
        dirty = self.document_page.dirty or (project is not None and project.dirty)
        name = self.session.project.path.name
        if project:
            name = (
                (project.path.name if project.path else self.lessons.title.text())
                + " · "
                + name
            )
        self.setWindowTitle(f'{"● " if dirty else ""}{name} — LittleTinker Rig')
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
        self.create_block_action.setEnabled(self.pages.currentIndex() == 0)
        for action in self.editor_actions:
            action.setEnabled(self.pages.currentIndex() != 3)
        if self.pages.currentIndex() == 3:
            self.statusBar().showMessage(self.block_editor.caption.text())
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
        # Terminal progress bars rewrite a line with carriage returns. Keep the
        # latest value, including when CR and the replacement arrive separately.
        for part in re.split(r"(\r\n|\r|\n)", text):
            if part == "\r":
                self.console_return = True
            elif part in ("\r\n", "\n"):
                self.console_return = False
                cursor.insertBlock()
            elif part:
                if self.console_return:
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                    cursor.movePosition(
                        QTextCursor.MoveOperation.EndOfBlock,
                        QTextCursor.MoveMode.KeepAnchor,
                    )
                    cursor.removeSelectedText()
                    self.console_return = False
                cursor.insertText(part)
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
        self.last_error = message
        self.copy_error.show()
        self.statusBar().showMessage(message.splitlines()[0] if message else "", 15000)
        self.append_output(message + "\n")
        self.console_dock.show()
        self.controls.armed.setChecked(False)

    def hub_error(self, message):
        self.error(message)
        self.connection_help.show()

    def show_usb_help(self):
        self.help_page.show_page("usb.md")
        self.set_mode(2)

    def upgrade_block(self):
        from difflib import unified_diff

        session = self.editing_session
        revision = session.document.state
        candidate = session.upgraded_source()
        diff = "".join(
            unified_diff(
                revision.source.splitlines(keepends=True),
                candidate.splitlines(keepends=True),
                fromfile="Current program",
                tofile="Upgraded program",
            )
        )

        def apply(_):
            if (
                session.document.state is not revision
                or session.upgraded_source() != candidate
            ):
                raise ValueError(
                    tr("Document or definitions changed; review the upgrade again")
                )
            session.editor.commit(candidate)

        dialog = EditDialog(self, tr("Review block upgrade"), apply, text=diff)
        dialog.text.setReadOnly(True)
        dialog.text.highlighter.setDocument(None)
        dialog.exec()

    def _dialog(self, title, apply, **kwargs):
        dialog = EditDialog(self, tr(title), apply, **kwargs)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_views()

    def insert_selected(self, *_):
        item = self.library.currentItem()
        if item and item.data(0, IDENTITY):
            self.insert_snippet(item.data(0, IDENTITY))

    def insert_snippet(self, identity, target=None):
        from little_tinker_rig.core.expressions import targets

        if (
            self.library.lesson_ids is not None
            and identity not in self.library.lesson_ids
        ):
            self.error(
                tr(
                    "This block is outside the current lesson palette. Enable Show all blocks to use it."
                )
            )
            return

        view = self.editing_source if target is None else self.source
        session = view.session
        snippet = next(
            (
                s
                for s in session.available_snippets
                if s.identity == identity and not s.historical
            ),
            None,
        )
        if snippet is None:
            self.error(tr("This block is no longer available."))
            return
        syntax = session.document.syntax
        if not snippet.expression and isinstance(
            getattr(session.editor.selection, "ctx", None), ast.Store
        ):
            session.editor.selection = session.editor.statement()
        if (
            target is None
            and snippet.expression
            and not isinstance(session.editor.selection, ast.expr)
        ):
            inputs = targets(session, snippet)
            if inputs:
                if len(inputs) == 1:
                    session.editor.selection = inputs[0]
                else:
                    menu = QMenu(view)
                    menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                    original = session.editor.selection

                    def restore_selection():
                        if syntax is session.document.syntax:
                            session.editor.selection = original
                            view.viewport().update()

                    menu.aboutToHide.connect(restore_selection)
                    for node in inputs:
                        span = syntax.spans[node]
                        label = syntax.text(node)
                        line, column = syntax.position(span.start)
                        action = menu.addAction(f"{line}:{column + 1} · {label[:60]}")

                        def choose(checked=False, node=node):
                            if syntax is session.document.syntax:
                                session.editor.selection = node
                                self.insert_snippet(identity)

                        action.triggered.connect(choose)
                        action.hovered.connect(
                            lambda node=node: (
                                setattr(session.editor, "selection", node),
                                view.viewport().update(),
                            )
                        )
                    menu.popup(view.mapToGlobal(view.rect().center()))
                    self.input_menu = menu
                    return
        offset = (
            target_position(syntax, target)[0]
            if target
            else syntax.spans[session.editor.selection].start
        )
        try:
            session.insert_snippet(
                snippet, default_bindings(session, snippet, offset), target
            )
            self.library.record_use(identity)
            view.changed.emit()
            self.refresh_views()
            view.reveal(session.document.syntax.spans[session.editor.selection].start)
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

    def import_module(self):
        from little_tinker_rig.core.structure import add_import

        module, accepted = QInputDialog.getText(
            self, tr("Import module…"), tr("Module")
        )
        if not accepted:
            return
        names, accepted = QInputDialog.getText(
            self, tr("Import module…"), tr("Names (leave empty to import the module)")
        )
        if accepted:
            add_import(self.editing_session, module.strip(), names.strip())

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
        self.scratch_dock.raise_()

    def show_help(self):
        if self.pages.currentIndex() == 3:
            self.help_page.show_page("block-editor.md")
            self.set_mode(2)
            return
        item = self.library.currentItem() if self.library.hasFocus() else None
        identity = item.data(0, IDENTITY) if item else None
        match = self.session.selected_match()
        self.help_page.show_page(
            identity or (match.snippet.identity if match else "tutorial/first.md")
        )
        self.set_mode(2)

    def open_block_help(self, identity):
        self.help_page.show_page(identity)
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
        if self.pages.currentIndex() == 3:
            self.block_editor.search.setFocus()
            self.block_editor.search.selectAll()
            return
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
        if self.pages.currentIndex() == 3:
            self.block_editor.save()
            return True
        return self.save_document(self.document_page)

    def save_document(self, page):
        if page.lesson_project:
            return self.lessons.save(page.lesson_project)
        if page.unnamed:
            return self.save_as(page=page)
        page.save()
        self.remember_file(page.session.project.path)
        self.recovery.flush()
        return True

    def new_document_path(self, parent=None):
        if parent is None or parent.is_relative_to(examples_directory().resolve()):
            parent = Path(
                self.settings.value(
                    "programDirectory",
                    QStandardPaths.writableLocation(
                        QStandardPaths.StandardLocation.DocumentsLocation
                    )
                    or str(Path.home()),
                )
            )
        paths = {
            self.documents.widget(i).session.project.path
            for i in range(self.documents.count())
        }
        index = 0
        while True:
            path = parent / ("untitled.py" if index == 0 else f"untitled_{index}.py")
            if not path.exists() and path not in paths:
                return path
            index += 1

    def new_file(self):
        self.open_document(
            self.new_document_path(
                None
                if self.document_page.lesson_project
                else self.session.project.path.parent
            ),
            unnamed=True,
        )
        self.set_mode(0)

    def open_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("Open program or lesson"),
            str(self.session.project.path.parent),
            "Programs and lessons (*.py *.ltr *.pylesson *.pyblocks);;Python (*.py);;LittleTinker Rig (*.ltr *.pylesson *.pyblocks)",
        )
        for path in paths:
            self.open_document(Path(path))
        if paths and Path(paths[-1]).suffix == ".py":
            self.set_mode(0)

    def save_as(self, *, page=None):
        if page is None and self.pages.currentIndex() == 3:
            self.block_editor.copy_block()
            return True
        page = page or self.document_page
        if page.lesson_project:
            return self.lessons.save(page.lesson_project, choose=True)
        session = page.session
        page.prepare_save()
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save Python"),
            str(session.project.path),
            "Python (*.py)",
        )
        if path:
            from little_tinker_rig.core.project import Project

            destination = Path(path).resolve()
            for index in range(self.documents.count()):
                other = self.documents.widget(index)
                if other is not page and other.session.project.path == destination:
                    raise ValueError(tr("This file is already open in another tab"))
            if destination == session.project.path:
                page.save()
            else:
                project = Project(destination, allow_draft=True)
                project.document = session.document
                project.draft = session.project.draft
                project.collections = session.project.collections
                project.pins = session.project.pins
                project.save()
                session.project = project
                page.code.path = destination
            page.unnamed = False
            self.settings.setValue("programDirectory", str(destination.parent))
            self.remember_file(destination)
            self.recovery.flush()
            return True
        return False

    def _robot(self):
        if self.robot is None:
            from .robot import Robot

            self.robot = Robot(self)
            self.robot.output.connect(self.append_output)
            self.robot.failed.connect(self.hub_error)
            self.robot.updated.connect(self.update_hub)
            self.robot.busy_changed.connect(self.hub_busy)
            self.robot.problem.connect(self.runtime_panel.receive)
            self.robot.program_started.connect(self.runtime_panel.clear)
        return self.robot

    def hub_busy(self, busy):
        self.hub_is_busy = busy
        if busy:
            self.hub_input.setEnabled(False)
        self.hub_progress.setVisible(busy)
        self.run_action.setEnabled(
            self.hub_info.connected and not busy and self.pages.currentIndex() != 3
        )
        self.upload_action.setEnabled(
            self.hub_info.connected and not busy and self.pages.currentIndex() != 3
        )
        self.stored_action.setEnabled(self.hub_info.connected and not busy)
        self.firmware_action.setEnabled(not busy)
        self.update_hub(self.hub_info)

    def update_hub(self, info):
        if info.error and info.error != self.hub_info.error:
            self.error(info.error)
        self.hub_info = info
        self.hub_input.setEnabled(
            info.connected
            and info.transport in ("ble", "usb")
            and not info.monitoring
            and not self.hub_is_busy
        )
        if hasattr(self, "lessons"):
            self.lessons.update_check()
        action = info.connection_action
        self.hub_button.setEnabled(action != "disconnecting")
        self.hub_button.setText(
            tr("Disconnecting…")
            if action == "disconnecting"
            else (
                tr("Cancel connection")
                if action == "connecting"
                else tr("Disconnect hub") if info.connected else tr("＋ Connect hub")
            )
        )
        self.hub_button.setToolTip(
            tr("Cancel connection")
            if action == "connecting"
            else (
                tr("Disconnecting…")
                if action == "disconnecting"
                else (
                    tr("Disconnect {name}", name=info.name or tr("Virtual hub"))
                    if info.connected
                    else tr("Bluetooth, USB or virtual hub")
                )
            )
        )
        self.run_action.setEnabled(
            info.connected and not self.hub_is_busy and self.pages.currentIndex() != 3
        )
        self.upload_action.setEnabled(
            info.connected and not self.hub_is_busy and self.pages.currentIndex() != 3
        )
        self.stored_action.setEnabled(info.connected and not self.hub_is_busy)
        self.stop_action.setEnabled(info.connected and not action)
        self.device_panel.update_info(info)
        self.controls.update_info(info)

    def connect_hub(self):
        if self.hub_info.connection_action == "disconnecting":
            return
        if self.hub_info.connected or self.hub_info.connection_action == "connecting":
            self.disconnect_hub()
            return
        dialog = ConnectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._robot().connect_hub(
                dialog.name.text() or None,
                dialog.transport.currentData(),
                dialog.model.currentData(),
            )
            self.device_dock.show()
            self.device_dock.raise_()

    def run_hub(self):
        self.controls.armed.setChecked(False)
        self.commit_code()
        if self.save():
            self.console_dock.show()
            self._robot().run_file(self.session.project.path)

    def upload_hub(self):
        self.controls.armed.setChecked(False)
        self.commit_code()
        if self.save():
            self.console_dock.show()
            self._robot().upload_file(self.session.project.path)

    def run_stored_hub(self):
        self.controls.armed.setChecked(False)
        self.console_dock.show()
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
        try:
            self.block_editor.flush()
        except OSError as error:
            self.error(str(error))
            event.ignore()
            return
        # A lesson archive is saved as a whole; one close decision owns all its tabs.
        confirmed = set()
        for index in range(self.documents.count()):
            page = self.documents.widget(index)
            owner = page.lesson_project or page
            if owner in confirmed:
                continue
            if not self.confirm_close(page):
                event.ignore()
                return
            confirmed.add(owner)
        self.controls.close()
        if self.robot:
            self.robot.close()
        try:
            self.recovery.close()
        except OSError as error:
            self.error(str(error))
            event.ignore()
            return
        self.settings.setValue("windowGeometry", self.saveGeometry())
        self.lessons.release_unused(all_projects=True)
        self.settings.sync()
        event.accept()

    def ensure_user_collection(self):
        root = user_collection()
        self.collection_saved(root, load_collection(root))
        self.block_editor.configure(
            self.session.snippets, self.session.collection_paths
        )
        return root

    def validate_collection(self, root, snippets):
        for index in range(self.documents.count()):
            session = self.documents.widget(index).session
            if root in session.collection_paths:
                session.validate_snippets(session.load_snippets({root: snippets}))

    def collection_saved(self, root, snippets):
        for index in range(self.documents.count()):
            page = self.documents.widget(index)
            if root in page.session.collection_paths:
                page.session.set_snippets(page.session.load_snippets({root: snippets}))
                page.source.refresh_source()
        self.document_changed()

    def open_definition(self, identity):
        snippet = (
            identity
            if not isinstance(identity, str)
            else next(
                (
                    s
                    for s in self.session.available_snippets
                    if s.identity == identity and not s.historical
                ),
                None,
            )
        )
        if snippet is None:
            return
        identity = snippet.identity
        if snippet.source_path:
            self.set_mode(3)
            self.block_editor.open_definition(snippet)
        elif identity.startswith("document/functions/"):
            self.set_mode(0)
            self.change_editor(1)
            self.code.moveCursor(QTextCursor.MoveOperation.Start)
            self.code.find("def " + identity.rsplit("/", 1)[1] + "(")

    def create_block_from_selection(self):
        expression = False
        if self.code_active:
            cursor = self.code.textCursor()
            if not cursor.hasSelection():
                raise ValueError(tr("Select Python source to create a block."))
            source = cursor.selectedText().replace("\u2029", "\n")
            prefix_cursor = QTextCursor(cursor)
            prefix_cursor.setPosition(cursor.selectionStart())
            prefix_cursor.movePosition(
                QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor
            )
            prefix = prefix_cursor.selectedText()
            if not prefix.strip():
                source = prefix + source
        else:
            source, _ = self.editing_session.extract_selection()
            match = self.editing_session.selected_match()
            expression = (
                match.snippet.expression
                if match
                else isinstance(self.editing_session.editor.selection, ast.expr)
            )
        imports = tuple(
            ast.unparse(node)
            for node in self.session.document.syntax.tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
        )
        definition = template_from_source(source, imports, expression=expression)
        self.set_mode(3)
        self.block_editor.create(definition)


def launch(path: Path | None = None, collections=()) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("LittleTinker Rig")
    app.setOrganizationName("LittleTinker")
    code = application_settings().value("language", DEFAULT_LANGUAGE)
    set_language(code if code in LANGUAGES else DEFAULT_LANGUAGE)
    window = Studio(path, collections)
    with capture_output(window.append_output):
        window.show()
        return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(description="LittleTinker Rig desktop editor")
    parser.add_argument("file", type=Path, nargs="?")
    return launch(parser.parse_args().file)
