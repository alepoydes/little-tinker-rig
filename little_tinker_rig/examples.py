"""Locate the single examples tree in a checkout or installed distribution."""

from pathlib import Path


def examples_directory():
    package = Path(__file__).resolve().parent
    bundled = package / "examples"
    return bundled if bundled.is_dir() else package.parent / "examples"
