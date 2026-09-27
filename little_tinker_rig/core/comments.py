"""Project definition comments onto matching code without regenerating that code."""

import ast
import textwrap
import tokenize
from collections import defaultdict

from .edit import patches
from .source_text import definition_syntax
from .syntax import Span


def definition_comments(syntax, match, span, nodes):
    """Return the unchanged code with definition comments, and expression notes.

    Statement comments follow corresponding AST owners. Expression-only comments
    occupy separate rows before the enclosing statement, never duplicate its code.
    All patch coordinates refer to the original program.
    """
    # Comment owners are paired structurally. Substituting every argument would
    # reparse a different definition for every call, without changing its comments.
    definition = definition_syntax(match.snippet.definition)
    if not definition.comment_owners and not any(
        syntax.owned_comments.get(n) for n in nodes
    ):
        if not any(
            t.type == tokenize.COMMENT
            for t in syntax.tokens_between(span.start, span.end)
        ):
            return syntax.source[span.start : span.end], ""
    if match.snippet.expression and not nodes:
        notes = [
            definition.source[s.start : s.end]
            for s in sorted(definition.comment_owners)
        ]
        changes = []
        for token in syntax.tokens_between(span.start, span.end):
            if token.type == tokenize.COMMENT:
                start, end = syntax.offset(*token.start), syntax.offset(*token.end)
                changes.append((Span(start - span.start, end - span.start), ""))
        return patches(syntax.source[span.start : span.end], changes), "\n".join(notes)

    roots = [n for n in nodes if syntax.statement_suite[n].owner not in nodes]
    owners = {}

    def pair(before, after):
        owners[before] = after
        if isinstance(before, ast.AnnAssign) and isinstance(after, ast.Assign):
            pair(before.target, after.targets[0])
            if before.value is not None:
                pair(before.value, after.value)
        elif type(before) is type(after):
            for field, value in ast.iter_fields(before):
                other = getattr(after, field)
                if isinstance(value, ast.AST) and isinstance(other, ast.AST):
                    pair(value, other)
                elif isinstance(value, list) and isinstance(other, list):
                    for a, b in zip(value, other, strict=False):
                        if isinstance(a, ast.AST) and isinstance(b, ast.AST):
                            pair(a, b)

    for before, after in zip(definition.tree.body, roots, strict=True):
        pair(before, after)
    removals = []
    for node in nodes:
        for comment in syntax.owned_comments.get(node, ()):
            first, column = syntax.position(comment.start)
            last, _ = syntax.position(comment.end)
            isolated = not syntax.lines[first - 1][:column].strip()
            removed = (
                Span(syntax.starts[first - 1], syntax.starts[last])
                if isolated
                else comment
            )
            if span.start <= removed.start and removed.end <= span.end:
                removals.append(removed)

    insertions = defaultdict(list)
    for comment, owner in sorted(definition.comment_owners.items()):
        target = owners.get(owner)
        if target is None:
            # A final module comment follows the final statement of the template.
            if owner is definition.tree and roots:
                target = roots[-1]
            else:
                continue
        first, column = definition.position(comment.start)
        text = definition.source[comment.start : comment.end]
        inline = bool(definition.lines[first - 1][:column].strip())
        indent = max(0, target.col_offset + column - getattr(owner, "col_offset", 0))
        if inline:
            offset = syntax.spans[target].end
            text = "  " + text
        elif owner is definition.tree or comment.start >= definition.spans[owner].end:
            offset = syntax.starts[target.end_lineno]
            text = " " * indent + text + "\n"
        elif comment.end <= definition.spans[owner].start:
            offset = syntax.starts[target.lineno - 1]
            text = " " * indent + text + "\n"
        else:
            # Docstrings and comments inside an otherwise empty compound suite.
            child = next(
                (n for n in getattr(target, "body", ()) if isinstance(n, ast.stmt)),
                target,
            )
            offset = syntax.starts[child.lineno - 1]
            text = textwrap.indent(textwrap.dedent(text), " " * indent) + "\n"
        if span.start <= offset <= span.end:
            # Replacing a whole comment line may cover the insertion anchor.
            offset = next((s.start for s in removals if s.contains(offset)), offset)
            insertions[offset].append(text)
    changes = [(Span(s.start - span.start, s.end - span.start), "") for s in removals]
    changes += [
        (Span(p - span.start, p - span.start), "".join(texts))
        for p, texts in insertions.items()
    ]
    return patches(syntax.source[span.start : span.end], changes), ""
