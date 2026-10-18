"""Debounced window checkpoints; locks distinguish crashed and live windows."""

import json
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QLockFile, QObject, QTimer
from PySide6.QtWidgets import QMessageBox

from little_tinker_rig.core.paths import personal_collection
from little_tinker_rig.core.project import atomic_write
from little_tinker_rig.i18n import tr


def recovery_directory():
    return personal_collection().parent / "recovery"


def lock_file(path):
    lock = QLockFile(str(path) + ".lock")
    lock.setStaleLockTime(0)
    return lock


class Recovery(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.path = recovery_directory() / f"{uuid4().hex}.json"
        self.lock = None
        self.previous = None
        self.reported_error = False
        self.closed = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(750)
        self.timer.timeout.connect(self.flush)

    def schedule(self):
        if not self.closed and not self.timer.isActive():
            self.timer.start()

    def flush(self):
        self.timer.stop()
        if self.closed:
            return False
        window = self.window
        if not window.documents.count():
            return True
        if window.documents.count() == 1 and window._unused_startup_placeholder():
            return True
        try:
            autosave_error = None
            try:
                window.example_workspaces.autosave()
                window.lessons.autosave()
            except (OSError, ValueError) as error:
                autosave_error = error
            data = {
                "format": 1,
                "active": window.documents.currentIndex(),
                "documents": [
                    window.documents.widget(i).checkpoint()
                    for i in range(window.documents.count())
                ],
            }
            if data == self.previous:
                if autosave_error:
                    raise autosave_error
                return True
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.lock is None:
                self.lock = lock_file(self.path)
                if not self.lock.tryLock(0):
                    self.lock = None
                    raise OSError("Could not lock the recovery file")
            atomic_write(self.path, json.dumps(data, ensure_ascii=False))
            self.previous = data
            if autosave_error:
                raise autosave_error
            self.reported_error = False
            return True
        except (OSError, ValueError) as error:
            if not self.reported_error:
                self.reported_error = True
                window.error(
                    tr("Could not save recovery data: {detail}", detail=str(error))
                )
            return False

    def offer(self):
        if self.closed:
            return
        for path in sorted(self.path.parent.glob("*.json")):
            if path == self.path:
                continue
            lock = lock_file(path)
            if not lock.tryLock(0):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data["format"] != 1 or not isinstance(data["documents"], list):
                    raise ValueError("Unsupported recovery format")
                names = "\n".join(item["path"] for item in data["documents"])
                answer = QMessageBox.question(
                    self.window,
                    tr("Recover work"),
                    tr(
                        "An earlier window did not close normally. Restore its documents and Scratch?\n\n{files}",
                        files=names,
                    ),
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    pages = []
                    for item in data["documents"]:
                        page = self.window.open_document(Path(item["path"]))
                        if item.get("lesson_project"):
                            page.lesson_project = self.window.lessons.restore(
                                item["lesson_project"]
                            )
                        if page.dirty and (
                            page.text != item["source"]
                            or list(page.session.document.state.scratch)
                            != item["scratch"]
                        ):
                            original = Path(item["path"])
                            opened = {
                                self.window.documents.widget(i).session.project.path
                                for i in range(self.window.documents.count())
                            }
                            index = 1
                            while True:
                                copy = original.with_name(
                                    f"{original.stem}_recovered_{index}.py"
                                )
                                if copy not in opened and not copy.exists():
                                    break
                                index += 1
                            page = self.window.open_document(copy)
                            item = dict(
                                item,
                                disk_hash=None,
                                workspace_hash=None,
                                saved_source="",
                                saved_scratch=[],
                            )
                        page.restore(item)
                        pages.append(page)
                    if pages:
                        self.window.documents.setCurrentWidget(
                            pages[min(data["active"], len(pages) - 1)]
                        )
                    self.window.document_changed()
                    if pages and self.window.pages.currentIndex() == 5:
                        self.window.set_mode(0)
                    if self.flush():
                        path.unlink()
                elif answer == QMessageBox.StandardButton.No:
                    path.unlink()
            except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
                self.window.error(
                    tr("Could not restore recovery data: {detail}", detail=str(error))
                )
            finally:
                lock.unlock()

    def close(self):
        self.timer.stop()
        self.path.unlink(missing_ok=True)
        self.closed = True
        if self.lock:
            self.lock.unlock()
            self.lock = None
