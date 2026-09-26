"""Preserve definition trivia while replacing corresponding Python expressions."""

import ast
import textwrap
import tokenize
from functools import lru_cache

from .edit import patches
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
    indent = first.col_offset
    while line > 1 and (
        not syntax.lines[line - 2].strip()
        or syntax.lines[line - 2].startswith(" " * indent + "#")
    ):
        line -= 1
    end = last.end_lineno
    while end < len(syntax.lines) and (
        not syntax.lines[end].strip()
        or syntax.lines[end].startswith(" " * indent + "#")
    ):
        end += 1
    return textwrap.dedent("".join(syntax.lines[line - 1 : end])).strip("\n")


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
    for value in removed:
        span = syntax.spans[value]
        equal = next(
            t
            for t in reversed(tokens)
            if t.string == "=" and syntax.offset(*t.end) <= span.start
        )
        left = syntax.offset(*equal.start)
        while left > start and source[left - 1] in " \t":
            left -= 1
        changes.append((Span(left - start, span.end - start), ""))
    signature = patches(source[start:end], changes)
    body = body_source(source, original.body)
    if original.body[0].lineno == original.lineno:
        body = source[end : syntax.starts[original.end_lineno]].strip()
    statements = list(transformed.body)
    if ast.get_docstring(original) is not None:
        # Dedenting the body also dedents the literal's physical lines. The
        # original indentation is restored below; keep its spelling intact.
        statements[0] = ast.parse(body).body[0]
    body = rewrite(body, ast.Module(body=statements, type_ignores=[]))
    return signature + "\n" + textwrap.indent(body, "    ")
