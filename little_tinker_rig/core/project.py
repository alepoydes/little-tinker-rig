"""Plain Python files with optional, independent workspace metadata."""

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from little_tinker_rig.i18n import tr

from .document import Document, State
from .source_file import atomic_write as atomic_write
from .source_file import decode_source, utf8_source


class ExternalChangeError(ValueError):
    """Saving requires a decision about a file changed since its last read."""

    def __init__(self, path, *, workspace=False):
        self.path = path
        super().__init__(
            tr("Workspace changed outside LittleTinker Rig: {path}", path=path)
            if workspace
            else tr("File changed outside LittleTinker Rig: {path}", path=path)
        )


class Project:
    """File ownership and external-change detection; editor state stays separate."""

    def __init__(self, path: Path, *, allow_draft: bool = False):
        self.path = path.resolve()
        self.encoding = "utf-8"
        source = ""
        self._disk_hash = None
        if self.path.exists():
            data = self.path.read_bytes()
            source, self.encoding = decode_source(data)
            self._disk_hash = hashlib.sha256(data).hexdigest()
        self.collections: list[Path] = []
        self.pins: dict[str, str] = {}
        self.example_attempt = None
        scratch = ()
        self._workspace_hash = None
        if self.workspace_path.exists():
            data = self.workspace_path.read_bytes()
            self._workspace_hash = hashlib.sha256(data).hexdigest()
            metadata = json.loads(data.decode("utf-8"))
            if not isinstance(metadata, dict) or metadata.get("format") != 1:
                raise ValueError("Unsupported workspace format")
            items = metadata.get("scratch", [])
            if not isinstance(items, list) or not all(
                isinstance(item, str) for item in items
            ):
                raise ValueError("Scratch must be a list of text fragments")
            scratch = tuple(items)
            collections = metadata.get("collections", [])
            pins = metadata.get("pins", {})
            if not isinstance(collections, list) or not all(
                isinstance(path, str) for path in collections
            ):
                raise ValueError("Collections must be a list of directory paths")
            if not isinstance(pins, dict) or not all(
                isinstance(name, str) and isinstance(version, str)
                for name, version in pins.items()
            ):
                raise ValueError("Pins must map collection names to version strings")
            self.collections = [(self.path.parent / p).resolve() for p in collections]
            self.pins = pins
            self.example_attempt = metadata.get("example_attempt")
            if self.example_attempt is not None and not isinstance(
                self.example_attempt, str
            ):
                raise ValueError("Invalid example attempt")
        try:
            self.document = Document(source, scratch)
        except SyntaxError:
            if not allow_draft:
                raise
            self.document = Document("", scratch, draft=source)
        self._saved = (
            State(source, scratch) if self.draft is not None else self.document.state
        )

    @property
    def draft(self):
        return self.document.state.draft

    @draft.setter
    def draft(self, text):
        self.document.set_draft(text)

    @property
    def workspace_path(self) -> Path:
        path = self.path.with_suffix(self.path.suffix + ".ltr.json")
        previous = self.path.with_suffix(self.path.suffix + ".pyblocks.json")
        return previous if not path.exists() and previous.exists() else path

    @property
    def dirty(self) -> bool:
        return self.state != self._saved or not self.path.exists()

    @property
    def state(self) -> State:
        return State(
            self.draft if self.draft is not None else self.document.state.source,
            self.document.state.scratch,
        )

    def text_dirty(self, source: str) -> bool:
        return State(source, self.document.state.scratch) != self._saved or (
            not self.path.exists() and bool(source or self.document.state.scratch)
        )

    def checkpoint(self, source: str) -> dict:
        """Keep the original save baseline, so recovery cannot hide disk conflicts."""
        return {
            "path": str(self.path),
            "source": source,
            "committed": self.document.state.source,
            "scratch": list(self.document.state.scratch),
            "collections": [str(p) for p in self.collections],
            "pins": self.pins,
            "encoding": self.encoding,
            "example_attempt": self.example_attempt,
            "disk_hash": self._disk_hash,
            "workspace_hash": self._workspace_hash,
            "saved_source": self._saved.source,
            "saved_scratch": list(self._saved.scratch),
        }

    @staticmethod
    def validate_checkpoint(checkpoint: dict) -> None:
        """Check a recovery item without changing a live document."""
        if not isinstance(checkpoint, dict):
            raise ValueError("Invalid recovery document")
        for key in ("source", "committed", "saved_source", "encoding"):
            if not isinstance(checkpoint[key], str):
                raise ValueError("Invalid recovery text")
        for key in ("scratch", "saved_scratch", "collections"):
            if not isinstance(checkpoint[key], list) or not all(
                isinstance(item, str) for item in checkpoint[key]
            ):
                raise ValueError("Invalid recovery workspace")
        if not isinstance(checkpoint["pins"], dict) or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in checkpoint["pins"].items()
        ):
            raise ValueError("Invalid recovery pins")
        for key in ("disk_hash", "workspace_hash"):
            if (
                key not in checkpoint
                or checkpoint[key] is not None
                and not isinstance(checkpoint[key], str)
            ):
                raise ValueError("Invalid recovery baseline")
        if checkpoint.get("example_attempt") is not None and not isinstance(
            checkpoint["example_attempt"], str
        ):
            raise ValueError("Invalid recovery example attempt")
        Document(checkpoint["committed"], tuple(checkpoint["scratch"]))

    def restore(self, checkpoint: dict) -> None:
        """Restore memory only; subsequent saves still check the pre-crash files."""
        self.validate_checkpoint(checkpoint)
        prepare, self.document.prepare = self.document.prepare, None
        try:
            self.document.commit(checkpoint["committed"], tuple(checkpoint["scratch"]))
        finally:
            self.document.prepare = prepare
        self.draft = (
            checkpoint["source"]
            if checkpoint["source"] != self.document.state.source
            else None
        )
        self.collections = [Path(p) for p in checkpoint["collections"]]
        self.pins = checkpoint["pins"]
        self.encoding = checkpoint["encoding"]
        self.example_attempt = checkpoint.get("example_attempt")
        self._disk_hash = checkpoint["disk_hash"]
        self._workspace_hash = checkpoint["workspace_hash"]
        self._saved = State(
            checkpoint["saved_source"], tuple(checkpoint["saved_scratch"])
        )

    def _hash(self, path: Path) -> str | None:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

    def save_collections(self) -> None:
        """Persist library connections independently of unsaved program/scratch text."""
        if self._hash(self.workspace_path) != self._workspace_hash:
            raise ExternalChangeError(self.workspace_path, workspace=True)
        metadata = (
            json.loads(self.workspace_path.read_text(encoding="utf-8"))
            if self.workspace_path.exists()
            else {"format": 1, "scratch": list(self._saved.scratch), "pins": self.pins}
        )
        metadata["collections"] = [
            os.path.relpath(p, self.path.parent) for p in self.collections
        ]
        text = json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
        atomic_write(self.workspace_path, text)
        self._workspace_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    def save(self) -> None:
        """Refuse to overwrite a file changed externally since opening/saving."""
        if self._hash(self.path) != self._disk_hash:
            raise ExternalChangeError(self.path)
        if self._hash(self.workspace_path) != self._workspace_hash:
            raise ExternalChangeError(self.workspace_path, workspace=True)
        source = utf8_source(self.state.source)
        if self.draft is not None:
            self.draft = source
        elif source != self.document.state.source:
            self.document.commit(source)
        state = self.state
        metadata = {
            "format": 1,
            "scratch": list(state.scratch),
            "collections": [
                os.path.relpath(p, self.path.parent) for p in self.collections
            ],
            "pins": self.pins,
        }
        if self.example_attempt:
            metadata["example_attempt"] = self.example_attempt
        keep_workspace = bool(
            state.scratch
            or self.collections
            or self.pins
            or self.example_attempt
            or self.workspace_path.exists()
        )

        def write_workspace(scratch):
            text = (
                json.dumps(
                    dict(metadata, scratch=list(scratch)), ensure_ascii=False, indent=2
                )
                + "\n"
            )
            atomic_write(self.workspace_path, text)
            self._workspace_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        if keep_workspace:
            # A recovery superset protects moves in both directions if saving
            # either file fails. Interrupted saves may leave extra copies.
            missing = Counter(self._saved.scratch) - Counter(state.scratch)
            write_workspace((*state.scratch, *missing.elements()))
        atomic_write(self.path, state.source)
        self.encoding = "utf-8"
        self._disk_hash = hashlib.sha256(state.source.encode("utf-8")).hexdigest()
        if keep_workspace:
            write_workspace(state.scratch)
        self._saved = state
