"""A detached drag is a proposal. Only a successful drop commits both areas."""

import ast
from dataclasses import dataclass

from . import edit
from .document import State
from .formatting import format_source
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
    fragment_syntax: Syntax | None = None
    result_type: str | None = None

    @classmethod
    def capture(cls, owner, *, index=None, fragment=None, node=None):
        if index is not None and fragment is None:
            text, remainder, nodes = owner.document.state.scratch[index], "", None
        else:
            session = owner if index is None else fragment
            if node is not None:
                text = edit.reindent(edit.block_text(session.document.syntax, node), 0)
                remainder = edit.delete(session.document.syntax, node)
                nodes = node
            else:
                text, remainder = session.extract_selection()
                nodes = session.selected_nodes()
            if (
                node is not None
                and isinstance(nodes, ast.expr)
                and not isinstance(session.document.syntax.parent.get(nodes), ast.Expr)
            ):
                remainder = session._field_source(nodes, remainder)
        return cls(
            owner,
            owner.document.state,
            owner.document.syntax,
            index,
            text,
            remainder,
            nodes,
            fragment.document.syntax if fragment else None,
            (
                str(value)
                if isinstance(nodes, ast.expr)
                and (value := session.analysis.type_info(nodes)) is not None
                else None
            ),
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
        identities = list(self.revision.scratch_ids)
        if self.origin is None:
            source = self.remainder
        elif self.remainder.strip():
            scratch[self.origin] = self.remainder
        else:
            del scratch[self.origin]
            del identities[self.origin]
        return source, scratch, identities

    def to_scratch(self, position):
        source, scratch, identities = self.remaining()
        if (
            self.origin is not None
            and not self.remainder.strip()
            and self.origin < position
        ):
            position -= 1
        scratch.insert(position, self.text)
        identity = (
            self.revision.scratch_ids[self.origin]
            if self.origin is not None and not self.remainder.strip()
            else object()
        )
        identities.insert(position, identity)
        self.owner.editor.commit(source, tuple(scratch), scratch_ids=identities)

    def to_program(self, target):
        self.validate()
        if not self.owner.accepts_target(target):
            raise ValueError("Expand the block to edit its fixed implementation")
        if self.origin is not None:
            self.owner.restore_scratch(
                self.origin, target, fragment=(self.text, self.remainder)
            )
        else:
            self.move_within(self.owner, target)

    def move_within(self, session, target):
        syntax = session.document.syntax
        if isinstance(self.nodes, ast.expr) and isinstance(target, ast.expr):
            from .expressions import copy_to

            copy_to(session, self.nodes, target, move=True)
            return
        offset = edit.target_position(syntax, target)[0]
        if (
            isinstance(self.nodes, ast.expr)
            and session.field_binding(self.nodes)
            and not isinstance(syntax.parent.get(self.nodes), ast.Expr)
        ):
            # Detaching a repeated input changes every occurrence, but keeps its
            # containing statements and hence the destination suite's indices.
            remaining = Syntax(self.remainder, fragment=session.document.fragment)
            owner = remaining.follow(syntax.path(target.suite.owner))
            suite = next(
                s
                for s in remaining.suites
                if s.owner is owner and s.field == target.suite.field
            )
            source = edit.insert(remaining, edit.Target(suite, target.index), self.text)
        else:
            source = edit.move(syntax, self.nodes, target)
        session.editor.commit(
            source, focus=edit.map_offset(syntax.source, source, offset)
        )

    def to_fragment(self, index, fragment, target):
        self.validate()
        if not fragment.accepts_target(target):
            raise ValueError("Expand the block to edit its fixed implementation")
        syntax = fragment.document.syntax
        if self.origin == index:
            if syntax is not self.fragment_syntax:
                raise ValueError("Fragment changed during drag")
            self.move_within(fragment, target)
            source = fragment.document.state.source
            scratch = list(self.revision.scratch)
            scratch[index] = format_source(source, fragment=True)
            self.owner.editor.commit(
                self.revision.source,
                tuple(scratch),
                scratch_ids=self.revision.scratch_ids,
            )
            return
        source = (
            edit.replace(syntax, target, self.text)
            if isinstance(target, ast.expr)
            else edit.insert(syntax, target, self.text)
        )
        if isinstance(target, ast.expr):
            source = fragment._field_source(target, source)
        main, scratch, identities = self.remaining()
        if (
            self.origin is not None
            and not self.remainder.strip()
            and self.origin < index
        ):
            index -= 1
        scratch[index] = format_source(source, fragment=True)
        self.owner.editor.commit(main, tuple(scratch), scratch_ids=identities)
