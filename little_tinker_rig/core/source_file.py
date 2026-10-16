"""Plain source files: UTF-8 saves and external-change protection."""

import hashlib
import io
import os
import re
import tempfile
import tokenize
from pathlib import Path

from little_tinker_rig.i18n import tr


def utf8_source(source: str) -> str:
    """Normalize a Python encoding declaration, including in invalid drafts."""
    lines = source.removeprefix("\ufeff").split("\n", 2)
    for index, line in enumerate(lines[:2]):
        cookie = re.match(r"[ \t\f]*#.*?coding[:=][ \t]*([-a-zA-Z0-9_.]+)", line)
        if cookie:
            start, end = cookie.span(1)
            lines[index] = line[:start] + "utf-8" + line[end:]
            break
        if not re.match(r"[ \t\f]*(?:#|\r?$)", line):
            break
    return "\n".join(lines)


def atomic_write(path: Path, text: str | bytes, encoding: str = "utf-8") -> None:
    """Replace one file atomically, preserving its permission bits."""
    path = path.resolve()
    mode = path.stat().st_mode & 0o777 if path.exists() else None
    temporary = None
    try:
        options = (
            {"mode": "wb"}
            if isinstance(text, bytes)
            else {"mode": "w", "encoding": encoding, "newline": ""}
        )
        with tempfile.NamedTemporaryFile(
            **options, dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            temporary.chmod(mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class SourceFile:
    def __init__(self, path=None):
        self.path = Path(path).expanduser().resolve() if path is not None else None
        raw = self.path.read_bytes() if self.path and self.path.exists() else None
        self.encoding = (
            tokenize.detect_encoding(io.BytesIO(raw).readline)[0]
            if raw is not None
            else "utf-8"
        )
        self.source = raw.decode(self.encoding) if raw is not None else ""
        self.digest = hashlib.sha256(raw).digest() if raw is not None else None

    def dirty(self, text):
        return text != self.source or bool(text and self.digest is None)

    def save(self, text, path=None, *, overwrite=False):
        target = Path(path).expanduser().resolve() if path is not None else self.path
        if target is None:
            raise ValueError(tr("Choose a file name first"))
        raw = target.read_bytes() if target.exists() else None
        if target == self.path:
            digest = hashlib.sha256(raw).digest() if raw is not None else None
            if digest != self.digest:
                raise ValueError(
                    tr(
                        "File changed outside LittleTinker Rig; reopen it or save to another path"
                    )
                )
        elif raw is not None and not overwrite:
            raise FileExistsError(tr("The file already exists. Replace it?"))
        text = utf8_source(text)
        data = text.encode("utf-8")
        atomic_write(target, data)
        self.path, self.source = target, text
        self.encoding = "utf-8"
        self.digest = hashlib.sha256(data).digest()
