"""Source editor and Pybricks tools for terminals, without Qt or block editing."""

import argparse
import asyncio
import re
from pathlib import Path

from textual import on, work
from textual.app import App, SystemCommand
from textual.binding import Binding
from textual.command import CommandPalette
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Log, ProgressBar, Static
from textual.widgets.text_area import Selection

from little_tinker_rig.core.source_file import SourceFile, utf8_source
from little_tinker_rig.i18n import LANGUAGES, N_, language, set_language, tr
from little_tinker_rig.pybricks.devices import DEVICE_KINDS, HubInfo, describe_device
from little_tinker_rig.pybricks.simulation import PROFILES
from little_tinker_rig.pybricks.worker import HubWorker

from .dialogs import Form, Unsaved
from .editor import PythonEditor


class HubEvent(Message):
    def __init__(self, kind, value):
        super().__init__()
        self.kind, self.value = kind, value


class Studio(App):
    TITLE = "LittleTinker Rig"
    CSS = """
    #shortcuts { height: 1; background: $panel; }
    #status { height: auto; max-height: 3; padding: 0 1; background: $panel; }
    #workspace { height: 1fr; }
    #editor { width: 1fr; height: 1fr; }
    #ports { width: 45; display: none; border-left: solid $accent; }
    #port-table { height: 1fr; }
    #console-pane { height: 12; display: none; border-top: solid $accent; }
    #console { height: 1fr; }
    #hub-input { height: 3; }
    #progress { height: 1; display: none; }
    #error-line { height: auto; display: none; }
    #error-line Static { width: 1fr; }
    #error-line Button { height: 1; min-width: 18; border: none; }
    #search { height: auto; display: none; }
    #search Input { width: 1fr; }
    #search Button { min-width: 10; }
    """
    BINDINGS = [
        Binding("ctrl+o", "open", N_("Open"), priority=True),
        Binding("ctrl+n", "new", N_("New"), show=False, priority=True),
        Binding("ctrl+s", "save", N_("Save"), priority=True),
        Binding("ctrl+shift+s", "save_as", N_("Save as"), show=False, priority=True),
        Binding("ctrl+f", "find", N_("Find / replace"), show=False, priority=True),
        Binding("f3", "find_next", N_("Find next"), show=False, priority=True),
        Binding("f4", "upload", N_("Upload"), priority=True),
        Binding("f5", "run", N_("Run"), priority=True),
        Binding("f6", "stop", N_("Stop"), priority=True),
        Binding("f7", "connect", N_("Connect"), priority=True),
        Binding("f8", "console", N_("Console"), priority=True),
        Binding("f9", "monitor", N_("Ports"), show=False, priority=True),
        Binding("f10", "command_palette", N_("Commands"), priority=True),
        Binding("ctrl+q", "quit", N_("Quit"), show=False, priority=True),
        Binding("escape", "editor", show=False),
    ]

    def __init__(self, path=None):
        super().__init__()
        self.file = SourceFile(path)
        self.info = HubInfo()
        self.hub_busy = False
        self.robot = None
        self.problem = None
        self.execution_path = None
        self.unread = 0
        self.closing = False

    def compose(self):
        self.status = Static(id="status", markup=False)
        yield self.status
        with Horizontal(id="search"):
            yield Input(placeholder=tr("Find"), id="find")
            yield Input(placeholder=tr("Replace with"), id="replacement")
            yield Button(tr("Next"), id="next")
            yield Button(tr("Replace"), id="replace")
            yield Button(tr("Replace all"), id="replace-all")
        with Horizontal(id="workspace"):
            self.editor = PythonEditor()
            yield self.editor
            with Vertical(id="ports"):
                self.port_title = Static(tr("Port monitor"))
                yield self.port_title
                self.ports = DataTable(id="port-table", cursor_type="row")
                yield self.ports
        with Horizontal(id="error-line"):
            self.error = Static(markup=False)
            yield self.error
            yield Button(tr("Go to error"), id="go-error")
        self.progress = ProgressBar(total=None, show_eta=False, id="progress")
        yield self.progress
        with Vertical(id="console-pane"):
            self.output_log = Log(id="console", max_lines=2000, highlight=False)
            yield self.output_log
            self.hub_input = Input(
                placeholder=tr("Hub input · Enter sends a line"),
                id="hub-input",
                disabled=True,
            )
            yield self.hub_input
        self.shortcuts = Static(id="shortcuts")
        yield self.shortcuts

    def on_mount(self):
        self.begin_capture_print(self)

        def send(kind):
            return lambda value: self.post_message(HubEvent(kind, value))

        self.robot = HubWorker(
            output=send("output"),
            failed=send("failed"),
            updated=send("info"),
            busy_changed=send("busy"),
            problem=send("problem"),
            program_started=send("started"),
        )
        self.load_file(self.file)
        self.translate()

    def translate(self):
        self.shortcuts.update(
            "  ".join(
                f"[bold]{binding.key.replace('ctrl+', '^').upper()}[/] {tr(binding.description)}"
                for binding in sorted(self.BINDINGS, key=lambda b: b.key != "f10")
                if binding.show
            )
        )
        self.query_one("#find", Input).placeholder = tr("Find")
        self.query_one("#replacement", Input).placeholder = tr("Replace with")
        for key, message in (
            ("next", N_("Next")),
            ("replace", N_("Replace")),
            ("replace-all", N_("Replace all")),
            ("go-error", N_("Go to error")),
        ):
            self.query_one(f"#{key}", Button).label = tr(message)
        self.hub_input.placeholder = tr("Hub input · Enter sends a line")
        self.port_title.update(tr("Port monitor"))
        self.ports.clear(columns=True)
        self.port_columns = self.ports.add_columns(
            tr("Port"), tr("Device"), tr("Value")
        )
        self.displayed_ports = {}
        self.update_hub()

    def get_system_commands(self, screen):
        commands = (
            (N_("New program"), self.action_new),
            (N_("Open program"), self.action_open),
            (N_("Save"), self.action_save),
            (N_("Save as"), self.action_save_as),
            (N_("Find / replace"), self.action_find),
            (N_("Check Python syntax"), self.action_check),
            (N_("Python completion"), self.editor.action_complete),
            (N_("Python help"), self.editor.action_help),
            (N_("Connect hub"), self.action_connect),
            (N_("Disconnect hub"), self.action_disconnect),
            (N_("Upload program"), self.action_upload),
            (N_("Upload and run"), self.action_run),
            (N_("Run uploaded program"), self.action_run_stored),
            (N_("Stop program"), self.action_stop),
            (N_("Port monitor"), self.action_monitor),
            (N_("Hub firmware"), self.action_firmware),
            (N_("Console"), self.action_console),
            (N_("Go to error"), self.action_error),
            (N_("Language"), self.action_language),
            (N_("Quit"), self.action_quit),
        )
        for title, action in commands:
            yield SystemCommand(tr(title), "", action)

    def action_command_palette(self):
        self.push_screen(CommandPalette(placeholder=tr("Search commands…")))

    def check_action(self, action, parameters):
        # Editor shortcuts must not start hub actions behind a modal dialog.
        if isinstance(self.screen, ModalScreen):
            return False
        return True

    def load_file(self, file):
        self.file = file
        self.execution_path = None
        self.editor.path = file.path
        self.editor.load_text(file.source)
        self.editor.focus()
        self.problem = None
        self.query_one("#error-line").display = False
        self.update_status()

    @on(PythonEditor.Changed)
    def edited(self):
        self.update_status()

    def update_status(self):
        file = str(self.file.path) if self.file.path else tr("Untitled")
        marker = " *" if self.file.dirty(self.editor.text) else ""
        state = tr("Disconnected")
        if self.info.connected:
            state = f"{self.info.name} · {self.info.transport}"
            if self.info.monitoring and (
                self.info.transport != "virtual" or self.query_one("#ports").display
            ):
                state += " · " + tr("Monitoring")
            elif self.info.running:
                state += " · " + tr("Running")
            if self.info.battery_mv is not None:
                state += f" · {self.info.battery_mv / 1000:.2f} V"
        if self.info.connection_action:
            state = (
                tr("Connecting to hub…")
                if self.info.connection_action == "connecting"
                else tr("Disconnecting…")
            )
        elif self.hub_busy:
            state += " · " + tr("Working…")
        if self.unread:
            state += " · " + tr("New console output · F8")
        self.status.update(f"{file}{marker}\n{state}")

    async def save_file(self, *, as_new=False):
        path = self.file.path
        try:
            if as_new or path is None:
                answer = await self.push_screen_wait(
                    Form(
                        tr("Save as"),
                        [
                            (
                                "path",
                                tr("Python file"),
                                str(path or Path.cwd() / "main.py"),
                                None,
                            )
                        ],
                        accept=tr("Save"),
                    )
                )
                if answer is None:
                    return False
                path = Path(answer["path"]).expanduser().resolve()
            overwrite = False
            if path != self.file.path and path.exists():
                answer = await self.push_screen_wait(
                    Form(
                        tr("Save as"),
                        text=tr("The file already exists. Replace it?")
                        + "\n"
                        + str(path),
                        accept=tr("Replace"),
                    )
                )
                if answer is None:
                    return False
                overwrite = True
            self.file.save(self.editor.text, path, overwrite=overwrite)
            if self.editor.text != self.file.source:
                selection = self.editor.selection
                self.editor.history.checkpoint()
                self.editor.replace(self.file.source, (0, 0), self.editor.document.end)
                self.editor.selection = selection
                self.editor.history.checkpoint()
            self.editor.path = self.file.path
            self.update_status()
            return True
        except (ValueError, OSError, UnicodeError) as error:
            self.failed(str(error))
            return False

    async def may_leave(self):
        if not self.file.dirty(self.editor.text):
            return True
        answer = await self.push_screen_wait(Unsaved())
        return answer == "discard" or (answer == "save" and await self.save_file())

    @work(group="files", exclusive=True)
    async def action_new(self):
        if await self.may_leave():
            self.load_file(SourceFile())

    @work(group="files", exclusive=True)
    async def action_open(self):
        answer = await self.push_screen_wait(
            Form(
                tr("Open program"),
                [("path", tr("Python file"), str(self.file.path or Path.cwd()), None)],
                accept=tr("Open"),
            )
        )
        if answer is None:
            return
        try:
            path = Path(answer["path"]).expanduser()
            if not path.is_file():
                raise FileNotFoundError(tr("Choose an existing Python file"))
            if await self.may_leave():
                self.load_file(SourceFile(path))
        except (ValueError, SyntaxError, OSError, UnicodeError) as error:
            self.failed(str(error))

    @work(group="files", exclusive=True)
    async def action_save(self):
        await self.save_file()

    @work(group="files", exclusive=True)
    async def action_save_as(self):
        await self.save_file(as_new=True)

    def action_find(self):
        self.query_one("#search").display = True
        self.query_one("#find", Input).focus()

    def action_editor(self):
        self.editor.cancel_assistance()
        self.query_one("#search").display = False
        self.editor.focus()

    def action_find_next(self):
        needle = self.query_one("#find", Input).value
        if not needle:
            self.action_find()
            return
        source = self.editor.text
        offset = self.editor.document.get_index_from_location(self.editor.selection.end)
        position = source.find(needle, offset)
        if position < 0:
            position = source.find(needle, 0, offset)
        if position < 0:
            self.notify(tr("Text not found"))
            return
        start = self.editor.document.get_location_from_index(position)
        end = self.editor.document.get_location_from_index(position + len(needle))
        self.editor.move_cursor(start, center=True)
        self.editor.selection = Selection(start, end)

    @on(Input.Submitted, "#find")
    def find_submitted(self):
        self.action_find_next()

    @on(Button.Pressed, "#next, #replace, #replace-all")
    def search_button(self, event):
        needle = self.query_one("#find", Input).value
        replacement = self.query_one("#replacement", Input).value
        if not needle:
            return
        if event.button.id == "replace-all":
            source = self.editor.text
            self.editor.replace(
                source.replace(needle, replacement),
                (0, 0),
                self.editor.document.end,
                maintain_selection_offset=False,
            )
        elif event.button.id == "replace" and self.editor.selected_text == needle:
            self.editor.replace(
                replacement,
                *sorted((self.editor.selection.start, self.editor.selection.end)),
                maintain_selection_offset=False,
            )
        self.action_find_next()

    def action_check(self):
        try:
            compile(self.editor.text, str(self.file.path or "main.py"), "exec")
        except SyntaxError as error:
            self.editor.move_cursor(
                (max(0, (error.lineno or 1) - 1), max(0, (error.offset or 1) - 1)),
                center=True,
            )
            self.editor.focus()
            self.failed(str(error))
            return False
        self.notify(tr("Python syntax is valid"))
        return True

    def show_console(self):
        self.query_one("#console-pane").display = True
        self.unread = 0
        self.update_status()

    def action_console(self):
        pane = self.query_one("#console-pane")
        pane.display = not pane.display
        self.unread = 0
        self.update_status()

    def output(self, text):
        if not text:
            return
        # Transport progress uses carriage returns and terminal escape sequences.
        plain = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        self.output_log.write(plain.replace("\r", "\n"))
        if self.hub_busy and (matches := re.findall(r"(\d+)%", plain)):
            self.progress.update(total=100, progress=min(100, int(matches[-1])))
        if not self.query_one("#console-pane").display:
            self.unread += 1
            self.update_status()

    def on_print(self, event):
        if self.is_mounted(self.status):
            self.output(event.text)

    def failed(self, message):
        self.show_console()
        self.output(message + "\n")
        self.notify(message, severity="error", markup=False)

    def on_hub_event(self, event):
        if self.closing or not self.is_mounted(self.status):
            return
        if event.kind == "output":
            self.output(event.value)
        elif event.kind == "failed":
            self.failed(event.value)
        elif event.kind == "info":
            self.info = event.value
            self.update_hub()
        elif event.kind == "busy":
            self.hub_busy = event.value
            self.progress.display = event.value
            self.progress.update(total=None, progress=0)
            self.update_hub()
        elif event.kind == "problem":
            self.problem = event.value
            self.error.update(
                f"{self.problem.path or ''}:{self.problem.line} · {self.problem.kind}: {self.problem.detail}"
            )
            self.query_one("#error-line").display = True
            self.show_console()
        elif event.kind == "started":
            self.problem = None
            self.query_one("#ports").display = False
            self.query_one("#error-line").display = False

    def update_hub(self):
        if not self.info.connected:
            self.query_one("#ports").display = False
        self.hub_input.disabled = not (
            self.info.connected
            and self.info.transport != "virtual"
            and self.info.running
            and not self.info.monitoring
            and not self.hub_busy
        )
        rows = {
            str(port): (
                str(port),
                tr(DEVICE_KINDS.get(data.get("type"), "Device")),
                describe_device(data),
            )
            for port, data in sorted(self.info.ports.items())
            if self.info.connected and self.info.monitoring
        }
        if rows.keys() != self.displayed_ports.keys():
            self.ports.clear()
            for key, values in rows.items():
                self.ports.add_row(*values, key=key)
        else:
            for key, values in rows.items():
                for index, value in enumerate(values):
                    if value != self.displayed_ports[key][index]:
                        self.ports.update_cell(
                            key, self.port_columns[index], value, update_width=True
                        )
        self.displayed_ports = rows
        self.update_status()

    @work(group="connection-dialog", exclusive=True)
    async def action_connect(self):
        if self.info.connection_action == "disconnecting":
            return
        if self.info.connected or self.info.connection_action == "connecting":
            self.action_disconnect()
            return
        answer = await self.push_screen_wait(
            Form(
                tr("Connect hub"),
                [
                    (
                        "transport",
                        tr("Connection"),
                        "ble",
                        [
                            ("Bluetooth", "ble"),
                            ("USB", "usb"),
                            (tr("Virtual hub"), "virtual"),
                        ],
                    ),
                    ("name", tr("Hub name / USB port (empty: automatic)"), "", None),
                    (
                        "model",
                        tr("Virtual hub model"),
                        "inventor",
                        [(name, key) for key, (name, _, _) in PROFILES.items()],
                    ),
                ],
                accept=tr("Connect"),
            )
        )
        if answer is not None:
            self.show_console()
            self.robot.connect_hub(
                answer["name"] or None, answer["transport"], answer["model"]
            )

    def action_disconnect(self):
        self.robot.disconnect_hub()

    @work(group="transfer", exclusive=True)
    async def transfer(self, run):
        if self.hub_busy:
            self.failed(tr("Wait for the hub operation to finish"))
            return
        if not self.info.connected:
            self.failed(tr("Connect a hub first"))
            return
        if not self.action_check():
            return
        path = self.file.path or (Path.cwd() / "untitled.py")
        sources = {path: self.editor.text}
        self.show_console()
        previous = self.execution_path
        self.execution_path = path
        try:
            if run:
                self.robot.run_file(path, sources)
            else:
                self.robot.upload_file(path, sources)
        except (ValueError, SyntaxError, OSError, UnicodeError) as error:
            self.execution_path = previous
            self.failed(str(error))

    def action_run(self):
        self.transfer(True)

    def action_upload(self):
        self.transfer(False)

    def action_run_stored(self):
        self.show_console()
        self.robot.run_stored()

    def action_stop(self):
        self.query_one("#ports").display = False
        self.robot.stop_program()

    @on(Input.Submitted, "#hub-input")
    def send_input(self, event):
        self.robot.write_input((event.value + "\r").encode("utf-8"))
        self.hub_input.value = ""

    @work(group="monitor-dialog", exclusive=True)
    async def action_monitor(self):
        if self.query_one("#ports").display:
            self.robot.stop_program()
            self.query_one("#ports").display = False
            return
        if not self.info.connected:
            self.failed(tr("Connect a hub first"))
            return
        answer = await self.push_screen_wait(
            Form(
                tr("Port monitor"),
                text=tr(
                    "Monitoring stops the current program and may replace the program stored on the hub. Upload your program again when finished."
                ),
                accept=tr("Start monitor"),
            )
        )
        if answer is not None:
            self.query_one("#ports").display = True
            self.robot.start_monitor()

    def action_firmware(self):
        from .firmware import FirmwareScreen

        self.push_screen(FirmwareScreen())

    @on(Button.Pressed, "#go-error")
    def error_button(self):
        self.action_error()

    @work(group="files", exclusive=True)
    async def action_error(self):
        problem = self.problem
        if not problem or not problem.path:
            return
        try:
            if problem.path in (self.file.path, self.execution_path):
                source = utf8_source(self.editor.text)
            else:
                file = SourceFile(problem.path)
                source = file.source
            if source != problem.source:
                self.failed(
                    tr(
                        "The source has changed since this program ran. The error refers to the uploaded version."
                    )
                )
                return
            if problem.path not in (self.file.path, self.execution_path):
                if not await self.may_leave():
                    return
                self.load_file(file)
            self.editor.move_cursor((problem.line - 1, 0), center=True)
            self.editor.focus()
        except (ValueError, OSError, UnicodeError) as error:
            self.failed(str(error))

    @work(group="language-dialog", exclusive=True)
    async def action_language(self):
        answer = await self.push_screen_wait(
            Form(
                tr("Language"),
                [
                    (
                        "language",
                        tr("Language"),
                        language(),
                        [(title, code) for code, title in LANGUAGES.items()],
                    )
                ],
            )
        )
        if answer is not None:
            set_language(answer["language"])
            self.translate()

    @work(group="files", exclusive=True)
    async def action_quit(self):
        if await self.may_leave():
            self.exit()

    async def on_unmount(self):
        self.closing = True
        self.end_capture_print(self)
        if self.robot:
            await asyncio.to_thread(self.robot.close)


def launch(path=None):
    Studio(path).run()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="LittleTinker Rig terminal Python editor and Pybricks tools"
    )
    parser.add_argument("file", type=Path, nargs="?")
    parser.add_argument("--language", choices=LANGUAGES, default="en")
    args = parser.parse_args()
    set_language(args.language)
    return launch(args.file)
