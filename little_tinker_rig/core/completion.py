"""Static Python assistance shared by source editors; never executes user code."""

from dataclasses import dataclass
from threading import RLock

import jedi

_lock = RLock()


@dataclass(frozen=True)
class Suggestions:
    words: tuple = ()
    signature: str = ""
    parameter: str = ""
    description: str = ""
    error: str = ""


def _analyze(source, path, line, column, mode):
    script = jedi.Script(source, path=path)
    prefix = source.split("\n")[line - 1][:column]
    word = prefix.rsplit(".", 1)[-1]
    complete = mode == "complete" or (
        mode == "auto"
        and (prefix.endswith(".") or (len(word) >= 2 and word[-2:].isidentifier()))
    )
    words = (
        tuple(
            (item.name_with_symbols, item.get_completion_prefix_length())
            for item in script.complete(line, column)
            if item.type != "path"
        )
        if complete
        else ()
    )
    signatures = script.get_signatures(line, column)
    definition = signatures[0] if signatures else None
    if definition is None and mode == "help":
        definitions = script.help(line, column)
        definition = definitions[0] if definitions else None
    description = (
        definition.docstring(raw=True) if definition and mode == "help" else ""
    )
    # Keep popups readable even for long upstream docstrings.
    description = description[:1800]
    signature = signatures[0] if signatures else None
    parameter = (
        signature.params[signature.index].to_string()
        if signature
        and signature.index is not None
        and signature.index < len(signature.params)
        else ""
    )
    return Suggestions(
        words, signature.to_string() if signature else "", parameter, description
    )


def analyze(source, path, line, column, mode):
    # Jedi caches are shared between Scripts and must not be used concurrently.
    with _lock:
        return _analyze(source, path, line, column, mode)
