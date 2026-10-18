"""Persistent example attempts with ordinary Python files and workspace metadata."""

import json
import shutil
from pathlib import Path
from time import time_ns
from uuid import uuid4

from little_tinker_rig.pybricks.program import Program

from .paths import personal_collection, resource
from .project import ExternalChangeError, atomic_write
from .timestamps import valid_unix_ns


def attempts_directory():
    return personal_collection().parent / "examples"


class ExampleWork:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.manifest = self.root / "work.json"
        self.baseline = self.manifest.read_text(encoding="utf-8")
        self.data = json.loads(self.baseline)
        if (
            not isinstance(self.data, dict)
            or self.data.get("format") != 1
            or not isinstance(self.data.get("example"), str)
            or not valid_unix_ns(self.data.get("opened"))
            or not valid_unix_ns(self.data.get("created", self.data.get("opened")))
            or not isinstance(self.data.get("files"), list)
            or not all(isinstance(p, str) for p in self.data["files"])
            or self.data.get("entry") not in self.data["files"]
        ):
            raise ValueError("Invalid example work")

    @classmethod
    def create(cls, source, examples):
        source = Path(source).resolve()
        identity = source.relative_to(examples.resolve()).as_posix()
        root = attempts_directory() / uuid4().hex
        program = Program(source)
        try:
            shutil.copytree(program.directory.name, root)
            entry = root / source.name
            data = {
                "format": 1,
                "example": identity,
                "opened": time_ns(),
                "entry": str(entry),
                "files": [
                    str(root / path.relative_to(source.parent))
                    for path in program.sources
                ],
            }
            data["created"] = data["opened"]
            atomic_write(root / "work.json", json.dumps(data, ensure_ascii=False))
            return cls(root)
        except BaseException:
            shutil.rmtree(root, ignore_errors=True)
            raise
        finally:
            program.cleanup()

    @classmethod
    def all(cls):
        works = []
        for path in attempts_directory().glob("*/work.json"):
            try:
                works.append(cls(path.parent))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return sorted(works, key=lambda work: work.data["opened"], reverse=True)

    @property
    def identity(self):
        return self.root.name

    @property
    def entry(self):
        return Path(self.data["entry"])

    def owns(self, path):
        return str(path) in self.data["files"] or path.is_relative_to(self.root)

    def remember(self, path):
        if str(path) not in self.data["files"]:
            self.data["files"].append(str(path))

    def save(self):
        text = json.dumps(self.data, ensure_ascii=False)
        if text == self.baseline:
            return
        if self.manifest.read_text(encoding="utf-8") != self.baseline:
            raise ExternalChangeError(self.manifest)
        atomic_write(self.manifest, text)
        self.baseline = text

    def update(self, **changes):
        previous = self.data
        self.data = dict(previous, **changes)
        try:
            self.save()
        except BaseException:
            self.data = previous
            raise

    def touch(self):
        self.update(opened=time_ns())

    def source(self, examples):
        return resource(examples, self.data["example"])

    def relocated(self, paths):
        self.update(
            entry=str(paths.get(self.entry, self.entry)),
            files=[str(paths.get(Path(p), Path(p))) for p in self.data["files"]],
        )
