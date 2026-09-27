"""External LDraw libraries: verified ZIP cache and lazy member reads.

Downloads are atomic and shared across workers. Only referenced members are read;
neither the official library nor an offline subset is extracted to a directory.
"""

import hashlib
import json
import tempfile
import threading
from concurrent.futures import CancelledError
from contextlib import AbstractContextManager
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

from .paths import parts_cache, resource

_download_lock = threading.Lock()
MAX_ARCHIVE = 512 * 1024**2


def validate_reference(spec):
    if not isinstance(spec, dict) or not all(
        isinstance(spec.get(k), str) and spec[k]
        for k in ("id", "version", "url", "sha256")
    ):
        raise ValueError("A parts library needs id, version, URL and SHA-256")
    if len(spec["sha256"]) != 64 or any(
        c not in "0123456789abcdef" for c in spec["sha256"]
    ):
        raise ValueError("Invalid library SHA-256")
    if urlparse(spec["url"]).scheme != "https" or not urlparse(spec["url"]).hostname:
        raise ValueError("A library download needs an HTTPS URL")


def check_cancelled(cancelled):
    if cancelled and cancelled():
        raise CancelledError("Parts loading cancelled")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_file(path, dependencies):
    data = path.read_bytes() if path.is_file() else None
    dependencies[path] = hashlib.sha256(data).hexdigest() if data is not None else None
    return data


def resolve_library(
    root, reference, *, download=False, local=None, progress=None, cancelled=None
):
    if isinstance(reference, str):
        return resource(root, reference)
    validate_reference(reference)
    destination = parts_cache() / (reference["sha256"] + ".zip")
    while not _download_lock.acquire(timeout=0.1):
        check_cancelled(cancelled)
    temporary = None
    try:
        check_cancelled(cancelled)
        if (
            local is None
            and destination.is_file()
            and digest(destination) == reference["sha256"]
        ):
            return destination
        if local is None and not download:
            raise FileNotFoundError(
                "Parts are not cached; download the library or open its ZIP archive"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if local is not None:
            source = Path(local).open("rb")
            total = Path(local).stat().st_size
        else:
            source = urlopen(
                Request(
                    reference["url"], headers={"User-Agent": "PyBlocks-Studio/0.1"}
                ),
                timeout=30,
            )
            total = int(source.headers.get("Content-Length", 0))
        with (
            source,
            tempfile.NamedTemporaryFile(
                dir=destination.parent, suffix=".part", delete=False
            ) as target,
        ):
            temporary = Path(target.name)
            hasher = hashlib.sha256()
            received = 0
            while chunk := source.read(1024 * 1024):
                check_cancelled(cancelled)
                received += len(chunk)
                if received > MAX_ARCHIVE:
                    raise ValueError("The parts archive is too large")
                target.write(chunk)
                hasher.update(chunk)
                if progress:
                    progress(received, total)
        if hasher.hexdigest() != reference["sha256"]:
            raise ValueError(
                f"Parts archive does not match {reference['id']} {reference['version']}. The download may have changed; use the matching local ZIP or an offline project."
            )
        with PartLibrary(temporary):
            pass
        check_cancelled(cancelled)
        temporary.replace(destination)
        return destination
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
        _download_lock.release()


def member_name(name):
    name = name.replace("\\", "/")
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or ":" in name:
        raise ValueError(f"Invalid LDraw resource: {name}")
    return path.as_posix().lower()


class PartLibrary(AbstractContextManager):
    def __init__(self, path, *, dependencies=None):
        self.path = Path(path)
        self.archive = None
        self.members = {}
        self.used = {}
        self.dependencies = dependencies if dependencies is not None else {}
        if self.path.is_dir():
            return
        try:
            self.archive = ZipFile(self.path)
            infos = self.archive.infolist()
            if len(infos) > 100000 or sum(i.file_size for i in infos) > 2 * 1024**3:
                raise ValueError("The parts library is too large")
            prefix = (
                "ldraw/"
                if any(i.filename.lower() == "ldraw/ldconfig.ldr" for i in infos)
                else ""
            )
            for info in infos:
                name = member_name(info.filename)
                if info.is_dir() or (prefix and not name.startswith(prefix)):
                    continue
                name = name.removeprefix(prefix)
                if name in self.members or info.file_size > 16 * 1024**2:
                    raise ValueError(f"Invalid or duplicate library member: {name}")
                self.members[name] = info
            if not any(name.startswith(("parts/", "p/")) for name in self.members):
                raise ValueError("The ZIP contains no LDraw parts")
        except (BadZipFile, ValueError, OSError) as error:
            self.close()
            raise ValueError(f"Invalid parts library: {error}") from error

    def read(self, name):
        original = name
        name = member_name(name)
        if name in self.used:
            return self.used[name]
        if self.archive:
            if name not in self.members:
                return None
            data = self.archive.read(self.members[name])
        else:
            path = resource(self.path, original)
            data = read_file(path, self.dependencies)
            if data is None:
                return None
        self.used[name] = data
        return data

    def close(self):
        if self.archive:
            self.archive.close()

    def __exit__(self, *args):
        self.close()


def subset(model, library, reference=None):
    """Return only the model's library dependencies, colors and attribution."""
    import io
    from zipfile import ZIP_DEFLATED

    from .ldraw import LDraw

    with LDraw(model, library) as reader:
        reader.scene()
        parts = reader.library
        for name in (
            "CAreadme.txt",
            "CAlicense.txt",
            "CAlicense4.txt",
            "Readme.txt",
            "sources.json",
        ):
            parts.read(name)
        output = io.BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            for name, data in sorted(parts.used.items()):
                archive.writestr(name, data)
            if reference:
                archive.writestr("source.json", json.dumps(reference, indent=2) + "\n")
        return output.getvalue()
