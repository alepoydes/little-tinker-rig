"""Cancellable resource work; GUI objects only receive progress and results."""

from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal
from shiboken6 import isValid


class ResourceSignals(QObject):
    progress = Signal(int, int)
    ready = Signal(object, str)


class ResourceJob(QRunnable):
    def __init__(self, action):
        super().__init__()
        self.action = action
        self.cancelled = Event()
        self.signals = ResourceSignals()

    def _emit(self, name, *args):
        # Window teardown may delete the Qt sender before cancelled work exits.
        if not isValid(self.signals):
            return
        try:
            getattr(self.signals, name).emit(*args)
        except RuntimeError:
            if isValid(self.signals):
                raise

    def _progress(self, received, total):
        self._emit("progress", received, total)

    def run(self):
        try:
            result = self.action(
                progress=self._progress, cancelled=self.cancelled.is_set
            )
        except Exception as error:
            self._emit("ready", None, str(error) or type(error).__name__)
        else:
            self._emit("ready", result, "")
