"""Canonical formatting through Ruff's supported command-line interface."""

import subprocess
import sys
import sysconfig
from functools import lru_cache
from pathlib import Path
from shutil import which

from .syntax import parse


@lru_cache(maxsize=64)
def format_source(source: str, *, fragment: bool = False) -> str:
    """Return validated canonical source, independent of cwd configuration."""
    parse(source, fragment=fragment)
    if not source.strip():
        return ""
    executable = which("ruff", path=sysconfig.get_path("scripts"))
    command = [executable] if executable else [sys.executable, "-m", "ruff"]
    try:
        result = subprocess.run(
            command
            + [
                "format",
                "--quiet",
                "--config",
                str(Path(__file__).with_name("formatting.toml")),
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
