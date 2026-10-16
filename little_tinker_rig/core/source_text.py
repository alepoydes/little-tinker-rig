"""Preserve definition trivia while replacing corresponding Python expressions."""

import ast
import tokenize
from functools import lru_cache

from .edit import patches, reindent
from .structure import sequence
from .syntax import Span, Syntax


@lru_cache(maxsize=32)
def definition_syntax(source):
    return Syntax(source, fragment=True)


def rewrite(source, tree):
    syntax = definition_syntax(source)
    changes = []

    def visit(old, new):
        if ast.dump(old) == ast.dump(new):
            return
        if type(old) is type(new):
            fields = list(ast.iter_fields(old))
            scalars = [
                key
                for key, value in fields
                if not isinstance(value, (ast.AST, list)) and value != getattr(new, key)
            ]
            if scalars == ["name"] and isinstance(old, (ast.FunctionDef, ast.ClassDef)):
                token = next(
                    t
                    for t in syntax.tokens_between(
                        syntax.spans[old].start, syntax.spans[old].end
                    )
                    if t.type == tokenize.NAME and t.string == old.name
                )
                changes.append(
                    (
                        Span(syntax.offset(*token.start), syntax.offset(*token.end)),
                        new.name,
                    )
                )
                scalars = []
            if not scalars and all(
                not isinstance(value, list) or len(value) == len(getattr(new, key))
                for key, value in fields
            ):
                for key, value in fields:
                    other = getattr(new, key)
                    if isinstance(value, ast.AST):
                        visit(value, other)
                    elif isinstance(value, list):
                        for a, b in zip(value, other, strict=True):
                            if isinstance(a, ast.AST):
                                visit(a, b)
                return
        text = ast.unparse(new)
        if isinstance(
            new,
            (
                ast.BinOp,
                ast.BoolOp,
                ast.Compare,
                ast.UnaryOp,
                ast.IfExp,
                ast.Lambda,
                ast.NamedExpr,
                ast.Await,
                ast.Yield,
                ast.YieldFrom,
            ),
        ):
            text = f"({text})"
        changes.append((syntax.spans[old], text))

    visit(syntax.tree, tree)
    return patches(source, changes)


def body_source(source, roots):
    """Body slice including leading comments, excluding wrapper help/imports."""
    syntax = definition_syntax(source)
    first, last = roots[0], roots[-1]
    line = first.lineno
    indent = syntax.lines[first.lineno - 1][: first.col_offset]
    while line > 1 and (
        not syntax.lines[line - 2].strip()
        or syntax.lines[line - 2].startswith(indent + "#")
    ):
        line -= 1
    end = last.end_lineno
    while end < len(syntax.lines) and (
        not syntax.lines[end].strip() or syntax.lines[end].startswith(indent + "#")
    ):
        end += 1
    return reindent("".join(syntax.lines[line - 1 : end]), 0).strip("\n")


def function_source(source, original, transformed):
    syntax = definition_syntax(source)
    original = next(
        n
        for n in syntax.tree.body
        if isinstance(n, ast.FunctionDef) and n.name == original.name
    )
    start = syntax.starts[original.lineno - 1]
    depth = 0
    tokens = []
    for token in syntax.tokens_between(start, syntax.spans[original].end):
        tokens.append(token)
        if token.type == tokenize.OP:
            if token.string in ("(", "[", "{"):
                depth += 1
            elif token.string in (")", "]", "}"):
                depth -= 1
            elif token.string == ":" and depth == 0:
                break
    end = syntax.offset(*tokens[-1].end)
    name = next(
        t for t in tokens if t.type == tokenize.NAME and t.string == original.name
    )
    changes = [
        (
            Span(syntax.offset(*name.start) - start, syntax.offset(*name.end) - start),
            transformed.name,
        )
    ]
    removed = list(original.args.defaults) if not transformed.args.defaults else []
    removed += [
        a
        for a, b in zip(
            original.args.kw_defaults, transformed.args.kw_defaults, strict=True
        )
        if a is not None and b is None
    ]
    parameters = sequence(syntax, original).items if removed else ()
    for value in removed:
        span = syntax.spans[value]
        parameter = next(p for p in parameters if p.contains(span.start))
        parts = syntax.tokens_between(parameter.start, parameter.end)
        equal = next(
            t
            for t in reversed(parts)
            if t.string == "=" and syntax.offset(*t.end) <= span.start
        )
        # AST spans omit redundant parentheses. The parameter's final code
        # token closes the whole default, including those parentheses.
        last = next(
            t
            for t in reversed(parts)
            if t.type not in {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE}
        )
        left = syntax.offset(*equal.start)
        right = syntax.offset(*last.end)
        while left > start and source[left - 1] in " \t":
            left -= 1
        comments = [
            t.string
            for t in parts
            if t.type == tokenize.COMMENT and left <= syntax.offset(*t.start) < right
        ]
        replacement = "  " + "\n".join(comments) + "\n" if comments else ""
        changes.append((Span(left - start, right - start), replacement))
    signature = patches(source[start:end], changes)
    body = body_source(source, original.body)
    if original.body[0].lineno == original.lineno:
        body = source[end : syntax.starts[original.end_lineno]].strip()
    body = rewrite(body, ast.Module(body=transformed.body, type_ignores=[]))
    return signature + "\n" + reindent(body, 4).rstrip("\n")
