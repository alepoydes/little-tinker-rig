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

    def __init__(
        self, source: str = "", scratch: tuple[str, ...] = (), *, fragment=False
    ):
        self.fragment = fragment
        self.prepare = None
        # Scratch is a parsed projection of its existing text, not a new edit.
        # Canonical formatting belongs to commits, not view construction.
        source = source if fragment else format_source(source)
        self._state = State(source, tuple(scratch))
        self._syntax = Syntax(source, fragment=self.fragment)
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
        scratch = self.state.scratch if scratch is None else tuple(scratch)
        if self.prepare is not None:
            source = self.prepare(source, scratch)
        source = (
            format_source(source, fragment=self.fragment)
            if source != self.state.source
            else source
        )
        state = State(source, scratch)
        if state == self.state:
            return False
        syntax = (
            self.syntax
            if source == self.state.source
            else Syntax(source, fragment=self.fragment)
        )
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
        syntax = (
            self.syntax
            if state.source == self.state.source
            else Syntax(state.source, fragment=self.fragment)
        )
        following.append(self.state)
        previous.pop()
        self._state, self._syntax = state, syntax
        return True
