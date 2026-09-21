"""Structural roles shared by every renderer; colors are quiet RGB defaults."""

import ast
from dataclasses import dataclass

from .syntax import Span, Syntax

PALETTE = {
    "control": "#e8ddf2",
    "loop": "#f5e7c8",
    "action": "#d8e9f6",
    "value": "#e4efdc",
    "state": "#f3dfcf",
    "definition": "#dcdff5",
    "placeholder": "#e5e7eb",
    "snippet": "#cfe9e5",
    "warning": "#f9d6c8",
}


def role(node: ast.AST) -> str:
    if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        return "loop"
    if isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    ):
        return "definition"
    if isinstance(node, (ast.Pass, ast.Constant)) and (
        isinstance(node, ast.Pass) or node.value is None
    ):
        return "placeholder"
    if isinstance(node, (ast.Call, ast.Expr)):
        return "action"
    if isinstance(node, (ast.Name, ast.Assign, ast.AnnAssign, ast.AugAssign)):
        return "state"
    if isinstance(node, ast.stmt):
        return "control"
    return "value"


def snippet_role(snippet) -> str:
    """A template keeps the same semantic color in the library and the document."""
    return role(snippet.body if snippet.expression else snippet.body[0])


@dataclass(frozen=True)
class Region:
    span: Span
    depth: int
    role: str
    line: int
    column: int
    end_line: int
    end_column: int
    extend_line: bool
    foldable: bool
    movable: bool


def regions(syntax: Syntax, matches=()) -> tuple[Region, ...]:
    result = []

    def visit(node: ast.AST, depth: int) -> None:
        visible = isinstance(node, (ast.stmt, ast.expr))
        if visible:
            span = syntax.spans[node]
            line, column = syntax.position(span.start)
            end_line, end_column = syntax.position(span.end)
            result.append(
                Region(
                    span,
                    depth,
                    role(node),
                    line,
                    column,
                    end_line,
                    end_column,
                    isinstance(node, ast.stmt),
                    isinstance(node, ast.stmt) and end_line > line,
                    isinstance(node, ast.stmt),
                )
            )
        for child in syntax.children[node]:
            visit(child, depth + visible)

    visit(syntax.tree, 0)
    for match in matches:
        contained = [
            region
            for region in result
            if match.span.start <= region.span.start
            and region.span.end <= match.span.end
        ]
        placeholders = {
            syntax.spans[node] for nodes in match.occurrences.values() for node in nodes
        }
        depth = min((region.depth for region in contained), default=0)
        result = [
            region
            for region in result
            if region not in contained or region.span in placeholders
        ]
        line, column = syntax.position(match.span.start)
        end_line, end_column = syntax.position(match.span.end)
        result.append(
            Region(
                match.span,
                depth,
                snippet_role(match.snippet),
                line,
                column,
                end_line,
                end_column,
                not match.snippet.expression,
                end_line > line,
                not match.snippet.expression,
            )
        )
    result.sort(key=lambda region: (region.depth, region.span.start, -region.span.end))
    return tuple(result)
