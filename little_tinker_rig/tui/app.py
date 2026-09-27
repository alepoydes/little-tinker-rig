"""Keyboard frontend. All edits go through the same Session as Qt and CLI."""

import argparse
import ast
import codecs
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    OptionList,
    RichLog,
    Static,
    TextArea,
)
from textual.widgets.option_list import Option

from little_tinker_rig.core.edit import target_position
from little_tinker_rig.core.presentation import regions, role_color, snippet_role
from little_tinker_rig.core.session import Session
from little_tinker_rig.core.snippets import instantiate


class EditDialog(ModalScreen):
    DEFAULT_CSS = """
    EditDialog { align: center middle; }
    EditDialog > Vertical { width: 85%; height: 85%; border: round $accent; background: $surface; padding: 1 2; }
    EditDialog TextArea { height: 1fr; }
    EditDialog #fields { height: 1fr; }
    EditDialog #error { color: $error; height: auto; }
    EditDialog Horizontal { height: 3; }
    """
    BINDINGS = [("escape", "dismiss", "Cancel"), ("ctrl+enter", "apply", "Apply")]

    def __init__(self, title, apply, *, text=None, fields=(), suggestions=()):
        super().__init__()
        self.title_text, self.apply_edit = title, apply
        self.initial_text, self.fields, self.suggestions = text, fields, suggestions

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.title_text)
            if self.initial_text is not None:
                yield TextArea(
                    self.initial_text,
                    show_line_numbers=True,
                    soft_wrap=False,
                    tab_behavior="indent",
                    id="text",
                )
            else:
                with VerticalScroll(id="fields"):
                    for index, (name, value, annotation) in enumerate(self.fields):
                        yield Label(name + (f" · {annotation}" if annotation else ""))
                        yield Input(
                            value,
                            id=f"parameter-{index}",
                            suggester=SuggestFromList(
                                list(self.suggestions), case_sensitive=True
                            ),
                        )
            yield Static("", id="error")
            with Horizontal():
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")

    def action_dismiss(self):
        self.dismiss(False)

    def action_apply(self):
        value = (
            self.query_one("#text", TextArea).text
            if self.initial_text is not None
            else {
                name: self.query_one(f"#parameter-{index}", Input).value
                for index, (name, _, _) in enumerate(self.fields)
            }
        )
        try:
            self.apply_edit(value)
        except (ValueError, SyntaxError, OSError) as error:
            self.query_one("#error", Static).update(str(error))
            return
        self.dismiss(True)

    @on(Button.Pressed)
    def button(self, event):
        if event.button.id == "apply":
            self.action_apply()
        else:
            self.action_dismiss()


class HelpDialog(ModalScreen):
    DEFAULT_CSS = """
    HelpDialog { align: center middle; }
    HelpDialog > Vertical { width: 85%; height: 85%; background: $surface; border: round $accent; }
    HelpDialog VerticalScroll { height: 1fr; padding: 1 2; }
    """
    BINDINGS = [("escape", "close", "Close")]

    def __init__(self, text):
        super().__init__()
        self.text = text

    def compose(self):
        with Vertical():
            with VerticalScroll():
                yield Markdown(self.text)
            yield Button("Close", id="close")

    def action_close(self):
        self.dismiss()

    @on(Button.Pressed)
    def close_help(self):
        self.action_close()


class QuitDialog(ModalScreen):
    DEFAULT_CSS = """
    QuitDialog { align: center middle; }
    QuitDialog > Vertical { width: 60; height: auto; padding: 1 2; background: $surface; border: round $accent; }
    QuitDialog Horizontal { height: 3; }
    QuitDialog #error { height: auto; color: $error; }
    """
    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self):
        with Vertical():
            yield Label("Save changes before closing?")
            yield Static("", id="error")
            with Horizontal():
                yield Button("Save", id="save", variant="primary")
                yield Button("Discard", id="discard", variant="error")
                yield Button("Cancel", id="cancel")

    def action_cancel(self):
        self.dismiss(False)

    @on(Button.Pressed)
    def choose(self, event):
        if event.button.id == "save":
            try:
                self.app.session.project.save()
            except (ValueError, OSError) as error:
                self.query_one("#error", Static).update(str(error))
                return
        self.dismiss(event.button.id != "cancel")


class Studio(App):
    TITLE = "LittleTinker Rig"
    CSS = """
    #columns { height: 1fr; }
    #library-pane { width: 28%; min-width: 20; }
    #scratch-pane { width: 25%; min-width: 18; }
    #source-pane { width: 1fr; }
    OptionList { height: 1fr; border: round $primary; }
    #console { height: 6; border-top: solid $primary; display: none; }
    #status { height: 2; }
    #quick-help { height: 4; }
    Label { padding: 0 1; }
    """
    BINDINGS = [
        ("ctrl+s", "save", "Save"),
        ("ctrl+z", "undo", "Undo"),
        ("ctrl+y", "redo", "Redo"),
        ("f1", "help", "Help"),
        ("f2", "edit", "Edit Python"),
        ("f3", "parameters", "Parameters"),
        ("alt+left", "parent", "Parent"),
        ("alt+right", "child", "Child"),
        ("ctrl+m", "move", "Move"),
        ("alt+up", "previous_target", "Previous target"),
        ("alt+down", "next_target", "Next target"),
        ("ctrl+enter", "commit_move", "Commit move"),
        ("escape", "cancel_move", "Cancel move"),
        ("ctrl+x", "scratch", "To Scratch"),
        ("ctrl+r", "restore", "Restore"),
        ("ctrl+n", "new_scratch", "New Scratch"),
        ("ctrl+f", "fold", "Fold"),
        ("ctrl+u", "upgrade", "Upgrade"),
        ("ctrl+e", "expand", "Expand snippet"),
        ("f5", "run", "Run hub"),
        ("f6", "stop", "Stop hub"),
        ("f7", "connect", "Connect"),
        ("f8", "console", "Console"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, path: Path, collections=()):
        super().__init__()
        self.session = Session(path, collections)
        self.visible_lines = []
        self.folded = set()
        self.connection = None
        self._displayed_source = None

    def compose(self):
        yield Header()
        with Horizontal(id="columns"):
            with Vertical(id="library-pane"):
                yield Label("Library · Enter to insert")
                yield Input(placeholder="Search snippets", id="search")
                yield OptionList(id="library")
                yield Static("", id="quick-help")
            with Vertical(id="source-pane"):
                yield Label(self.session.project.path.name)
                yield OptionList(id="source")
            with Vertical(id="scratch-pane"):
                yield Label("Scratch · unfinished code")
                yield OptionList(id="scratch")
        yield Static("", id="status")
        yield RichLog(id="console", wrap=True)
        yield Footer()

    def on_mount(self):
        self._library("")
        self.session.editor.select(0)
        self.refresh_views()
        self.query_one("#source").focus()

    def _library(self, search):
        widget = self.query_one("#library", OptionList)
        widget.clear_options()
        for snippet in self.session.snippets:
            if (
                not snippet.historical
                and search.casefold()
                in (snippet.identity + " " + snippet.help).casefold()
            ):
                preview = instantiate(
                    snippet,
                    {p.name: p.name for p in snippet.parameters if p.default is None},
                ).source
                text = Text(
                    snippet.help.splitlines()[0] if snippet.help else snippet.identity,
                    style="bold",
                )
                text.append("\n" + "\n".join(preview.splitlines()[:3]))
                text.stylize(f"#203040 on {role_color(snippet_role(snippet))}")
                widget.add_option(Option(text, id=snippet.identity))

    @on(Input.Changed, "#search")
    def search(self, event):
        self._library(event.value)

    def refresh_views(self, _result=None):
        source = self.session.document.state.source
        if source != self._displayed_source:
            self.folded.clear()
            self._displayed_source = source
        syntax = self.session.document.syntax
        selected = syntax.spans[self.session.editor.selection]
        match = self.session.selected_match()
        if match:
            selected = match.span
        first_line, first_column = syntax.position(selected.start)
        last_line, last_column = syntax.position(selected.end)
        presentation = regions(syntax, self.session.visible_matches)
        hidden = set()
        for start, end in self.folded:
            hidden.update(range(start + 1, end + 1))
        widget = self.query_one("#source", OptionList)
        options = []
        self.visible_lines = []
        for row, line in enumerate(source.splitlines() or [""], 1):
            if row in hidden:
                continue
            self.visible_lines.append(row)
            text = Text(f"{row:>4}  ", style="dim")
            code = Text(line.ljust(max(60, len(line))), style="#243344 on #f5f6f8")
            for region in presentation:
                if region.line <= row <= region.end_line:
                    start = (
                        region.column
                        if row == region.line
                        else min(region.column, len(line) - len(line.lstrip()))
                    )
                    end = (
                        len(code)
                        if region.extend_line or row < region.end_line
                        else region.end_column
                    )
                    code.stylize(f"on {role_color(region.role)}", start, end)
            if first_line <= row <= last_line:
                code.stylize(
                    "bold underline",
                    first_column if row == first_line else 0,
                    last_column if row == last_line else len(line),
                )
            text.append_text(code)
            if any(start == row for start, _ in self.folded):
                text.append(" …", style="bold")
            options.append(Option(text, id=f"line-{row}"))
        with widget.prevent(OptionList.OptionHighlighted):
            widget.clear_options()
            widget.add_options(options)
            selected_line = syntax.position(selected.start)[0]
            if selected_line in self.visible_lines:
                widget.highlighted = self.visible_lines.index(selected_line)
        scratch = self.query_one("#scratch", OptionList)
        previous = scratch.highlighted
        scratch.clear_options()
        for index, text in enumerate(self.session.document.state.scratch):
            scratch.add_option(
                Option(
                    f"{index}: {text.strip().splitlines()[0] if text.strip() else '(empty)'}",
                    id=str(index),
                )
            )
        if previous is not None and previous < scratch.option_count:
            scratch.highlighted = previous
        self._status()

    def _status(self):
        editor = self.session.editor
        match = self.session.selected_match()
        message = match.snippet.identity if match else type(editor.selection).__name__
        if editor.moving:
            target = editor.moving.targets[editor.moving.index]
            offset, indent = target_position(editor.moving.syntax, target)
            message = f"Move → line {editor.moving.syntax.position(offset)[0]}, indent {indent}. Alt+arrows; Ctrl+Enter commits; Esc cancels."
        else:
            diagnostics = self.session.analysis.diagnostics()
            message += f" · {len(diagnostics)} name warning(s)"
            if self.session.project.dirty:
                message += " · unsaved"
        self.query_one("#status", Static).update(message)

    @on(OptionList.OptionHighlighted, "#source")
    def select_line(self, event):
        row = int(event.option.id.split("-")[1])
        syntax = self.session.document.syntax
        line = syntax.lines[row - 1] if row <= len(syntax.lines) else ""
        line = line.rstrip("\r\n")
        self.session.editor.select(syntax.offset(row, len(line) - len(line.lstrip())))
        self.refresh_views()

    @on(OptionList.OptionHighlighted, "#library")
    def quick_help(self, event):
        snippet = next(
            s
            for s in self.session.snippets
            if s.identity == event.option.id and not s.historical
        )
        self.query_one("#quick-help", Static).update(
            snippet.help.splitlines()[0] if snippet.help else ""
        )

    @on(OptionList.OptionSelected, "#library")
    def insert_snippet(self, event):
        snippet = next(
            s
            for s in self.session.snippets
            if s.identity == event.option.id and not s.historical
        )
        self._parameters(
            snippet, lambda values: self.session.insert_snippet(snippet, values)
        )

    def _parameters(self, snippet, apply, bindings=None):
        bindings = bindings or {}
        fields = [
            (
                p.name,
                (
                    ast.unparse(bindings[p.name])
                    if p.name in bindings
                    else p.default or ""
                ),
                p.annotation,
            )
            for p in snippet.parameters
        ]
        offset = self.session.document.syntax.spans[self.session.editor.selection].start
        self.push_screen(
            EditDialog(
                snippet.identity,
                apply,
                fields=fields,
                suggestions=self.session.analysis.available(offset),
            ),
            self.refresh_views,
        )

    def perform(self, operation):
        try:
            operation()
            self.refresh_views()
        except (ValueError, SyntaxError, OSError) as error:
            self.notify(str(error), severity="error", timeout=8)

    def action_save(self):
        self.perform(self.session.project.save)

    def action_undo(self):
        self.perform(self.session.editor.undo)

    def action_redo(self):
        self.perform(self.session.editor.redo)

    def action_parent(self):
        editor = self.session.editor
        if editor.moving:
            self.perform(lambda: editor.navigate_move(depth=-1))
        else:
            editor.parent()
            self.refresh_views()

    def action_child(self):
        editor = self.session.editor
        if editor.moving:
            self.perform(lambda: editor.navigate_move(depth=1))
        else:
            editor.child()
            self.refresh_views()

    def action_edit(self):
        if self.focused is self.query_one("#scratch"):
            index = self.query_one("#scratch", OptionList).highlighted
            if index is not None:
                self.push_screen(
                    EditDialog(
                        "Edit Scratch",
                        lambda text: self.session.set_scratch(index, text),
                        text=self.session.document.state.scratch[index],
                    ),
                    self.refresh_views,
                )
        else:
            self.push_screen(
                EditDialog(
                    "Edit as Python · Ctrl+Enter to apply",
                    self.session.edit_python,
                    text=self.session.selected_text(),
                ),
                self.refresh_views,
            )

    def action_parameters(self):
        match = self.session.selected_match()
        if match:
            self._parameters(
                match.snippet, self.session.edit_parameters, match.bindings
            )
        else:
            self.notify("Select a recognized snippet first")

    def action_help(self):
        match = self.session.selected_match()
        library = self.query_one("#library", OptionList)
        if self.focused is library and library.highlighted is not None:
            identity = library.get_option_at_index(library.highlighted).id
            snippet = next(
                s
                for s in self.session.snippets
                if s.identity == identity and not s.historical
            )
        else:
            snippet = match.snippet if match else None
        text = (
            f"# {snippet.identity}\n\n{snippet.help}"
            if snippet
            else "# LittleTinker Rig\n\nTab changes panels. Select a source line, then Alt+Left/Right selects its parent/child. F2 edits ordinary Python; F3 edits snippet parameters.\n\nLibrary: search, select and Enter to insert. Ctrl+X moves to Scratch; Ctrl+R restores a fragment. Ctrl+M starts a move, Alt+arrows choose the destination, Ctrl+Enter commits.\n\nCtrl+S saves. Ctrl+Z/Y undo/redo. F7 connects a hub, F5 runs, F6 stops. The program stays a normal Python file."
        )
        self.push_screen(HelpDialog(text))

    def action_move(self):
        self.perform(self.session.begin_move)

    def action_previous_target(self):
        self.navigate(-1)

    def action_next_target(self):
        self.navigate(1)

    def navigate(self, step):
        editor = self.session.editor
        self.perform(
            lambda: (
                editor.navigate_move(step) if editor.moving else editor.sibling(step)
            )
        )

    def action_commit_move(self):
        self.perform(self.session.editor.commit_move)

    def action_cancel_move(self):
        self.perform(self.session.editor.cancel_move)

    def action_scratch(self):
        self.perform(self.session.to_scratch)

    def action_new_scratch(self):
        self.push_screen(
            EditDialog(
                "New Scratch fragment",
                lambda text: self.session.set_scratch(None, text),
                text="",
            ),
            self.refresh_views,
        )

    def action_restore(self):
        index = self.query_one("#scratch", OptionList).highlighted
        if index is not None:
            self.perform(lambda: self.session.restore_scratch(index))

    def action_upgrade(self):
        self.perform(self.session.upgrade_selected)

    def action_expand(self):
        self.perform(self.session.toggle_expansion)

    def action_fold(self):
        syntax = self.session.document.syntax
        node = self.session.editor.selection
        match = self.session.selected_match()
        span = match.span if match else syntax.spans[node]
        pair = (syntax.position(span.start)[0], syntax.position(span.end)[0])
        if pair in self.folded:
            self.folded.remove(pair)
        else:
            self.folded.add(pair)
        self.refresh_views()

    def action_connect(self):
        self.push_screen(
            EditDialog(
                "Connect hub (empty name: first available)",
                lambda values: self.connect(
                    values["name"], values["transport"], values["model"]
                ),
                fields=[
                    ("transport", "ble", "ble / usb / virtual"),
                    ("model", "inventor", "inventor / boost / technic (virtual)"),
                    ("name", "", "Bluetooth hub"),
                ],
            )
        )

    @work(group="connection", exclusive=True)
    async def connect(self, name, transport="ble", model="inventor"):
        try:
            from little_tinker_rig.pybricks.connection import Connection
            from little_tinker_rig.pybricks.virtual import VirtualConnection

            if self.connection:
                await self.connection.disconnect()
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            factory = VirtualConnection if transport == "virtual" else Connection
            options = {"model": model} if transport == "virtual" else {}
            self.connection = factory(
                lambda data: self.console_output(decoder.decode(data)), **options
            )
            await self.connection.connect(name or None, transport)
            self.notify("Hub connected")
        except Exception as error:
            self.notify(str(error), severity="error")

    def action_console(self):
        widget = self.query_one("#console", RichLog)
        widget.display = not widget.display

    def console_output(self, text):
        self.query_one("#console", RichLog).write(Text(text))
        if not self.query_one("#console").display:
            self.query_one("#status", Static).update(
                "New program output · F8 opens Console"
            )

    @work(group="run", exclusive=True)
    async def action_run(self):
        try:
            if self.connection is None:
                raise ValueError("Connect a hub with F7 first")
            self.session.project.save()
            await self.connection.run(self.session.project.path)
        except Exception as error:
            self.notify(str(error), severity="error")

    @work(group="stop", exclusive=True)
    async def action_stop(self):
        try:
            if self.connection:
                await self.connection.stop()
        except Exception as error:
            self.notify(str(error), severity="error")

    def action_quit(self):
        if self.session.project.dirty:
            self.push_screen(QuitDialog(), lambda leave: self.exit() if leave else None)
        else:
            self.exit()

    async def on_unmount(self):
        if self.connection:
            try:
                await self.connection.disconnect()
            except Exception as error:
                self.log.warning(f"Disconnect during shutdown: {error}")


def launch(path: Path, collections=()) -> int:
    Studio(path, collections).run()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LittleTinker Rig terminal editor")
    parser.add_argument("file", type=Path, nargs="?", default=Path("main.py"))
    return launch(parser.parse_args().file)
