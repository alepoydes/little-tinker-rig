"""Desktop workspaces with independent source documents and one hub connection."""

import argparse
import ast
import re
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, QSize, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
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
    QWidgetAction,
)

from little_tinker_rig.core.authoring import (
    selection_imports,
    template_from_source,
    user_collection,
)
from little_tinker_rig.core.edit import Target, target_position
from little_tinker_rig.core.expressions import navigate as navigate_expression
from little_tinker_rig.core.lessons import WORKSPACES, localized
from little_tinker_rig.core.parameters import default_bindings
from little_tinker_rig.core.project import ExternalChangeError
from little_tinker_rig.core.snippets import LEVELS, load_collection
from little_tinker_rig.core.syntax import Syntax
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
from .help import HelpPage
from .lessons import Lessons
from .library import IDENTITY, LEVEL_TITLES, VIEW_TITLES, Library, snippet_title
from .localization import localize, translate_standard_dialogs
from .navigation import ChoiceButtons, ModeList
from .recovery import Recovery
from .runtime import RuntimePanel
from .theme import (
    apply_application_theme,
    colors,
    contrast_icon,
    studio_stylesheet,
    svg_icon,
    theme_name,
)
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
        example_path = (
            path
            if path and path.resolve().is_relative_to(examples_directory().resolve())
            else None
        )
        if lesson_path or example_path:
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
        self.visual_theme = theme_name(self.settings.value("visualTheme", "light"))
        apply_application_theme(self.visual_theme)
        self.setMouseTracking(True)
        self.scratch_visible = False
        self.input_search = None
        self.collections = collections
        available = self.screen().availableGeometry().size()
        self.setMinimumSize(QSize(930, 620).boundedTo(available))
        self.resize(QSize(1380, 880).boundedTo(available))
        self.robot = None
        self.hub_info = HubInfo()
        self.hub_is_busy = False
        self.unread = 0
        self.setStyleSheet(studio_stylesheet(self.visual_theme))
        self.documents = QTabWidget()
        self.documents.setDocumentMode(True)
        self.documents.setTabsClosable(True)
        self.documents.setMovable(True)
        from .example_work import ExampleWorkspaces

        self.example_workspaces = ExampleWorkspaces(self)
        self.open_document(path or self.new_document_path(), unnamed=path is None)
        self.library = Library(self.session.available_snippets, self.settings)
        self.library.set_scope(self.document_page.catalog_scope)
        self.library.definition_requested.connect(self.open_definition)
        self.library.insert_requested.connect(
            lambda: self.perform(self.insert_selected)
        )
        self.search = QLineEdit()
        self.search.setPlaceholderText(N_("Find a block…"))
        self.search_action = self.search.addAction(
            svg_icon("search"), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.library.filter)
        self.level_filter = ChoiceButtons({**LEVEL_TITLES, "all": N_("All")})
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
        layout.setContentsMargins(5, 8, 5, 8)
        self.library.setAccessibleName(N_("Library · drag a block into the program"))
        layout.addWidget(self.search)
        layout.addWidget(self.level_filter)
        row = QHBoxLayout()
        row.setSpacing(2)
        row.addWidget(self.view_filter, 1)
        self.group_buttons = {}
        for key, title, expand in (
            ("collapse-all", N_("Collapse all groups"), False),
            ("expand-all", N_("Expand all groups"), True),
        ):
            button = QToolButton()
            button.setObjectName("catalogUtility")
            button.setIcon(svg_icon(key))
            button.setIconSize(QSize(20, 20))
            button.setToolTip(title)
            button.setAccessibleName(title)
            button.clicked.connect(
                lambda checked=False, expand=expand: self.library.expand_groups(expand)
            )
            row.addWidget(button)
            self.group_buttons[key] = button
        self.clear_usage = QToolButton()
        self.clear_usage.setObjectName("catalogUtility")
        self.clear_usage.setIcon(svg_icon("clear-history"))
        self.clear_usage.setProperty("translationSources", {})
        self.clear_usage.clicked.connect(self.library.clear_history)
        row.addWidget(self.clear_usage)
        layout.addLayout(row)
        self.library_status = QLabel()
        self.library_status.setWordWrap(True)
        self.library_status.setProperty("translationSources", {})
        self.library.status_changed.connect(self.library_status.setText)
        self.library.status_changed.connect(
            lambda text: self.library_status.setVisible(
                bool(text) and not self.library.empty_message
            )
        )
        layout.addWidget(self.library_status)
        self.whole_blocks = QPushButton(N_("← Back to whole blocks"))
        self.whole_blocks.setToolTip(
            N_(
                "The library is showing blocks for the selected input. Select its containing block to add the next action."
            )
        )
        self.whole_blocks.clicked.connect(self.clear_input_search)
        self.whole_blocks.hide()
        layout.addWidget(self.whole_blocks)
        layout.addWidget(self.library, 1)
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
        self.program_page.setStretchFactor(0, 0)
        self.program_page.setStretchFactor(1, 1)
        self.program_page.setChildrenCollapsible(False)
        self._catalog_width_manual = False
        self._catalog_resize_pending = False
        self.program_page.splitterMoved.connect(self._catalog_splitter_moved)
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
        workspace = self.workspace = QWidget()
        workspace_layout = self.workspace_layout = QHBoxLayout(workspace)
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
        self._scratch_dock_auto = True
        self._scratch_relocating = False
        self._scratch_layout_pending = False
        self._scratch_needs_size = False
        self.scratch_dock.dockLocationChanged.connect(
            self._scratch_dock_location_changed
        )
        self.block_editor.configure(
            self.session.snippets, self.session.collection_paths
        )
        self.main_menu_bar = self.menuBar()
        self.title_bar = TitleBar(self, self.main_menu_bar)
        self.setMenuWidget(self.title_bar)
        self.active_document = self.document_page
        self.documents.currentChanged.connect(self.document_changed)
        self.documents.tabCloseRequested.connect(self.close_document)
        self.refresh_views()
        self.update_hub(HubInfo())
        self.document_mode_changed()
        self.retranslate()
        QApplication.instance().applicationStateChanged.connect(self.application_state)
        QApplication.instance().installEventFilter(self)
        QApplication.instance().focusChanged.connect(self.focus_changed)
        self.recovery = Recovery(self)
        self.documents.tabBar().tabMoved.connect(lambda *_: self.recovery.schedule())
        self.recovery.schedule()
        QTimer.singleShot(0, self.recovery.offer)
        if geometry := self.settings.value("windowGeometry", b""):
            self.restoreGeometry(geometry)
        self._schedule_catalog_width()
        self._schedule_scratch_layout()
        if lesson_path:
            self.perform(lambda: self.lessons.open(lesson_path))
        elif example_path:
            placeholder = self.document_page
            self.perform(lambda: self.open_document(example_path))
            if self.documents.count() > 1:
                self.close_document(self.documents.indexOf(placeholder))

    def _icon(self, theme, fallback):
        if (Path(__file__).with_name("icons") / f"{theme}.svg").is_file():
            return svg_icon(theme)
        return contrast_icon(
            QIcon.fromTheme(
                theme, self.style().standardIcon(getattr(QStyle.StandardPixmap, fallback))
            )
        )

    def _action(
        self,
        menu,
        label,
        shortcut,
        callback,
        toolbar=None,
        icon=None,
        *,
        commit_parameters=True,
    ):
        action = QAction(label, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if icon:
            action.setIcon(self._icon(*icon))
            action.setProperty("visualIconSource", icon)
        action.setToolTip(label)
        action.triggered.connect(
            lambda checked=False: self.perform(
                callback, commit_parameters=commit_parameters
            )
        )
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
        self.active_cell = None
        self.scratch_stack = QStackedWidget()
        self.scratch_stack.addWidget(self.scratch)
        self.scratch_dock = self.dock(
            N_("Scratch"), self.scratch_stack, Qt.DockWidgetArea.RightDockWidgetArea
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
        self.scratch_dock.hide()
        self.device_dock.hide()

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
        self.main_toolbar = toolbar
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
        self.reload_action = self._action(
            file, N_("Reload from disk…"), None, self.reload_document
        )
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
        self.format_action = self._action(
            edit, N_("Format Python"), "Ctrl+Alt+L", self.format_python
        )
        self.structural_actions.append(
            self._action(edit, N_("Import module…"), None, self.import_module)
        )
        self.find_action = self._action(edit, N_("Find"), "Ctrl+F", self.show_find)
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
                f"Ctrl+Alt+{index + 1}",
                lambda mode=index: self.change_editor(mode),
            )
            action.setCheckable(True)
            group.addAction(action)
            self.editor_actions.append(action)
        self.editor_actions[int(self.code_active)].setChecked(True)
        view.addSeparator()
        appearance = view.addMenu(N_("Appearance"))
        theme_group = QActionGroup(self)
        self.theme_actions = {}
        for value, label in (("light", N_("Light")), ("dark", N_("Dark"))):
            action = appearance.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == self.visual_theme)
            action.triggered.connect(
                lambda checked=False, selected=value: self.change_visual_theme(selected)
            )
            theme_group.addAction(action)
            self.theme_actions[value] = action
        appearance.addSeparator()
        intensity_row = QWidget()
        intensity_layout = QHBoxLayout(intensity_row)
        intensity_layout.setContentsMargins(8, 2, 8, 2)
        intensity_layout.addWidget(QLabel(N_("Block color")))
        self.intensity = QSlider(Qt.Orientation.Horizontal)
        self.intensity.setAccessibleName(N_("Block color"))
        self.intensity.setRange(0, 100)
        self.intensity.setValue(int(self.settings.value("blockIntensity", 78)))
        self.intensity.valueChanged.connect(self.set_intensity)
        self.intensity.valueChanged.connect(
            lambda value: self.settings.setValue("blockIntensity", value)
        )
        intensity_layout.addWidget(self.intensity)
        intensity_action = QWidgetAction(appearance)
        intensity_action.setDefaultWidget(intensity_row)
        appearance.addAction(intensity_action)
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
            commit_parameters=False,
        )
        self.run_button = toolbar.widgetForAction(self.run_action)
        self.stop_button = toolbar.widgetForAction(self.stop_action)
        self.run_button.setObjectName("programRun")
        self.stop_button.setObjectName("programStop")
        self.run_action.setIcon(
            svg_icon("media-playback-start", tint=colors()["accent_text"])
        )
        self.stop_action.setIcon(svg_icon("media-playback-stop", tint="#ffffff"))
        self._action(robot, N_("Connect…"), "F7", self.connect_hub)
        self._action(
            robot, N_("Disconnect"), None, self.disconnect_hub, commit_parameters=False
        )
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
        self.hub_button.setObjectName("hubConnection")
        self.hub_button.setIcon(self._icon("network-connect", "SP_ComputerIcon"))
        self.hub_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.hub_button.clicked.connect(self.connect_hub)
        self.hub_button_action = toolbar.addWidget(self.hub_button)
        self.theme_toggle = QToolButton()
        self.theme_toggle.setObjectName("appearanceToggle")
        self.theme_toggle.clicked.connect(
            lambda: self.change_visual_theme(
                "dark" if self.visual_theme == "light" else "light"
            )
        )
        toolbar.addWidget(self.theme_toggle)
        self._refresh_theme_toggle()
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
        self.set_intensity(self.intensity.value())
        self._update_toolbar_density()

    def _refresh_theme_toggle(self):
        target = "dark" if self.visual_theme == "light" else "light"
        self.theme_toggle.setIcon(svg_icon("theme-moon" if target == "dark" else "theme-sun"))
        name = tr("Dark") if target == "dark" else tr("Light")
        description = tr("Appearance") + " · " + name
        self.theme_toggle.setToolTip(description)
        self.theme_toggle.setAccessibleName(description)

    def _update_toolbar_density(self):
        style = (
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            if self.width() >= 1180
            else Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.run_button.setToolButtonStyle(style)
        self.stop_button.setToolButtonStyle(style)

    def _catalog_splitter_moved(self, *_):
        self._catalog_width_manual = True

    def _schedule_catalog_width(self):
        if self._catalog_width_manual or self._catalog_resize_pending:
            return
        self._catalog_resize_pending = True
        QTimer.singleShot(0, self._fit_catalog_width)

    def _fit_catalog_width(self):
        self._catalog_resize_pending = False
        if self._catalog_width_manual or not self.library_pane.isVisible():
            return
        available = self.program_page.width()
        if available <= 0:
            return
        target = 270 if self.width() < 1100 else 320
        if abs(self.library_pane.width() - target) > 1:
            self.program_page.setSizes([target, max(1, available - target)])

    def _scratch_dock_location_changed(self, area):
        if not self._scratch_relocating:
            self._scratch_dock_auto = False
            self.pages.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                (
                    QSizePolicy.Policy.Ignored
                    if area == Qt.DockWidgetArea.BottomDockWidgetArea
                    else QSizePolicy.Policy.Preferred
                ),
            )

    def _schedule_scratch_layout(self):
        if not self._scratch_dock_auto or self._scratch_layout_pending:
            return
        self._scratch_layout_pending = True
        QTimer.singleShot(0, self, self._fit_scratch_layout)

    def _fit_scratch_layout(self):
        self._scratch_layout_pending = False
        if not self._scratch_dock_auto:
            return
        narrow = self.width() < 1200
        target = (
            Qt.DockWidgetArea.BottomDockWidgetArea
            if narrow
            else Qt.DockWidgetArea.RightDockWidgetArea
        )
        if self.dockWidgetArea(self.scratch_dock) == target:
            return
        active = (
            self.scratch_dock.isVisible()
            and not self.scratch_dock.visibleRegion().isEmpty()
        )
        hidden = self.scratch_dock.isHidden()
        self._scratch_relocating = True
        try:
            self.removeDockWidget(self.scratch_dock)
            self.addDockWidget(target, self.scratch_dock)
            if narrow:
                self.tabifyDockWidget(self.console_dock, self.scratch_dock)
            else:
                self.tabifyDockWidget(self.device_dock, self.scratch_dock)
            self.pages.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                (
                    QSizePolicy.Policy.Ignored
                    if narrow
                    else QSizePolicy.Policy.Preferred
                ),
            )
            self.scratch_dock.setVisible(not hidden)
            if active:
                self.scratch_dock.raise_()
            self._scratch_needs_size = True
        finally:
            self._scratch_relocating = False
        if active:
            self._schedule_scratch_size()

    def _schedule_scratch_size(self):
        QTimer.singleShot(0, self, self._size_scratch_once)

    def _size_scratch_once(self):
        if not self._scratch_needs_size or not self.scratch_dock.isVisible():
            return
        bottom = (
            self.dockWidgetArea(self.scratch_dock)
            == Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.resizeDocks(
            [self.scratch_dock],
            [180 if bottom else 300],
            Qt.Orientation.Vertical if bottom else Qt.Orientation.Horizontal,
        )
        self._scratch_needs_size = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "run_button"):
            self._update_toolbar_density()
        if hasattr(self, "program_page"):
            self._schedule_catalog_width()
        if hasattr(self, "_scratch_dock_auto"):
            self._schedule_scratch_layout()

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
    def scratch(self):
        return self.document_page.scratch

    @property
    def find_bar(self):
        return self.document_page.find_bar

    @property
    def editing_page(self):
        if self.pages.currentIndex() != 0:
            return None
        if self.active_cell in self.scratch.cells and self.scratch_dock.isVisible():
            return self.active_cell
        return self.document_page

    @property
    def editing_source(self):
        page = self.editing_page
        return page.source if page is not None else self.source

    @property
    def editing_session(self):
        return self.editing_source.session

    def change_editor(self, index):
        if page := self.editing_page:
            page.change_mode(index)

    def format_python(self):
        from little_tinker_rig.core.formatting import format_source

        editor = self.text_editor()
        if editor is not None and not editor.isReadOnly():
            editor.replace_formatted(
                format_source(
                    editor.toPlainText(),
                    fragment=self.editing_page in self.scratch.cells,
                )
            )

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
        for button in self.group_buttons.values():
            button.setVisible(self.library.view in ("catalog", "lesson"))
        self.clear_usage.setVisible(self.library.view in ("recent", "frequent"))
        title = (
            tr("Clear recent")
            if self.library.view == "recent"
            else tr("Reset usage history")
        )
        self.clear_usage.setToolTip(title)
        self.clear_usage.setAccessibleName(title)

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
        requested = self.document_page
        previous = self.active_document
        if previous is not requested and self.documents.indexOf(previous) >= 0:
            self.documents.blockSignals(True)
            self.documents.setCurrentWidget(previous)
            self.documents.blockSignals(False)
            if not self.finish_parameters():
                return
            self.documents.blockSignals(True)
            self.documents.setCurrentWidget(requested)
            self.documents.blockSignals(False)
        self.active_document = requested
        self.active_cell = None
        self.library.set_scope(self.document_page.catalog_scope)
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
        if not self.finish_parameters():
            return
        set_language(code)
        application_settings().setValue("language", code)
        for window in QApplication.topLevelWidgets():
            # Qt can retain closed windows here until deferred deletion runs.
            if isinstance(window, Studio) and (window is self or window.isVisible()):
                window.retranslate()

    def change_visual_theme(self, name):
        name = theme_name(name)
        self.settings.setValue("visualTheme", name)
        apply_application_theme(name)
        for window in QApplication.topLevelWidgets():
            if isinstance(window, Studio) and (window is self or window.isVisible()):
                window.visual_theme = name
                window.setStyleSheet(studio_stylesheet(name))
                window.title_bar.apply_theme(name)
                for action in window.findChildren(QAction):
                    if source := action.property("visualIconSource"):
                        action.setIcon(window._icon(*source))
                window.run_action.setIcon(
                    svg_icon("media-playback-start", tint=colors()["accent_text"])
                )
                window.stop_action.setIcon(
                    svg_icon("media-playback-stop", tint="#ffffff")
                )
                for button in window.findChildren(QToolButton):
                    standard = button.property("standardIcon")
                    if standard is not None:
                        button.setIcon(
                            contrast_icon(button.style().standardIcon(standard))
                        )
                    if visual := button.property("visualIconName"):
                        button.setIcon(svg_icon(visual))
                window.hub_button.setIcon(
                    window._icon("network-connect", "SP_ComputerIcon")
                )
                window._refresh_theme_toggle()
                window.console_button.setIcon(
                    window._icon("utilities-terminal", "SP_FileDialogListView")
                )
                window.level_filter.apply_theme()
                window.view_filter.apply_theme()
                window.search_action.setIcon(svg_icon("search"))
                window.modes.apply_theme()
                for key, button in window.group_buttons.items():
                    button.setIcon(svg_icon(key))
                window.clear_usage.setIcon(svg_icon("clear-history"))
                window.library.itemDelegate().apply_theme()
                window.block_editor.apply_theme()
                window.help_page.apply_theme()
                window.lessons.apply_theme()
                window.device_panel.apply_theme()
                window.controls.apply_theme()
                window.runtime_panel.apply_theme()
                for assembly_page in (
                    window.lessons.assembly_host.lesson_page,
                    window.lessons.assembly_host.free_page,
                ):
                    if assembly_page:
                        assembly_page.apply_theme()
                        if assembly_page.view:
                            assembly_page.view.requestUpdate()
                window.theme_actions[name].setChecked(True)
                for index in range(window.documents.count()):
                    page = window.documents.widget(index)
                    page.source.apply_theme()
                    page.code.apply_theme()
                    page.scratch.apply_theme()
                window.library.viewport().update()
                window.update()
        for dialog in QApplication.topLevelWidgets():
            if isinstance(dialog, QDialog) and hasattr(dialog, "apply_theme"):
                dialog.apply_theme()

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
        self._refresh_theme_toggle()
        for index in range(self.documents.count()):
            self.documents.widget(index).update_mode()
            self.documents.widget(index).finder.retranslate()
            self.documents.widget(index).source.refresh_source()
        self.scratch.refresh(self.session)
        for cell in self.scratch.cells:
            cell.finder.retranslate()
        self.language_actions[language()].setChecked(True)
        self.library.set_scope(self.document_page.catalog_scope)
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
        self.refresh_status()

    def open_document(self, path, *, unnamed=False):
        path = Path(path).resolve()
        if path.is_file() and path.is_relative_to(examples_directory().resolve()):
            return self.example_workspaces.open(path)
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
        page.example_work = self.example_workspaces.owner(path) if not project else None
        page.update_mode()
        page.unnamed = unnamed
        page.changed.connect(self.refresh_views)
        page.failed.connect(self.error)
        page.snippet_dropped.connect(self.insert_snippet)
        page.definition_requested.connect(self.open_definition)
        page.help_requested.connect(self.open_block_help)
        page.input_search_requested.connect(self.find_input_blocks)
        page.mode_changed.connect(self.document_mode_changed)
        page.scratch.changed.connect(self.refresh_views)
        page.scratch.failed.connect(self.error)
        page.scratch.snippet_inserted.connect(
            lambda identity: self.library.record_use(identity)
        )
        page.scratch.definition_requested.connect(self.open_definition)
        page.scratch.help_requested.connect(self.open_block_help)
        page.scratch.input_search_requested.connect(self.find_input_blocks)
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
        self.example_workspaces.menu(self.examples_menu, examples_directory())

    def refresh_recent_files(self):
        self.recent_menu.clear()
        recent = self.settings.value("recentFiles", [])
        recent = [recent] if isinstance(recent, str) else recent
        if not recent:
            self.recent_menu.addAction(tr("No recent files")).setEnabled(False)
            return
        for index, path in enumerate(recent, 1):
            action = self.recent_menu.addAction(f"&{index}  {path.replace('&', '&&')}")
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
        if not self.finish_parameters():
            return False
        if page.example_work:
            return self.recovery.flush()
        project = page.lesson_project
        if project and project.retain and project.path is None:
            return self.recovery.flush()
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
        if project and project.retain:
            message = tr(
                "Update saved lesson project {name} before closing? Your local attempt remains available either way.",
                name=project.path.name,
            )
        elif project:
            message = tr(
                "Save lesson project {name} before closing? Saving includes all open programs in this project.",
                name=(
                    project.path.name
                    if project.path
                    else localized(project.lesson.data["title"], language())
                ),
            )
        else:
            message = tr("Save {p0} before closing?", p0=page.session.project.path.name)
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
        self.scratch_stack.removeWidget(page.scratch)
        page.scratch.deleteLater()
        page.deleteLater()
        if self.recovery.flush():
            self.lessons.release_unused()

    def scratch_visibility(self, visible):
        if getattr(self, "_scratch_relocating", False):
            return
        if visible and getattr(self, "_scratch_needs_size", False):
            self._schedule_scratch_size()
        if self.pages.currentIndex() == 0:
            if not visible:
                # Finish after Qt has hidden the dock's children; restoring it
                # inside visibilityChanged would leave those children hidden.
                QTimer.singleShot(0, self, self.finish_scratch_hide)
            # An inactive dock tab emits visibilityChanged(False) without being
            # closed. Preserve the user's choice when switching tabs or modes.
            self.scratch_visible = not self.scratch_dock.isHidden()

    def finish_scratch_hide(self):
        if (
            self.pages.currentIndex() != 0
            or not self.scratch_dock.visibleRegion().isEmpty()
        ):
            return
        for cell in self.scratch.cells:
            if not cell.source.finish_parameter():
                self.scratch_dock.show()
                self.scratch_dock.raise_()
                cell.source.parameter_editor.line_edit.setFocus()
                break
        self.refresh_status()

    def set_mode(self, index):
        if index < 0 or self.modes.item(index).isHidden():
            return
        if not self.finish_parameters():
            self.modes.blockSignals(True)
            self.modes.setCurrentRow(self.pages.currentIndex())
            self.modes.blockSignals(False)
            return
        self.pages.setCurrentIndex(index)
        if self.document_page.lesson_project:
            self.document_page.lesson_project.progress["mode"] = WORKSPACES[index]
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
        if index == 1:
            self.device_dock.show()
            self.device_dock.raise_()
        elif index != 0:
            self.device_dock.hide()
        if index == 3:
            self.block_editor.configure(
                self.session.snippets, self.session.collection_paths
            )
        self.update_hub(self.hub_info)
        self.refresh_status()

    def refresh_views(self):
        if not hasattr(self, "scratch_stack") or self.document_page is None:
            return
        if self.scratch_stack.indexOf(self.scratch) < 0:
            self.scratch_stack.addWidget(self.scratch)
        self.scratch_stack.setCurrentWidget(self.scratch)
        self.document_page.sync_text()
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
            cell = self.scratch.focused_cell()
            if cell is not None:
                self.active_cell = cell
            elif new is self.document_page or self.document_page.isAncestorOf(new):
                self.active_cell = None
            self.refresh_status()

    def text_editor(self):
        if self.pages.currentIndex() == 3:
            return self.block_editor.code or self.block_editor.empty
        page = self.editing_page
        return page.code if page is not None and page.code_active else None

    def find_input_blocks(self, view, slot, providers):
        if not self.input_search:
            self.library.remember_view()
            self.catalog_return = (
                self.library.view,
                self.search.text(),
                self.library.view_states[self.library.view],
            )
        if self.input_search:
            self.input_search[0].input_target = None
        self.input_search = (view, slot)
        view.input_target = None if providers else slot
        self.search.clear()
        self.view_filter.select("catalog")
        self.library.context_key = None
        self.library.set_context(view.session, slot, providers)
        self.library.expand_groups(True)
        self.whole_blocks.setText(tr("← All blocks · {name}", name=slot.parameter.name))
        self.whole_blocks.setToolTip(
            tr("Create the value before this block, in a scope visible here.")
            + "\n"
            + tr("Constructors inside a loop run on every iteration.")
            if providers
            else tr(
                "Drag a matching expression onto this input to replace its value, or double-click a result. Undo restores the previous value."
            )
        )
        self.whole_blocks.show()

    def clear_input_search(self):
        previous = self.input_search
        self.input_search = None
        if previous:
            previous[0].input_target = None
        self.library.clear_context()
        self.whole_blocks.hide()
        if previous:
            view, search, state = self.catalog_return
            self.view_filter.select(view)
            self.search.setText(search)
            self.library.view_states[view] = state
            self.library.render()

    def input_search_current(self):
        view, slot = self.input_search
        if view.session.document.syntax is not slot.syntax:
            return False
        if view is self.source:
            return not self.code_active
        return any(
            cell.source is view and not cell.code_active for cell in self.scratch.cells
        )

    def refresh_status(self):
        if not hasattr(self, "undo_action"):
            return
        self.editing_source.expression_level = self.level_filter.value
        if hasattr(self, "lessons"):
            self.lessons.palette()
        self.library.set_scope(self.document_page.catalog_scope)
        if self.input_search:
            if not self.input_search_current() or self.library.context_key is None:
                self.clear_input_search()
        page = self.editing_page
        if page is not None:
            was_visible = self.library_pane.isVisible()
            self.library_pane.setVisible(not page.code_active)
            if not was_visible and self.library_pane.isVisible():
                self._schedule_catalog_width()
        session = self.editing_session
        match = session.selected_match()
        selection = (
            snippet_title(match.snippet)
            if match and match.snippet.help
            else "Python"
            if page and page.code_active
            else tr("Select a block")
        )
        self.statusBar().showMessage(
            tr("Python · changes not checked")
            if page
            and page.code_active
            and page.code.toPlainText() != session.document.state.source
            else tr(
                "{p0} · warnings: {p1}",
                p0=selection,
                p1=len(session.analysis.diagnostics()),
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
        self.setWindowTitle(f"{'● ' if dirty else ''}{name} — LittleTinker Rig")
        text_editor = self.text_editor()
        self.undo_action.setEnabled(
            (
                text_editor.document().isUndoAvailable()
                if self.pages.currentIndex() == 3 and text_editor
                else self.session.document.can_undo
            )
            and self.pages.currentIndex() in (0, 3)
        )
        self.redo_action.setEnabled(
            (
                text_editor.document().isRedoAvailable()
                if self.pages.currentIndex() == 3 and text_editor
                else self.session.document.can_redo
            )
            and self.pages.currentIndex() in (0, 3)
        )
        for action in self.structural_actions:
            action.setEnabled(text_editor is None and self.pages.currentIndex() == 0)
        self.create_block_action.setEnabled(self.pages.currentIndex() == 0)
        for action in self.editor_actions:
            action.setEnabled(page is not None)
        if page:
            self.editor_actions[int(page.code_active)].setChecked(True)
        self.find_action.setEnabled(self.pages.currentIndex() in (0, 2, 3))
        self.format_action.setEnabled(
            text_editor is not None and not text_editor.isReadOnly()
        )
        self.reload_action.setEnabled(
            self.pages.currentIndex() == 0
            and not self.document_page.unnamed
            and self.document_page.lesson_project is None
        )
        if self.pages.currentIndex() == 3:
            self.statusBar().showMessage(self.block_editor.caption.text())
        for index in range(self.documents.count()):
            page = self.documents.widget(index)
            self.documents.setTabText(
                index, ("● " if page.dirty else "") + page.session.project.path.name
            )
            self.documents.setTabToolTip(index, str(page.session.project.path))
        self.source.viewport().update()

    def finish_parameters(self):
        views = [self.documents.widget(i).source for i in range(self.documents.count())]
        if hasattr(self, "scratch"):
            views.extend(cell.source for cell in self.scratch.cells)
        return all(view.finish_parameter() for view in views)

    def perform(self, callback, *, commit_parameters=True):
        if commit_parameters and not self.finish_parameters():
            return
        cell = self.editing_page if self.editing_page in self.scratch.cells else None
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
            if self.input_search:
                if not self.input_search_current():
                    self.clear_input_search()
                    return
                view, slot = self.input_search
                snippet = self.library.snippets.get(item.data(0, IDENTITY))
                if (
                    view.input_target is slot
                    or snippet is not None
                    and snippet.expression
                ) and view.session.document.syntax is slot.syntax:
                    view.session.editor.selection = slot.node
                    self.insert_snippet(item.data(0, IDENTITY), view=view)
                    return
                statement = next(
                    (
                        node
                        for node in slot.syntax.ancestors(slot.node)
                        if isinstance(node, ast.stmt)
                    ),
                    None,
                )
                if statement in slot.syntax.statement_suite:
                    suite = slot.syntax.statement_suite[statement]
                    view.session.editor.selection = slot.node
                    self.insert_snippet(
                        item.data(0, IDENTITY),
                        Target(suite, suite.statements.index(statement)),
                        view=view,
                    )
                    return
            self.insert_snippet(item.data(0, IDENTITY))

    def insert_snippet(self, identity, target=None, *, view=None):
        from little_tinker_rig.core.expressions import targets

        if (
            view is None
            and target is None
            and self.editing_page
            and self.editing_page.code_active
        ):
            raise ValueError(
                tr("Switch this editor to Blocks before inserting a block.")
            )
        view = view or (self.editing_source if target is None else self.source)
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
        cell = self.editing_page if self.editing_page in self.scratch.cells else None
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
        cell = self.editing_page if self.editing_page in self.scratch.cells else None
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
        match = self.editing_session.selected_match()
        self.help_page.show_page(
            identity or (match.snippet.identity if match else "tutorial/first.md")
        )
        self.set_mode(2)

    def open_block_help(self, identity):
        self.help_page.show_page(identity)
        self.set_mode(2)

    def show_diagnostics(self):
        page = self.editing_page
        if page is None:
            return
        page.commit_code()
        session = self.editing_session
        diagnostics = session.analysis.diagnostics()
        for diagnostic in diagnostics:
            line, column = session.document.syntax.position(diagnostic.span.start)
            self.append_output(f"{line}:{column}: {diagnostic.message}\n")
        if not diagnostics:
            self.append_output(tr("No unknown names found.\n"))
        self.console_dock.show()

    def show_find(self):
        if self.pages.currentIndex() == 2:
            self.help_page.open_find()
            return
        if self.pages.currentIndex() == 3:
            search = self.block_editor.search
            search.setFocus()
            search.selectAll()
            return
        if page := self.editing_page:
            page.finder.open()

    def find_next(self):
        if page := self.editing_page:
            page.finder.find()

    def set_intensity(self, value):
        QApplication.instance().setProperty("ltrBlockIntensity", value / 100)
        for index in range(self.documents.count()):
            page = self.documents.widget(index)
            for view in (page.source, *(cell.source for cell in page.scratch.cells)):
                view.intensity = value / 100
                view.viewport().update()

    def navigate(self, step):
        editor = self.editing_session.editor
        editor.navigate_move(step) if editor.moving else editor.sibling(step)

    def undo(self):
        if self.pages.currentIndex() not in (0, 3):
            return
        editor = self.text_editor()
        (
            editor.undo()
            if self.pages.currentIndex() == 3 and editor
            else self.document_page.undo()
        )

    def redo(self):
        if self.pages.currentIndex() not in (0, 3):
            return
        editor = self.text_editor()
        (
            editor.redo()
            if self.pages.currentIndex() == 3 and editor
            else self.document_page.redo()
        )

    def save(self):
        if self.pages.currentIndex() == 3:
            self.block_editor.save()
            return True
        return self.save_document(self.document_page)

    def save_document(self, page):
        if not self.finish_parameters():
            return False
        if page.lesson_project:
            return self.lessons.save(page.lesson_project)
        if page.unnamed:
            return self.save_as(page=page)
        try:
            page.save()
        except ExternalChangeError as error:
            dialog = QMessageBox(self)
            dialog.setWindowTitle(tr("File changed on disk"))
            dialog.setIcon(QMessageBox.Icon.Warning)
            dialog.setText(str(error))
            dialog.setInformativeText(
                tr(
                    "Reload replaces this document and its Scratch with the saved version. Save a copy keeps your edits in another file."
                )
            )
            reload = dialog.addButton(
                tr("Reload from disk"), QMessageBox.ButtonRole.DestructiveRole
            )
            copy = dialog.addButton(
                tr("Save a copy…"), QMessageBox.ButtonRole.ActionRole
            )
            cancel = dialog.addButton(QMessageBox.StandardButton.Cancel)
            dialog.setDefaultButton(cancel)
            dialog.exec()
            if dialog.clickedButton() is copy:
                return self.save_as(page=page, copy_only=True)
            if dialog.clickedButton() is reload:
                page.reload()
                self.document_changed()
            return False
        self.remember_file(page.session.project.path)
        self.recovery.flush()
        return True

    def reload_document(self):
        page = self.document_page
        if page.unnamed or page.lesson_project:
            return
        if (
            page.dirty
            and QMessageBox.question(
                self,
                tr("Reload from disk"),
                tr(
                    "Replace this document and its Scratch with the saved version? Unsaved changes will be discarded."
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        page.reload()
        self.document_changed()

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
                if self.document_page.lesson_project or self.document_page.example_work
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

    def save_as(self, *, page=None, copy_only=False):
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
            old_scope, was_unnamed = page.catalog_scope, page.unnamed
            from little_tinker_rig.core.project import Project

            destination = Path(path).resolve()
            if destination.is_relative_to(examples_directory().resolve()):
                raise ValueError(tr("Save your work outside the bundled examples."))
            owner = self.example_workspaces.owner(destination)
            if owner is not None and owner is not page.example_work:
                raise ValueError(tr("This file belongs to another example attempt."))
            if copy_only and destination == session.project.path:
                raise ValueError(tr("Choose another file to keep both versions."))
            for index in range(self.documents.count()):
                other = self.documents.widget(index)
                if other is not page and other.session.project.path == destination:
                    raise ValueError(tr("This file is already open in another tab"))
            relocation = (
                self.example_workspaces.relocation(page, destination)
                if page.example_work
                else None
            )
            if destination == session.project.path:
                page.save()
            else:
                project = Project(destination, allow_draft=True)
                project.document = session.document
                project.draft = session.project.draft
                project.collections = session.project.collections
                project.pins = session.project.pins
                project.example_attempt = session.project.example_attempt
                if page.example_work:
                    project.example_attempt = page.example_work.identity
                project.save()
            if relocation:
                self.example_workspaces.relocate(page, *relocation)
            if destination != session.project.path:
                session.project = project
                page.code.path = destination
            page.unnamed = False
            if was_unnamed:
                self.library.relocate_scope(old_scope, page.catalog_scope)
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
        state = "busy" if action else "connected" if info.connected else "disconnected"
        if self.hub_button.property("connectionState") != state:
            self.hub_button.setProperty("connectionState", state)
            self.hub_button.style().unpolish(self.hub_button)
            self.hub_button.style().polish(self.hub_button)
        self.hub_button.setEnabled(action != "disconnecting")
        self.hub_button.setText(
            tr("Disconnecting…")
            if action == "disconnecting"
            else (
                tr("Cancel connection")
                if action == "connecting"
                else tr("Disconnect hub")
                if info.connected
                else tr("＋ Connect hub")
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
        self.transfer_hub(run=True)

    def upload_hub(self):
        self.transfer_hub(run=False)

    def transfer_hub(self, *, run):
        self.controls.armed.setChecked(False)
        if not self.finish_parameters():
            return
        self.document_page.commit_code()
        if not self.recovery.flush():
            return
        sources = {
            self.documents.widget(i).session.project.path: self.documents.widget(i).text
            for i in range(self.documents.count())
        }
        self.console_dock.show()
        robot = self._robot()
        transfer = robot.run_file if run else robot.upload_file
        transfer(self.session.project.path, sources)

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

    def eventFilter(self, watched, event):
        # Window shortcuts are disabled by modal dialogs. Stop still belongs to
        # the Studio that owns the dialog, even with several windows open.
        if event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            owner = QApplication.activeModalWidget()
            while owner is not None and owner is not self:
                owner = owner.parent()
            if (
                owner is self
                and event.key() == Qt.Key.Key_F6
                and event.modifiers() == Qt.KeyboardModifier.NoModifier
                and self.stop_action.isEnabled()
            ):
                if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                    self.stop_action.trigger()
                event.accept()
                return True
        return super().eventFilter(watched, event)

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
        page = self.editing_page
        if page is None:
            return
        expression = False
        if page.code_active:
            cursor = page.code.textCursor()
            if not cursor.hasSelection():
                raise ValueError(tr("Select Python source to create a block."))
            source = cursor.selectedText().replace("\u2029", "\n")
            offset = cursor.selectionStart()
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
            offset = self.editing_session.document.syntax.spans[
                self.editing_session.editor.selection
            ].start
            match = self.editing_session.selected_match()
            expression = (
                match.snippet.expression
                if match
                else isinstance(self.editing_session.editor.selection, ast.expr)
            )
        session = self.editing_session
        try:
            syntax = Syntax(page.text, fragment=True)
        except SyntaxError:
            syntax = session.document.syntax
        context = getattr(session, "context", None)
        imports = selection_imports(
            source,
            syntax,
            offset,
            context=context.document.syntax if context else None,
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
