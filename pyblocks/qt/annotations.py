"""Display-only explanations of structural blocks; never written into Python."""

import ast

from pyblocks.core.presentation import role, snippet_role
from pyblocks.i18n import N_, tr

ICONS = {
    "loop": "⟳",
    "control": "◇",
    "action": "▶",
    "state": "▣",
    "definition": "ƒ",
    "value": "＝",
    "placeholder": "…",
}
LABELS = {
    ast.If: N_("Check a condition"),
    ast.For: N_("Repeat for each item"),
    ast.While: N_("Repeat while the condition is true"),
    ast.Try: N_("Run with error handling"),
    ast.FunctionDef: N_("Define an action"),
    ast.Return: N_("Return a result"),
    ast.Break: N_("Leave the loop"),
    ast.Continue: N_("Next iteration"),
    ast.Assign: N_("Store a value"),
    ast.AugAssign: N_("Change a value"),
    ast.Expr: N_("Perform an action"),
    ast.Pass: N_("Place actions here"),
}


def block_notes(session):
    syntax = session.document.syntax
    matches = [m for m in session.visible_matches if not m.snippet.expression]
    notes = {}
    for node, span in syntax.spans.items():
        if type(node) not in LABELS or any(
            m.span.start <= span.start and span.end <= m.span.end for m in matches
        ):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        line, column = syntax.position(span.start)
        notes.setdefault(
            line, (column, tr(LABELS[type(node)]), ICONS.get(role(node), "▶"))
        )
    for match in matches:
        line, column = syntax.position(match.span.start)
        notes[line] = (
            column,
            tr(match.snippet.help).splitlines()[0],
            block_icon(match.snippet),
        )
    return notes


def block_icon(snippet):
    identity = snippet.identity
    if "/motors/" in identity:
        return "⚙" if "/create_" in identity else "↻"
    if "/sensors/" in identity:
        return "⏱" if identity.endswith("/wait_ms") else "◉"
    if "/drive/" in identity:
        return "⏱" if "clock" in identity or "elapsed" in identity else "➜"
    return ICONS.get(snippet_role(snippet), "▶")
