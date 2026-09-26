"""User-owned libraries are independent of programs and installation paths."""

from pathlib import Path, PurePosixPath

from platformdirs import user_cache_path, user_data_path


def resource(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("A resource must have a relative POSIX path")
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or ":" in name:
        raise ValueError(f"Resource escapes its package: {name}")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Resource escapes its package: {name}")
    return path


def parts_cache():
    return user_cache_path("pyblocks-studio", appauthor=False) / "ldraw"


def personal_collection():
    directory = user_data_path("pyblocks-studio", appauthor=False)
    if not directory.is_absolute():
        raise ValueError("The user data directory must be an absolute path")
    return (directory / "blocks").resolve()
