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
                text = edit.reindent(session.document.syntax.text(node), 0)
                remainder = edit.delete(session.document.syntax, node)
                nodes = node
            else:
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
            fragment.document.syntax if fragment else None,
            session.analysis.type_of(nodes) if isinstance(nodes, ast.expr) else None,
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
            source = edit.move(self.syntax, self.nodes, target)
            offset = (
                self.syntax.spans[target].start
                if isinstance(target, ast.expr)
                else edit.target_position(self.syntax, target)[0]
            )
            focus = edit.map_offset(self.syntax.source, self.remainder, offset)
            self.owner.editor.commit(source, focus=focus)

    def to_fragment(self, index, fragment, target):
        self.validate()
        syntax = fragment.document.syntax
        if self.origin == index:
            if syntax is not self.fragment_syntax:
                raise ValueError("Fragment changed during drag")
            source = edit.move(syntax, self.nodes, target)
            scratch = list(self.revision.scratch)
            scratch[index] = format_source(source, fragment=True)
            self.owner.editor.commit(self.revision.source, tuple(scratch))
            return
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
