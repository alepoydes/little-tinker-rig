"""Small keyboard dialogs shared by terminal file and hub actions."""

from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from little_tinker_rig.i18n import tr


class Form(ModalScreen):
    DEFAULT_CSS = """
    Form { align: center middle; }
    Form > Vertical { width: 80%; max-width: 95; height: auto; max-height: 90%; border: round $accent; padding: 0 2; background: $surface; }
    Form VerticalScroll { height: auto; max-height: 50vh; }
    Form Label { margin-top: 1; }
    Form Horizontal { height: auto; margin-top: 1; align-horizontal: right; }
    Form Button { margin-left: 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+enter", "accept", show=False),
    ]

    def __init__(self, title, fields=(), *, text="", accept=None):
        super().__init__()
        self.heading, self.fields, self.text = title, fields, text
        self.accept = accept or tr("Apply")

    def compose(self):
        with Vertical():
            yield Label(self.heading)
            with VerticalScroll():
                if self.text:
                    yield Static(self.text, markup=False)
                for key, label, value, options in self.fields:
                    yield Label(label)
                    if options is None:
                        yield Input(value, id=key)
                    else:
                        yield Select(options, value=value, allow_blank=False, id=key)
            with Horizontal():
                yield Button(self.accept, id="accept", variant="primary")
                yield Button(tr("Cancel"), id="cancel")

    def action_cancel(self):
        self.dismiss(None)

    def action_accept(self):
        self.dismiss({key: self.query_one(f"#{key}").value for key, *_ in self.fields})

    @on(Button.Pressed)
    def button(self, event):
        event.stop()
        if event.button.id == "accept":
            self.action_accept()
        else:
            self.action_cancel()

    @on(Input.Submitted)
    def submitted(self):
        self.action_accept()


class Unsaved(ModalScreen):
    DEFAULT_CSS = """
    Unsaved { align: center middle; }
    Unsaved > Vertical { width: 70; height: auto; border: round $warning; padding: 1 2; background: $surface; }
    Unsaved Horizontal { height: auto; margin-top: 1; }
    Unsaved Button { margin-right: 1; }
    """
    BINDINGS = [Binding("escape", "cancel", show=False)]

    def compose(self):
        with Vertical():
            yield Static(tr("Save changes before continuing?"))
            with Horizontal():
                yield Button(tr("Save"), id="save", variant="primary")
                yield Button(tr("Discard"), id="discard", variant="error")
                yield Button(tr("Cancel"), id="cancel")

    def action_cancel(self):
        self.dismiss("cancel")

    @on(Button.Pressed)
    def button(self, event):
        self.dismiss(event.button.id)
