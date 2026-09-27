"""Route process output through a Qt signal before touching GUI widgets."""

from contextlib import contextmanager, redirect_stderr, redirect_stdout

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit, QWidget

from pyblocks.i18n import N_


class HubInput(QWidget):
    sent = Signal(bytes)

    def __init__(self):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.field = QLineEdit()
        self.field.setPlaceholderText(N_("Hub input · Enter sends a line"))
        self.field.installEventFilter(self)
        row.addWidget(self.field, 1)
        self.immediate = QCheckBox(N_("Send keys immediately"))
        self.immediate.setToolTip(
            N_(
                "Send keys only while this input has focus. Escape leaves keyboard control."
            )
        )
        row.addWidget(self.immediate)
        self.field.returnPressed.connect(self.send_line)
        self.setToolTip(
            N_("Program input for a Bluetooth or USB hub. Stop the port monitor first.")
        )

    def send_line(self):
        self.sent.emit((self.field.text() + "\r").encode("utf-8"))
        self.field.clear()

    def eventFilter(self, obj, event):
        if (
            event.type() in (event.Type.ShortcutOverride, event.Type.KeyPress)
            and self.immediate.isChecked()
        ):
            escape = event.key() == Qt.Key.Key_Escape
            interrupt = (
                event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_C
            )
            text = (
                event.text()
                if not event.modifiers()
                & (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.AltModifier
                    | Qt.KeyboardModifier.MetaModifier
                )
                else ""
            )
            if not (escape or interrupt or text):
                return False
            if event.type() == event.Type.ShortcutOverride:
                event.accept()
                return True
            if escape:
                self.immediate.setChecked(False)
            elif interrupt:
                self.sent.emit(b"\x03")
            else:
                self.sent.emit(text.encode("utf-8"))
            return True
        return super().eventFilter(obj, event)


class OutputStream(QObject):
    written = Signal(str)
    encoding = "utf-8"

    def write(self, text):
        if text:
            self.written.emit(text)
        return len(text)

    def flush(self):
        pass

    def isatty(self):
        return False


@contextmanager
def capture_output(receiver):
    # Install once for the GUI lifetime, not around individual async operations:
    # redirect_stdout/stderr are process-wide, including the hub worker thread.
    stream = OutputStream()
    stream.written.connect(receiver)
    with redirect_stdout(stream), redirect_stderr(stream):
        yield
