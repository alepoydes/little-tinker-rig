"""Shared selection and move navigation for mouse, keyboard and CLI clients."""

import ast
from dataclasses import dataclass

from . import edit
from .document import Document
from .syntax import Syntax


@dataclass
class Move:
    syntax: Syntax
    node: ast.stmt | tuple[ast.stmt, ...]
    targets: tuple[edit.Target, ...]
    index: int = 0


class Editor:
    """Transient interaction state over a Document; AST references are disposable."""

    def __init__(self, document: Document):
        self.document = document
        self.selection = document.syntax.tree
        self.moving: Move | None = None

    def select(self, offset: int) -> ast.AST:
        self.selection = self.document.syntax.at(offset)
        return self.selection

    def parent(self) -> ast.AST:
        self.selection = self.document.syntax.parent.get(self.selection, self.selection)
        return self.selection

    def child(self) -> ast.AST:
        children = self.document.syntax.children.get(self.selection, ())
        if children:
            self.selection = children[0]
        return self.selection

    def sibling(self, step: int) -> ast.AST:
        """Select a neighbouring child of the same parent, wrapping at the ends."""
        syntax = self.document.syntax
        parent = syntax.parent.get(self.selection)
        if parent is not None:
            siblings = syntax.children[parent]
            self.selection = siblings[
                (siblings.index(self.selection) + step) % len(siblings)
            ]
        return self.selection

    def statement(self) -> ast.stmt:
        for node in self.document.syntax.ancestors(self.selection):
            if isinstance(node, ast.stmt):
                return node
        raise ValueError("Select a statement first")

    def commit(
        self,
        source: str,
        scratch: tuple[str, ...] | None = None,
        *,
        focus: int | None = None,
    ) -> bool:
        offset = self.document.syntax.spans[self.selection].start
        changed = self.document.commit(source, scratch)
        self.moving = None
        self.select(
            edit.map_offset(source, self.document.state.source, focus)
            if focus is not None
            else min(offset, len(self.document.state.source))
        )
        return changed

    def replace(self, fragment: str) -> None:
        self.commit(edit.replace(self.document.syntax, self.selection, fragment))

    def delete(self) -> None:
        self.commit(edit.delete(self.document.syntax, self.selection))

    def to_scratch(self) -> None:
        syntax = self.document.syntax
        node = self.selection
        span = (
            syntax.block_span(node)
            if isinstance(node, ast.stmt)
            else syntax.spans[node]
        )
        text = syntax.source[span.start : span.end]
        self.commit(edit.delete(syntax, node), self.document.state.scratch + (text,))

    def from_scratch(self, index: int, target: edit.Target) -> None:
        scratch = self.document.state.scratch
        if not 0 <= index < len(scratch):
            raise ValueError("Scratch index outside workspace")
        source = edit.insert(self.document.syntax, target, scratch[index])
        self.commit(source, scratch[:index] + scratch[index + 1 :])

    def begin_move(self, nodes: tuple[ast.stmt, ...] | None = None) -> Move:
        syntax, node = self.document.syntax, nodes or self.statement()
        _, removed, _ = edit.statement_group(syntax, node)
        # Within one statement list, compiler context is independent of position
        # except for declarations whose meaning depends on preceding statements.
        ordered = any(
            isinstance(item, (ast.Global, ast.Nonlocal))
            or isinstance(item, ast.ImportFrom)
            and item.module == "__future__"
            for item in ast.walk(syntax.tree)
        )
        valid_suites = {}
        candidates = []
        for target in edit.targets(syntax):
            try:
                offset, _ = edit.target_position(syntax, target)
                if removed.start <= offset <= removed.end:
                    continue
                key = (id(target.suite.owner), target.suite.field)
                if ordered or key not in valid_suites:
                    try:
                        edit.move(syntax, node, target)
                    except SyntaxError:
                        valid_suites[key] = False
                    else:
                        valid_suites[key] = True
                if valid_suites[key]:
                    candidates.append(target)
            except ValueError:
                continue
        if not candidates:
            raise ValueError("No legal destination for this statement")
        candidates.sort(key=lambda target: edit.target_position(syntax, target))
        self.moving = Move(syntax, node, tuple(candidates))
        return self.moving

    def navigate_move(self, step: int = 0, depth: int = 0) -> edit.Target:
        move = self._move()
        if depth:
            offset, indent = edit.target_position(move.syntax, move.targets[move.index])
            candidates = [
                (abs(edit.target_position(move.syntax, target)[0] - offset), index)
                for index, target in enumerate(move.targets)
                if (edit.target_position(move.syntax, target)[1] - indent) * depth > 0
            ]
            if candidates:
                move.index = min(candidates)[1]
        else:
            move.index = (move.index + step) % len(move.targets)
        return move.targets[move.index]

    def preview_move(self) -> str:
        move = self._move()
        return edit.move(move.syntax, move.node, move.targets[move.index])

    def commit_move(self) -> None:
        move = self._move()
        first = move.node[0] if isinstance(move.node, tuple) else move.node
        fingerprint = ast.dump(first)
        offset, _ = edit.target_position(move.syntax, move.targets[move.index])
        self.commit(self.preview_move())
        syntax = self.document.syntax
        candidates = [
            node
            for node in syntax.spans
            if isinstance(node, ast.stmt) and ast.dump(node) == fingerprint
        ]
        if candidates:
            self.selection = min(
                candidates, key=lambda node: abs(syntax.spans[node].start - offset)
            )

    def cancel_move(self) -> None:
        self.moving = None

    def _move(self) -> Move:
        if self.moving is None:
            raise ValueError("No move in progress")
        if self.moving.syntax is not self.document.syntax:
            self.moving = None
            raise ValueError("Document changed during move; select the block again")
        return self.moving

    def undo(self) -> bool:
        return self._history(self.document.undo)

    def redo(self) -> bool:
        return self._history(self.document.redo)

    def _history(self, restore) -> bool:
        changed = restore()
        self.selection = self.document.syntax.tree
        self.moving = None
        return changed
