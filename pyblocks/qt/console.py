"""Route process output through a Qt signal before touching GUI widgets."""

from contextlib import contextmanager, redirect_stderr, redirect_stdout

from PySide6.QtCore import QObject, Signal


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
