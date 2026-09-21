"""Atomic document commits and snapshot history; no frontend dependencies."""

from dataclasses import dataclass

from .formatting import format_source
from .syntax import Syntax


@dataclass(frozen=True)
class State:
    source: str
    scratch: tuple[str, ...] = ()


class Document:
    """Own the committed source and Scratch. A failed commit changes nothing."""

    def __init__(self, source: str = "", scratch: tuple[str, ...] = ()):
        source = format_source(source)
        self._state = State(source, tuple(scratch))
        self._syntax = Syntax(source)
        self._undo: list[State] = []
        self._redo: list[State] = []

    @property
    def state(self) -> State:
        return self._state

    @property
    def syntax(self) -> Syntax:
        return self._syntax

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def commit(self, source: str, scratch: tuple[str, ...] | None = None) -> bool:
        """Validate and format before publishing; return whether state changed."""
        source = format_source(source) if source != self.state.source else source
        state = State(source, self.state.scratch if scratch is None else tuple(scratch))
        if state == self.state:
            return False
        syntax = Syntax(source)
        self._undo.append(self.state)
        self._redo.clear()
        self._state, self._syntax = state, syntax
        return True

    def undo(self) -> bool:
        return self._restore(self._undo, self._redo)

    def redo(self) -> bool:
        return self._restore(self._redo, self._undo)

    def _restore(self, previous: list[State], following: list[State]) -> bool:
        if not previous:
            return False
        state = previous[-1]
        syntax = Syntax(state.source)
        following.append(self.state)
        previous.pop()
        self._state, self._syntax = state, syntax
        return True
