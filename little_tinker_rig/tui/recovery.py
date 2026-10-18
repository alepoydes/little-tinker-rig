"""Crash checkpoints for the terminal editor, independent of Qt."""

import json
import os
from pathlib import Path
from uuid import uuid4

from little_tinker_rig.core.paths import personal_collection
from little_tinker_rig.core.source_file import SourceFile, atomic_write


def recovery_directory():
    return personal_collection().parent / "tui-recovery"


def _lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return stream
    except BaseException:
        stream.close()
        raise


def _unlock(stream):
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    stream.close()


class Recovery:
    def __init__(self):
        self.directory = recovery_directory()
        self.path = self.directory / f"{uuid4().hex}.json"
        self.lock = None
        self.previous = None

    def flush(self, file, text, cursor):
        if not file.dirty(text):
            self.path.unlink(missing_ok=True)
            self.previous = None
            return
        data = {
            "format": 1,
            "path": str(file.path) if file.path else None,
            "text": text,
            "baseline_source": file.source,
            "baseline_encoding": file.encoding,
            "baseline_digest": file.digest.hex() if file.digest else None,
            "cursor": list(cursor),
        }
        if data == self.previous and self.path.exists():
            return
        if self.lock is None:
            self.lock = _lock(self.path.with_suffix(".lock"))
        atomic_write(self.path, json.dumps(data, ensure_ascii=False))
        self.previous = data

    def stale(self):
        if not self.directory.exists():
            return
        for path in sorted(self.directory.glob("*.json")):
            if path == self.path:
                continue
            try:
                lock = _lock(path.with_suffix(".lock"))
            except OSError:
                continue
            if path.exists():
                yield path, lock
            else:
                _unlock(lock)

    @staticmethod
    def read(path):
        data = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or data.get("format") != 1
            or (
                data.get("path") is not None
                and (
                    not isinstance(data["path"], str)
                    or not Path(data["path"]).is_absolute()
                )
            )
            or not isinstance(data.get("text"), str)
            or not isinstance(data.get("baseline_source"), str)
            or not isinstance(data.get("baseline_encoding"), str)
            or not isinstance(data.get("cursor"), list)
            or len(data["cursor"]) != 2
            or any(type(number) is not int or number < 0 for number in data["cursor"])
        ):
            raise ValueError("Invalid terminal recovery data")
        digest = data.get("baseline_digest")
        if digest is not None:
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError("Invalid terminal recovery digest")
            try:
                digest = bytes.fromhex(digest)
            except ValueError as error:
                raise ValueError("Invalid terminal recovery digest") from error
        file = SourceFile()
        file.path = Path(data["path"]) if data["path"] else None
        file.source = data["baseline_source"]
        file.encoding = data["baseline_encoding"]
        file.digest = digest
        return file, data["text"], tuple(data["cursor"])

    @staticmethod
    def release(lock):
        _unlock(lock)

    def close(self, *, remove):
        try:
            if remove:
                self.path.unlink(missing_ok=True)
        finally:
            if self.lock is not None:
                _unlock(self.lock)
                self.lock = None
        if remove:
            self.path.with_suffix(".lock").unlink(missing_ok=True)
