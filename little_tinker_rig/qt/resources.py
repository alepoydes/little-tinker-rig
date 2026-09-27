"""Cancellable resource work; GUI objects only receive progress and results."""

from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal


class ResourceSignals(QObject):
    progress = Signal(int, int)
    ready = Signal(object, str)


class ResourceJob(QRunnable):
    def __init__(self, action):
        super().__init__()
        self.action = action
        self.cancelled = Event()
        self.signals = ResourceSignals()

    def run(self):
        try:
            result = self.action(
                progress=self.signals.progress.emit, cancelled=self.cancelled.is_set
            )
        except Exception as error:
            self.signals.ready.emit(None, str(error) or type(error).__name__)
        else:
            self.signals.ready.emit(result, "")
