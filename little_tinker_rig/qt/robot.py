"""Qt signals adapt the shared hub worker to the desktop interface."""

from PySide6.QtCore import QObject, Signal

from little_tinker_rig.pybricks.worker import HubWorker


class Robot(QObject):
    output = Signal(str)
    failed = Signal(str)
    updated = Signal(object)
    busy_changed = Signal(bool)
    problem = Signal(object)
    program_started = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = HubWorker(
            output=self.output.emit,
            failed=self.failed.emit,
            updated=self.updated.emit,
            busy_changed=self.busy_changed.emit,
            problem=self.problem.emit,
            program_started=self.program_started.emit,
        )

    @property
    def info(self):
        return self.worker.info

    @property
    def connection(self):
        return self.worker.connection

    @property
    def operation(self):
        return self.worker.operation

    @property
    def thread(self):
        return self.worker.thread

    def connect_hub(self, name=None, transport="ble", model="inventor"):
        return self.worker.connect_hub(name, transport, model)

    def run_file(self, path, sources=None):
        return self.worker.run_file(path, sources)

    def upload_file(self, path, sources=None):
        return self.worker.upload_file(path, sources)

    def run_stored(self):
        return self.worker.run_stored()

    def start_monitor(self):
        return self.worker.start_monitor()

    def stop_program(self):
        return self.worker.stop_program()

    def drive(self, commands):
        return self.worker.drive(commands)

    def send(self, state):
        return self.worker.send(state)

    def configure(self, port, kind, value=None):
        return self.worker.configure(port, kind, value)

    def write_input(self, data):
        return self.worker.write_input(data)

    def disconnect_hub(self):
        return self.worker.disconnect_hub()

    def close(self):
        return self.worker.close()
