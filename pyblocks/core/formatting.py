"""Canonical formatting through Black's supported command-line interface."""

import subprocess
import sys
from pathlib import Path

from .syntax import parse


def format_source(source: str, *, fragment: bool = False) -> str:
    """Return validated canonical source, independent of cwd configuration."""
    parse(source, fragment=fragment)
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "black",
                "--quiet",
                "--config",
                str(Path(__file__).with_name("black.toml")),
                "-",
            ],
            input=source,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError(
            "Formatting exceeded 30 seconds; source was not changed"
        ) from error
    if result.returncode:
        raise ValueError(f"Formatting failed: {result.stderr.strip()}")
    parse(result.stdout, fragment=fragment)
    return result.stdout
