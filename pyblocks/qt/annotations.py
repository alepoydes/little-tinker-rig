"""Display-only explanations of structural blocks; never written into Python."""

import ast
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass

from pyblocks.core.presentation import ICONS, block_icon, role, snippet_role
from pyblocks.core.syntax import Span
from pyblocks.i18n import N_, tr

LABELS = {
    ast.If: N_("Check a condition"),
    ast.For: N_("Repeat for each item"),
    ast.While: N_("Repeat while the condition is true"),
    ast.Try: N_("Run with error handling"),
    ast.FunctionDef: N_("Define an action"),
    ast.ClassDef: N_("Define a class"),
    ast.With: N_("Use a context with cleanup"),
    ast.Return: N_("Return a result"),
    ast.Break: N_("Leave the loop"),
    ast.Continue: N_("Next iteration"),
    ast.Assign: N_("Store a value"),
    ast.AugAssign: N_("Change a value"),
    ast.Expr: N_("Perform an action"),
    ast.Pass: N_("Place actions here"),
}


@dataclass(frozen=True)
class BlockNote:
    column: int
    description: str
    icon: str
    role: str
    span: Span
    error: bool = False


def block_notes(session):
    syntax = session.document.syntax
    matches = session.visible_matches
    starts = [m.span.start for m in matches]
    notes = defaultdict(list)
    for node, span in syntax.spans.items():
        if type(node) not in LABELS:
            continue
        index = bisect_right(starts, span.start) - 1
        if index >= 0 and span.end <= matches[index].span.end:
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        line, column = syntax.position(span.start)
        notes[line].append(
            BlockNote(
                column,
                tr(LABELS[type(node)]),
                ICONS.get(role(node), "▶"),
                role(node),
                span,
            )
        )
    for match in matches:
        line, column = syntax.position(match.span.start)
        description = (
            tr(match.snippet.help).splitlines()[0]
            if match.snippet.help
            else match.snippet.identity.rsplit("/", 1)[1]
        )
        notes[line].append(
            BlockNote(
                column,
                description,
                block_icon(match.snippet),
                snippet_role(match.snippet),
                match.span,
            )
        )
    for diagnostic in session.analysis.diagnostics():
        if diagnostic.severity != "error":
            continue
        line, column = syntax.position(diagnostic.span.start)
        notes[line].append(
            BlockNote(
                column,
                tr("Error: {detail}", detail=diagnostic.message),
                "!",
                "warning",
                diagnostic.span,
                True,
            )
        )
    return {
        line: tuple(sorted(items, key=lambda note: note.column))
        for line, items in notes.items()
    }
