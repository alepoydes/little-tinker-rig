"""Atomic document commits and snapshot history; no frontend dependencies."""

from dataclasses import dataclass, field

from .formatting import format_source
from .syntax import Syntax


@dataclass(frozen=True)
class State:
    source: str
    scratch: tuple[str, ...] = ()
    # Runtime identity belongs to history, but not to persisted content equality.
    scratch_ids: tuple[object, ...] = field(default=(), compare=False, repr=False)


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
        self._state = State(source, tuple(scratch), tuple(object() for _ in scratch))
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

    def candidate(
        self, source: str, scratch: tuple[str, ...] | None = None, *, scratch_ids=None
    ) -> State:
        """Prepare an edit for review without publishing it or changing history."""
        scratch = self.state.scratch if scratch is None else tuple(scratch)
        if scratch_ids is None:
            scratch_ids = (
                self.state.scratch_ids
                if scratch == self.state.scratch
                else tuple(object() for _ in scratch)
            )
        scratch_ids = tuple(scratch_ids)
        if len(scratch_ids) != len(scratch) or len(set(scratch_ids)) != len(scratch):
            raise ValueError("Scratch fragments need distinct identities")
        if self.prepare is not None:
            source = self.prepare(source, scratch)
        source = (
            format_source(source, fragment=self.fragment)
            if source != self.state.source
            else source
        )
        return State(source, scratch, scratch_ids)

    def commit(
        self, source: str, scratch: tuple[str, ...] | None = None, *, scratch_ids=None
    ) -> bool:
        """Validate and format before publishing; return whether state changed."""
        state = self.candidate(source, scratch, scratch_ids=scratch_ids)
        source = state.source
        if state == self.state and state.scratch_ids == self.state.scratch_ids:
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
