"""A detached drag is a proposal. Only a successful drop commits both areas."""

import ast
from dataclasses import dataclass

from . import edit
from .document import State
from .formatting import format_source
from .interaction import Move
from .session import Session
from .syntax import Syntax


@dataclass
class Transfer:
    owner: Session
    revision: State
    syntax: Syntax
    origin: int | None
    text: str
    remainder: str
    nodes: ast.AST | tuple[ast.stmt, ...] | None = None

    @classmethod
    def capture(cls, owner, *, index=None, fragment=None):
        if index is not None and fragment is None:
            text, remainder, nodes = owner.document.state.scratch[index], "", None
        else:
            session = owner if index is None else fragment
            text, remainder = session.extract_selection()
            match = session.selected_match()
            nodes = (
                session._match_nodes(match)
                if match and not match.snippet.expression
                else session.editor.selection
            )
        return cls(
            owner,
            owner.document.state,
            owner.document.syntax,
            index,
            text,
            remainder,
            nodes,
        )

    def validate(self):
        if (
            self.owner.document.state is not self.revision
            or self.owner.document.syntax is not self.syntax
        ):
            raise ValueError("Document changed during drag; pick up the block again")

    def remaining(self):
        self.validate()
        source, scratch = self.revision.source, list(self.revision.scratch)
        if self.origin is None:
            source = self.remainder
        elif self.remainder.strip():
            scratch[self.origin] = self.remainder
        else:
            del scratch[self.origin]
        return source, scratch

    def to_scratch(self, position):
        source, scratch = self.remaining()
        if (
            self.origin is not None
            and not self.remainder.strip()
            and self.origin < position
        ):
            position -= 1
        scratch.insert(position, self.text)
        self.owner.editor.commit(source, tuple(scratch))

    def to_program(self, target):
        self.validate()
        if self.origin is not None:
            self.owner.restore_scratch(
                self.origin, target, fragment=(self.text, self.remainder)
            )
        else:
            if not isinstance(target, edit.Target):
                raise ValueError("Move a statement to a statement boundary")
            self.owner.editor.moving = Move(self.syntax, self.nodes, (target,))
            self.owner.editor.commit_move()

    def to_fragment(self, index, fragment, target):
        self.validate()
        if self.origin == index:
            raise ValueError("Move blocks within a cell using its editor")
        syntax = fragment.document.syntax
        source = (
            edit.replace(syntax, target, self.text)
            if isinstance(target, ast.expr)
            else edit.insert(syntax, target, self.text)
        )
        main, scratch = self.remaining()
        if (
            self.origin is not None
            and not self.remainder.strip()
            and self.origin < index
        ):
            index -= 1
        scratch[index] = format_source(source, fragment=True)
        self.owner.editor.commit(main, tuple(scratch))
