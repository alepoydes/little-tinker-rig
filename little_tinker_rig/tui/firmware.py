"""Prepare and review firmware before running the shared isolated installer."""

import asyncio
import codecs
import re
import sys
import webbrowser
from pathlib import Path

from textual import on, work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Log,
    ProgressBar,
    Select,
    Static,
)

from little_tinker_rig.core.paths import firmware_cache
from little_tinker_rig.i18n import language, tr
from little_tinker_rig.pybricks import firmware


class FirmwareScreen(ModalScreen):
    DEFAULT_CSS = """
    FirmwareScreen { align: center middle; }
    FirmwareScreen > Vertical { width: 95%; max-width: 120; height: 95%; border: round $accent; background: $surface; padding: 0 1; }
    FirmwareScreen #firmware-fields { height: 1fr; min-height: 5; max-height: 60%; }
    FirmwareScreen Horizontal { height: auto; }
    FirmwareScreen Select { width: 1fr; }
    FirmwareScreen Input { width: 1fr; }
    FirmwareScreen Button { margin-right: 1; }
    FirmwareScreen #firmware-log { height: 1fr; min-height: 3; }
    FirmwareScreen #firmware-progress { height: 1; }
    FirmwareScreen #firmware-details { height: auto; }
    FirmwareScreen Checkbox { height: auto; }
    """
    BINDINGS = [Binding("escape", "close", show=False)]

    def __init__(self):
        super().__init__()
        self.cache = firmware_cache()
        self.package = None
        self.images = []
        self.busy = False
        self.process = None

    def compose(self):
        with Vertical():
            yield Label(tr("Hub firmware"))
            with VerticalScroll(id="firmware-fields"):
                with Horizontal():
                    yield Select(
                        [
                            (tr(name), key)
                            for key, (_, _, name) in firmware.MODELS.items()
                        ],
                        value="inventor",
                        allow_blank=False,
                        id="model",
                    )
                    yield Select(
                        [
                            (tr("Install Pybricks"), "pybricks"),
                            (tr("Restore LEGO firmware"), "lego"),
                        ],
                        value="pybricks",
                        allow_blank=False,
                        id="kind",
                    )
                yield Select(
                    [(tr("Stable"), "stable"), (tr("Beta"), "beta")],
                    value="stable",
                    allow_blank=False,
                    id="channel",
                )
                yield Select([], prompt=tr("Version"), id="version")
                with Horizontal():
                    yield Button(tr("Refresh versions"), id="refresh")
                    yield Button(tr("Prepare download"), id="download")
                    yield Button(tr("Release notes"), id="notes", disabled=True)
                with Horizontal():
                    yield Input(
                        placeholder=tr("Local firmware ZIP / BIN path"), id="local-path"
                    )
                    yield Button(tr("Prepare local file"), id="local")
                yield Static(id="instructions", markup=False)
            yield Static(id="firmware-details", markup=False)
            yield Log(id="firmware-log", max_lines=2000, highlight=False)
            yield ProgressBar(total=100, show_eta=False, id="firmware-progress")
            yield Checkbox(
                tr(
                    "I agree to the firmware license and replacing the current firmware and stored program"
                ),
                id="consent",
            )
            with Horizontal():
                yield Button(
                    tr("Install firmware"),
                    id="install",
                    variant="warning",
                    disabled=True,
                )
                yield Button(tr("Close"), id="close")

    def on_mount(self):
        try:
            self.images = firmware.catalog(self.cache)
        except (ValueError, TypeError, OSError) as error:
            self.log_text(str(error) + "\n")
        self.selection_changed()

    def log_text(self, text):
        self.query_one("#firmware-log", Log).write(text.replace("\r", "\n"))
        matches = re.findall(r"(\d+)%", text)
        if matches:
            self.query_one("#firmware-progress", ProgressBar).update(
                total=100, progress=min(100, int(matches[-1]))
            )

    def invalidate(self):
        self.package = None
        self.query_one("#consent", Checkbox).value = False
        self.query_one("#firmware-details", Static).update("")
        self.update_buttons()

    def update_buttons(self):
        for widget in self.query(
            "Select, Input, #refresh, #download, #local, #consent, #close, #notes"
        ):
            widget.disabled = self.busy
        self.query_one("#install", Button).disabled = (
            self.busy
            or self.package is None
            or not self.query_one("#consent", Checkbox).value
        )
        if not self.busy:
            self.query_one("#download", Button).disabled = (
                self.query_one("#version", Select).value is Select.NULL
            )
        self.query_one("#channel", Select).disabled = (
            self.busy or self.query_one("#kind", Select).value == "lego"
        )
        index = self.query_one("#version", Select).value
        self.query_one("#notes", Button).disabled = (
            self.busy or index is Select.NULL or not self.images[int(index)].notes
        )

    def selection_changed(self):
        model, kind = (
            self.query_one("#model", Select).value,
            self.query_one("#kind", Select).value,
        )
        choices = [
            (image.label, str(index))
            for index, image in enumerate(self.images)
            if image.matches(model, kind, self.query_one("#channel", Select).value)
        ]
        version = self.query_one("#version", Select)
        version.set_options(choices)
        if choices:
            version.value = choices[0][1]
        self.query_one("#instructions", Static).update(
            firmware.instructions(model, kind, self.query_one("#channel", Select).value)
        )
        self.invalidate()

    @on(Select.Changed, "#model, #kind, #channel")
    def target_changed(self):
        self.selection_changed()

    @on(Select.Changed, "#version")
    @on(Input.Changed, "#local-path")
    def source_changed(self):
        self.invalidate()

    @on(Checkbox.Changed, "#consent")
    def consent_changed(self):
        self.update_buttons()

    @on(Button.Pressed)
    def button(self, event):
        event.stop()
        if event.button.id == "close":
            self.action_close()
        elif event.button.id == "notes":
            index = self.query_one("#version", Select).value
            if index is not Select.NULL:
                webbrowser.open(self.images[int(index)].notes)
        elif not self.busy:
            self.perform(event.button.id)

    @work(group="firmware", exclusive=False)
    async def perform(self, action):
        if self.busy:
            return
        package = self.package
        if action == "install" and (
            package is None or not self.query_one("#consent", Checkbox).value
        ):
            return
        self.busy = True
        self.update_buttons()
        progress = self.query_one("#firmware-progress", ProgressBar)
        progress.update(total=None, progress=0)
        success = False

        def report(text):
            self.app.call_from_thread(self.log_text, text + "\n")

        try:
            if action == "refresh":
                self.images = await asyncio.to_thread(
                    firmware.catalog, self.cache, refresh=True, report=report
                )
                self.selection_changed()
            elif action in {"download", "local"}:
                self.invalidate()
                model, kind = (
                    self.query_one("#model", Select).value,
                    self.query_one("#kind", Select).value,
                )
                self.query_one("#firmware-log", Log).clear()
                if action == "download":
                    index = self.query_one("#version", Select).value
                    if index is Select.NULL:
                        raise ValueError(tr("Choose a firmware version first"))
                    path = await asyncio.to_thread(
                        firmware.download,
                        self.images[int(index)],
                        self.cache,
                        report=report,
                    )
                else:
                    path = Path(self.query_one("#local-path", Input).value).expanduser()
                package = await asyncio.to_thread(
                    lambda: asyncio.run(firmware.prepare(path, model, kind))
                )
                self.package = package
                self.query_one("#firmware-details", Static).update(
                    f"{package.model} · {package.kind} · {package.version}\n{package.path}\nSHA-256: {package.digest}"
                )
                self.log_text(package.license + "\n")
            elif action == "install":
                future = self.app.robot.disconnect_hub()
                if future is not None:
                    await asyncio.wrap_future(future)
                self.query_one("#firmware-log", Log).clear()
                self.process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-u",
                    "-m",
                    "little_tinker_rig.pybricks.firmware",
                    str(package.path),
                    package.model,
                    package.kind,
                    package.digest,
                    "--language",
                    language(),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                decoder = codecs.getincrementaldecoder("utf-8")("replace")
                while data := await self.process.stdout.read(4096):
                    self.log_text(decoder.decode(data))
                self.log_text(decoder.decode(b"", final=True))
                success = await self.process.wait() == 0
                self.log_text(
                    "\n"
                    + firmware.result_message(success, package.kind, package.model)
                    + "\n"
                )
                return
            success = True
        except Exception as error:
            self.log_text(str(error) + "\n")
            if action == "install":
                self.log_text(
                    firmware.result_message(False, package.kind, package.model) + "\n"
                )
        finally:
            self.busy = False
            self.process = None
            self.query_one("#consent", Checkbox).value = False
            progress.update(total=100, progress=100 if success else 0)
            self.update_buttons()

    def action_close(self):
        if not self.busy:
            self.dismiss()
