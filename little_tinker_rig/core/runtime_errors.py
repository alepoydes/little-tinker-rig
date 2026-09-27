"""Tracebacks refer to an execution snapshot, never the current editor revision."""

import re
from dataclasses import dataclass
from pathlib import Path

from little_tinker_rig.i18n import N_, tr

from .helpers import helper_section

FRAME = re.compile(r'^\s*File "([^"]+)", line (\d+)(?:, in (.*))?$')
EXCEPTION = re.compile(r"^([A-Za-z_]\w*(?:\.\w+)*)(?::\s*(.*))?$")

EXPLANATIONS = {
    "NameError": N_(
        "This name has no value yet. Check its spelling and where it is created."
    ),
    "UnboundLocalError": N_("This variable is used before it receives a value."),
    "TypeError": N_(
        "An operation received an unsuitable value or arguments. Check this block's parameters."
    ),
    "ValueError": N_(
        "A parameter has an unsupported value. Check its range and available choices."
    ),
    "ZeroDivisionError": N_("Division by zero is not allowed. Check the divisor."),
    "IndexError": N_(
        "This item is outside the list or sequence. Check its index and length."
    ),
    "KeyError": N_("This key is missing from the dictionary. Check its name."),
    "AttributeError": N_(
        "This object has no such method or property. Check the object and its name."
    ),
    "ImportError": N_(
        "A required module could not be loaded. Check the program files and hub support."
    ),
    "ModuleNotFoundError": N_(
        "A required module could not be loaded. Check the program files and hub support."
    ),
    "NotImplementedError": N_(
        "This operation is not implemented by the current execution environment."
    ),
}


@dataclass(frozen=True)
class RuntimeProblem:
    program: object
    path: Path | None
    line: int
    kind: str
    detail: str

    @property
    def explanation(self):
        if self.kind == "OSError" and (
            "ENODEV" in self.detail
            or "[Errno 19]" in self.detail
            or re.search(r"No .* on port", self.detail)
        ):
            return tr(
                "A device was not found. Check its cable and the port selected in this block."
            )
        text = EXPLANATIONS.get(self.kind)
        return (
            tr(text)
            if text
            else self.kind + (": " + self.detail if self.detail else "")
        )

    @property
    def source(self):
        return self.program.sources.get(self.path, "") if self.program else ""


class Tracebacks:
    def __init__(self, program, received):
        self.program, self.received = program, received
        self.buffer = ""
        self.frames = None

    def feed(self, text):
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self.line(line.rstrip("\r"))
        if len(self.buffer) > 65536:
            self.buffer = self.buffer[-65536:]

    def line(self, text):
        if text == "Traceback (most recent call last):":
            self.frames = []
        elif self.frames is not None:
            if frame := FRAME.match(text):
                self.frames.append((frame[1], int(frame[2])))
                self.frames = self.frames[-100:]
            elif error := EXCEPTION.match(text):
                frames, self.frames = self.frames, None
                if error[1] in {"KeyboardInterrupt", "GeneratorExit"}:
                    return
                known = []
                for filename, line in frames:
                    path = (
                        self.program.original_path(filename) if self.program else None
                    )
                    if path is not None and 1 <= line <= len(
                        self.program.sources[path].splitlines()
                    ):
                        known.append((path, line))
                user = []
                for path, line in known:
                    source = self.program.sources[path]
                    try:
                        section = helper_section(source)
                    except ValueError:
                        section = None
                    offset = sum(
                        len(s) for s in source.splitlines(keepends=True)[: line - 1]
                    )
                    if section is None or not section.contains(offset):
                        user.append((path, line))
                path, line = (user or known or [(None, 0)])[-1]
                self.received(
                    RuntimeProblem(self.program, path, line, error[1], error[2] or "")
                )
