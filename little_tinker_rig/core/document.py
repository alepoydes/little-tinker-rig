"""Atomic document commits and snapshot history; no frontend dependencies."""

from dataclasses import dataclass, field, replace
from functools import cached_property

from .formatting import format_source
from .syntax import Syntax


@dataclass(frozen=True)
class State:
    source: str
    scratch: tuple[str, ...] = ()
    # Runtime identity belongs to history, but not to persisted content equality.
    scratch_ids: tuple[object, ...] = field(default=(), compare=False, repr=False)
    draft: str | None = None

    @property
    def text(self):
        return self.source if self.draft is None else self.draft


class Document:
    """Own the committed source and Scratch. A failed commit changes nothing."""

    def __init__(
        self,
        source: str = "",
        scratch: tuple[str, ...] = (),
        *,
        fragment=False,
        draft=None,
    ):
        self.fragment = fragment
        self.prepare = None
        # Scratch is a parsed projection of its existing text, not a new edit.
        # Canonical formatting belongs to commits, not view construction.
        source = source if fragment else format_source(source)
        self._state = State(
            source, tuple(scratch), tuple(object() for _ in scratch), draft
        )
        self._syntax = Syntax(source, fragment=self.fragment)
        self._undo: list[State] = []
        self._redo: list[State] = []
        self._group = None

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
        self,
        source: str,
        scratch: tuple[str, ...] | None = None,
        *,
        scratch_ids=None,
        apply_draft=False,
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
        return State(
            source, scratch, scratch_ids, None if apply_draft else self.state.draft
        )

    def commit(
        self,
        source: str,
        scratch: tuple[str, ...] | None = None,
        *,
        scratch_ids=None,
        group=None,
        apply_draft=False,
    ) -> bool:
        """Validate and format before publishing; return whether state changed."""
        state = self.candidate(
            source, scratch, scratch_ids=scratch_ids, apply_draft=apply_draft
        )
        source = state.source
        if state == self.state and state.scratch_ids == self.state.scratch_ids:
            return False
        syntax = (
            self.syntax
            if source == self.state.source
            else Syntax(source, fragment=self.fragment)
        )
        return self._publish(state, syntax, group)

    def set_draft(self, text, *, group=None):
        state = replace(self.state, draft=None if text == self.state.source else text)
        if state == self.state:
            return False
        return self._publish(state, self.syntax, group)

    def _publish(self, state, syntax, group):
        # Parsing an unchanged draft updates its projection, not its edit history.
        content_changed = (
            state.text != self.state.text
            or state.scratch != self.state.scratch
            or state.scratch_ids != self.state.scratch_ids
        )
        if not content_changed:
            self._state, self._syntax = state, syntax
            return True
        if group is None or group is not self._group:
            self._undo.append(self.state)
        if self._redo or state.scratch_ids != self.state.scratch_ids:
            self.__dict__.pop("scratch_identities", None)
        self._redo.clear()
        self._state, self._syntax = state, syntax
        self._group = group
        return True

    @cached_property
    def scratch_identities(self):
        """Identities still reachable through this document's Undo/Redo history."""
        return frozenset(
            identity
            for state in (*self._undo, self.state, *self._redo)
            for identity in state.scratch_ids
        )

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
        self._group = None
        return True
