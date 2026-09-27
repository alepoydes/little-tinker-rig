"""Archive a collection before starting its next version; definitions stay static."""

import re
import shutil
import tempfile
import tomllib
from pathlib import Path

from .project import atomic_write
from .snippets import load_collection


def next_version(directory: Path, version: str, validate=None):
    """Preserve the saved version and advance its manifest, without editing modules."""
    directory = directory.resolve()
    manifest_path = directory / "collection.toml"
    manifest = manifest_path.read_text(encoding="utf-8")
    parsed = tomllib.loads(manifest)
    old = parsed["collection"]["version"]

    def number(value):
        if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", value):
            raise ValueError("Use a version of the form MAJOR.MINOR.PATCH")
        return tuple(map(int, value.split(".")))

    if number(version) <= number(old):
        raise ValueError(
            "The new collection version must be greater than the current version"
        )
    if any((directory / ".drafts").rglob("*.json")):
        raise ValueError(
            "Save or discard all collection drafts before starting a new version"
        )
    load_collection(directory)
    archive = directory / "history" / old
    if archive.exists():
        raise ValueError(f"Version {old} already has an archive")
    # Only the collection header changes; preserve other manifest sections.
    header = re.search(r"(?m)^\[collection\][^\n]*\n([^\[]*)", manifest)
    if header is None:
        raise ValueError("Missing collection header")
    updated, count = re.subn(
        r"(?m)^\s*version\s*=\s*(['\"]).*?\1[^\n]*",
        f'version = "{version}"',
        header.group(),
        count=1,
    )
    if count != 1:
        raise ValueError("Missing collection version")
    updated = manifest[: header.start()] + updated + manifest[header.end() :]
    updated += f'\n[[history]]\nversion = "{old}"\npath = "history/{old}"\n'
    histories = [
        (directory / item["path"]).resolve() for item in parsed.get("history", ())
    ]

    def modules():
        return {
            p.relative_to(directory): p.read_bytes()
            for p in directory.rglob("*.py")
            if not any(
                part.startswith(".") or part in {"history", "__pycache__"}
                for part in p.relative_to(directory).parts
            )
            and not any(p.resolve().is_relative_to(root) for root in histories)
        }

    originals = modules()
    with tempfile.TemporaryDirectory(
        prefix=".ltr-version-", dir=directory.parent
    ) as temporary:
        candidate = Path(temporary) / "collection"
        shutil.copytree(
            directory, candidate, ignore=shutil.ignore_patterns(".*", "__pycache__")
        )
        snapshot = candidate / "history" / old
        snapshot.mkdir(parents=True)
        for name, data in originals.items():
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (snapshot / "snapshot.toml").write_text(manifest, encoding="utf-8")
        (candidate / "collection.toml").write_text(updated, encoding="utf-8")
        snippets = load_collection(candidate)
        if validate:
            validate(directory, snippets)
        if (
            manifest_path.read_text(encoding="utf-8") != manifest
            or modules() != originals
        ):
            raise ValueError("Collection changed while preparing its next version")
        archive.parent.mkdir(exist_ok=True)
        snapshot.rename(archive)
        try:
            atomic_write(manifest_path, updated)
        except OSError:
            shutil.rmtree(archive)
            raise
    return load_collection(directory)
