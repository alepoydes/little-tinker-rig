"""Python text editing with static completion, independent of block sessions."""

import asyncio

from textual import on, work
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, TextArea
from textual.widgets.option_list import Option

from little_tinker_rig.core.completion import analyze
from little_tinker_rig.i18n import tr

from .dialogs import Form


class Completions(ModalScreen):
    DEFAULT_CSS = """
    Completions { align: center middle; }
    Completions > Vertical { width: 65; height: auto; max-height: 65%; border: round $accent; background: $surface; }
    Completions OptionList { height: auto; max-height: 18; }
    """
    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, words):
        super().__init__()
        self.words = words

    def compose(self):
        with Vertical():
            yield Label(tr("Python completion"))
            yield OptionList(*(Option(name, id=name) for name, _ in self.words))

    def action_cancel(self):
        self.dismiss(None)

    @on(OptionList.OptionSelected)
    def chosen(self, event):
        self.dismiss(event.option.id)


class PythonEditor(TextArea):
    BINDINGS = [
        Binding("ctrl+space", "complete", show=False),
        Binding("f1", "help", show=False),
    ]

    def __init__(self):
        super().__init__(
            language="python",
            show_line_numbers=True,
            soft_wrap=False,
            tab_behavior="indent",
            id="editor",
        )
        self.path = None
        self.assistance = None
        self.indent_width = 4

    def action_complete(self):
        self.assistance = self.assist("complete")

    def action_help(self):
        self.assistance = self.assist("help")

    def cancel_assistance(self):
        if self.assistance is not None:
            self.assistance.cancel()

    @work(group="assistance", exclusive=True)
    async def assist(self, mode):
        source, cursor, path = self.text, self.cursor_location, self.path
        try:
            result = await asyncio.to_thread(
                analyze, source, path, cursor[0] + 1, cursor[1], mode
            )
        except Exception as error:
            self.app.notify(
                tr("Python assistance failed: {error}", error=str(error)),
                severity="error",
            )
            return
        if (self.text, self.cursor_location, self.path) != (
            source,
            cursor,
            path,
        ) or not self.has_focus:
            return
        if result.words:
            word = await self.app.push_screen_wait(Completions(result.words))
            if word and (self.text, self.cursor_location, self.path) == (
                source,
                cursor,
                path,
            ):
                row, col = cursor
                start = col - dict(result.words)[word]
                line = self.document.get_line(row)
                end = col
                while end < len(line) and ("a" + line[end]).isidentifier():
                    end += 1
                if word.endswith("=") and line[end : end + 1] == "=":
                    end += 1
                self.replace(
                    word, (row, start), (row, end), maintain_selection_offset=False
                )
                self.move_cursor((row, start + len(word)))
        else:
            text = "\n\n".join(
                filter(None, (result.signature, result.parameter, result.description))
            )
            await self.app.push_screen_wait(
                Form(
                    tr("Python help"),
                    text=text or tr("No Python suggestions here"),
                    accept=tr("Close"),
                )
            )
