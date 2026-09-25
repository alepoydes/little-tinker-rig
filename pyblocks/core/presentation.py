"""Structural roles shared by every renderer; colors are quiet RGB defaults."""

import ast
from bisect import bisect_right
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

ICONS = {
    "loop": "⟳",
    "control": "◇",
    "action": "▶",
    "state": "▣",
    "definition": "ƒ",
    "value": "＝",
    "placeholder": "…",
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
    return snippet.color or role(
        snippet.body if snippet.expression else snippet.body[0]
    )


def role_color(role: str) -> str:
    return PALETTE.get(role, role)


def block_icon(snippet):
    if snippet.icon is not None:
        return snippet.icon
    # Only legacy definitions need inferred appearance; migration makes it explicit.
    identity = snippet.identity
    if "/motors/" in identity:
        return "⚙" if "/create_" in identity else "↻"
    if "/sensors/" in identity:
        return "⏱" if identity.endswith("/wait_ms") else "◉"
    if "/drive/" in identity:
        return "⏱" if "clock" in identity or "elapsed" in identity else "➜"
    return ICONS.get(snippet_role(snippet), "▶")


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
    outlined: bool = False


def regions(syntax: Syntax, matches=()) -> tuple[Region, ...]:
    result = []

    def visit(node: ast.AST, depth: int) -> None:
        visible = isinstance(node, (ast.stmt, ast.expr))
        if visible:
            span = syntax.spans[node]
            line, column = syntax.position(span.start)
            end_line, end_column = syntax.position(span.end)
            if isinstance(node, ast.stmt):
                line = syntax.position(syntax.owned_spans[node].start)[0]
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
                    isinstance(node, ast.stmt),
                )
            )
        for child in syntax.children[node]:
            visit(child, depth + visible)

    visit(syntax.tree, 0)
    matches = sorted(matches, key=lambda match: match.span.start)
    starts = [match.span.start for match in matches]
    depths, first_lines = {}, {}
    visible = []
    for region in result:
        index = bisect_right(starts, region.span.start) - 1
        if index >= 0 and region.span.end <= matches[index].span.end:
            depths[index] = min(depths.get(index, region.depth), region.depth)
            first_lines[index] = min(first_lines.get(index, region.line), region.line)
        else:
            visible.append(region)
    result = visible
    for index, match in enumerate(matches):
        depth = depths.get(index, 0)
        line, column = syntax.position(match.span.start)
        line = first_lines.get(index, line)
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
                True,
            )
        )
    result.sort(key=lambda region: (region.depth, region.span.start, -region.span.end))
    return tuple(result)
