"""Names and variable-length parts of Python, indexed from the current source."""

import ast
import io
import keyword
import tokenize
from dataclasses import dataclass

from . import edit
from .syntax import Span, Syntax


def token_span(syntax, token):
    return Span(syntax.offset(*token.start), syntax.offset(*token.end))


def name_span(syntax, node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        start = syntax.spans[node].start
        tokens = iter(syntax.tokens_between(start, syntax.spans[node].end))
        for token in tokens:
            if token.string in {"def", "class"}:
                return token_span(syntax, next(tokens))
    if isinstance(node, ast.Attribute):
        span = syntax.spans[node]
        return token_span(
            syntax,
            next(
                t
                for t in reversed(syntax.tokens_between(span.start, span.end))
                if t.type == tokenize.NAME
            ),
        )
    if isinstance(node, (ast.arg, ast.keyword)):
        span = syntax.spans[node]
        return token_span(
            syntax,
            next(
                t
                for t in syntax.tokens_between(span.start, span.end)
                if t.type == tokenize.NAME
            ),
        )
    return syntax.spans[node]


def rename(session, node, name):
    """Rename a lexical definition and its resolved references in one revision."""
    if not name.isidentifier() or keyword.iskeyword(name):
        raise ValueError("Enter a Python identifier")
    syntax, analysis = session.document.syntax, session.analysis
    old = node.arg if isinstance(node, ast.arg) else node.name
    scope = analysis.resolve(node, old)
    if name != old and name in scope.bindings:
        raise ValueError(f"Name {name!r} is already defined in this scope")
    for other in syntax.spans:
        if other is node or analysis.scopes.get(other) is not scope:
            continue
        if (
            isinstance(
                other,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.ExceptHandler,
                ),
            )
            and getattr(other, "name", None) == old
        ):
            raise ValueError(
                "This name has another declaration; edit the declarations as Python"
            )
        if isinstance(other, (ast.Import, ast.ImportFrom)) and any(
            (a.asname or a.name.split(".")[0]) == old for a in other.names
        ):
            raise ValueError(
                "This name is also imported; edit the declarations as Python"
            )
    changes = [(name_span(syntax, node), name)]
    for ref in syntax.spans:
        if (
            isinstance(ref, ast.Name)
            and ref.id == old
            and analysis.resolve(ref, old) is scope
        ):
            # A new name must not capture references in nested scopes.
            current = analysis.scopes[ref]
            while current is not scope and current is not None:
                if name != old and name in current.bindings:
                    raise ValueError(f"Name {name!r} is shadowed in a nested scope")
                current = current.parent
            changes.append((syntax.spans[ref], name))
        elif isinstance(ref, (ast.Global, ast.Nonlocal)) and old in ref.names:
            owner = (
                analysis.root
                if isinstance(ref, ast.Global)
                else analysis.scopes[ref].parent
            )
            while owner is not None and old not in owner.bindings:
                owner = owner.parent
            if owner is scope:
                span = syntax.spans[ref]
                changes.extend(
                    (token_span(syntax, token), name)
                    for token in syntax.tokens
                    if token.string == old
                    and span.start <= syntax.offset(*token.start) < span.end
                )
    # Existing references to the new spelling must not be captured either.
    if name != old:
        for ref, _ in analysis.references:
            if ref.id != name:
                continue
            current = analysis.scopes[ref]
            while current is not None and name not in current.bindings:
                if current is scope:
                    raise ValueError(f"Renaming would capture {name!r}")
                current = current.parent
    if isinstance(node, ast.arg):
        definition = scope.node
        for call in ast.walk(syntax.tree):
            if (
                isinstance(call, ast.Call)
                and analysis.call_definition(call) is definition
            ):
                changes.extend(
                    (name_span(syntax, item), name)
                    for item in call.keywords
                    if item.arg == old
                )
    result = edit.patches(syntax.source, changes)
    syntax.validate(result)
    return result


@dataclass(frozen=True)
class Sequence:
    syntax: Syntax
    node: ast.AST
    span: Span
    items: tuple[Span, ...]
    kind: str
    minimum: int = 0
    suffix: str = ""

    def change(self, index, action, text=None):
        """Apply one insertion, deletion or adjacent move; validate before commit."""
        comments = []
        if self.kind != "operands":
            args = self.node.args
            nodes = (
                args + self.node.keywords
                if isinstance(self.node, ast.Call)
                else [
                    *args.posonlyargs,
                    *args.args,
                    *args.kwonlyargs,
                    *args.defaults,
                    *(n for n in args.kw_defaults if n is not None),
                    *(n for n in (args.vararg, args.kwarg) if n is not None),
                ]
            )
            spans = [self.syntax.spans[n] for n in nodes]
            comments = [
                token
                for token in self.syntax.tokens_between(self.span.start, self.span.end)
                if token.type == tokenize.COMMENT
                and not any(s.contains(self.syntax.offset(*token.start)) for s in spans)
            ]
        values = []
        for span in self.items:
            changes = [
                (
                    Span(
                        self.syntax.offset(*t.start) - span.start,
                        self.syntax.offset(*t.end) - span.start,
                    ),
                    "",
                )
                for t in comments
                if span.contains(self.syntax.offset(*t.start))
            ]
            values.append(
                edit.patches(self.syntax.source[span.start : span.end], changes).strip()
            )
        if action == "insert":
            if not 0 <= index <= len(values) or not text or not text.strip():
                raise ValueError("Enter an item and choose an insertion position")
            values.insert(index, text.strip())
        else:
            if not 0 <= index < len(values):
                raise ValueError("Select a list item")
            if action == "remove":
                if len(values) <= self.minimum:
                    raise ValueError(f"Keep at least {self.minimum} items")
                values.pop(index)
            elif action in {"left", "right"}:
                other = index + (-1 if action == "left" else 1)
                if not 0 <= other < len(values):
                    raise ValueError("The item is already at the end")
                values[index], values[other] = values[other], values[index]
            else:
                raise ValueError("Unknown list operation")
        if self.kind == "operands":
            operator = " and " if isinstance(self.node.op, ast.And) else " or "
            # Explicit grouping preserves evaluation order when inserting another
            # logical expression. replace_expressions removes only safe brackets.
            replacement = operator.join(f"({value})" for value in values)
            if self.suffix:
                replacement = "(\n" + self.suffix + "\n" + replacement + "\n)"
            return edit.replace_expressions(self.syntax, [(self.span, replacement)])
        replacement = join_items(values)
        if comments:
            replacement += "\n" + "\n".join(t.string for t in comments) + "\n"
        result = edit.patches(self.syntax.source, [(self.span, replacement)])
        self.syntax.validate(result)
        return result


def join_items(values):
    if not any("\n" in value or "#" in value for value in values):
        return ", ".join(values)
    result = []
    for value in values:
        lines = value.splitlines(keepends=True)
        starts = [0]
        for line in lines:
            starts.append(starts[-1] + len(line))
        tokens = [
            t
            for t in tokenize.generate_tokens(io.StringIO(value).readline)
            if t.type
            not in {
                tokenize.COMMENT,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.ENDMARKER,
            }
        ]
        if not tokens:
            raise ValueError("A list item must contain Python code")
        row, col = tokens[-1].end
        end = starts[row - 1] + col
        result.append(value[:end] + "," + value[end:])
    return "\n" + "\n".join(result) + "\n"


def sequence(syntax, node):
    if isinstance(node, ast.BoolOp):
        span = syntax.spans[node]
        items = tuple(syntax.spans[n] for n in node.values)
        comments = "\n".join(
            t.string
            for t in syntax.tokens_between(span.start, span.end)
            if t.type == tokenize.COMMENT
            and not any(s.contains(syntax.offset(*t.start)) for s in items)
        )
        return Sequence(
            syntax, node, syntax.spans[node], items, "operands", 2, comments
        )
    if isinstance(node, ast.Call):
        start = syntax.spans[node.func].end
        kind = "arguments"
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        start = name_span(syntax, node).end
        kind = "parameters"
    else:
        return None
    # The first top-level '(' after the callable/name starts its list. Parentheses
    # closing a parenthesized callable precede it; type parameter brackets nest.
    depth = 0
    opened = None
    pieces = []
    lambdas = 0
    code_in_part = False
    for token in syntax.tokens_between(start, syntax.spans[node].end):
        if opened is None:
            if token.string == "(" and depth == 0:
                opened = token_span(syntax, token).end
                part = opened
                depth = 1
            elif token.string == "[":
                depth += 1
            elif token.string == "]":
                depth -= 1
            continue
        if token.type == tokenize.OP:
            if token.string in "([{":
                depth += 1
            elif token.string in ")]}":
                depth -= 1
                if depth == 0:
                    end = token_span(syntax, token).start
                    if code_in_part:
                        pieces.append(Span(part, end))
                    suffix = "" if code_in_part else syntax.source[part:end]
                    return Sequence(
                        syntax,
                        node,
                        Span(opened, end),
                        tuple(pieces),
                        kind,
                        suffix=suffix,
                    )
            elif token.string == ":" and depth == 1 and lambdas:
                lambdas -= 1
            elif token.string == "," and depth == 1 and not lambdas:
                end = token_span(syntax, token).start
                pieces.append(Span(part, end))
                part = token_span(syntax, token).end
                code_in_part = False
                continue
        elif token.string == "lambda" and depth == 1:
            lambdas += 1
        if token.type not in {
            tokenize.COMMENT,
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
        }:
            code_in_part = True
    raise ValueError("Cannot locate the argument list")


OPERATORS = {
    "binary operator": ("+", "-", "*", "/", "//", "%", "**", "&", "|", "^", "<<", ">>"),
    "comparison": ("==", "!=", "<", "<=", ">", ">=", "in", "not in", "is", "is not"),
    "boolean operator": ("and", "or"),
}


def operator_spans(syntax, node):
    if isinstance(node, ast.BinOp):
        operands, kind = (node.left, node.right), "binary operator"
    elif isinstance(node, ast.Compare):
        operands, kind = (node.left, *node.comparators), "comparison"
    elif isinstance(node, ast.BoolOp):
        operands, kind = node.values, "boolean operator"
    else:
        return
    for index, (left, right) in enumerate(zip(operands, operands[1:], strict=False)):
        start, end = syntax.spans[left].end, syntax.spans[right].start
        tokens = [
            token
            for token in syntax.tokens_between(start, end)
            if token.type in {tokenize.OP, tokenize.NAME}
            and token.string not in {"(", ")", "[", "]", "{", "}"}
        ]
        if tokens:
            yield Span(
                syntax.offset(*tokens[0].start), syntax.offset(*tokens[-1].end)
            ), kind, index


def change_operator(syntax, node, index, operator):
    import copy

    updated = copy.deepcopy(node)
    if isinstance(node, ast.BinOp):
        if operator not in OPERATORS["binary operator"]:
            raise ValueError("Choose an arithmetic operator")
        updated.op = ast.parse(f"a {operator} b", mode="eval").body.op
    elif isinstance(node, ast.Compare):
        if operator not in OPERATORS["comparison"]:
            raise ValueError("Choose a comparison operator")
        updated.ops[index] = ast.parse(f"a {operator} b", mode="eval").body.ops[0]
    else:
        if operator not in OPERATORS["boolean operator"]:
            raise ValueError("Choose and or or")
        updated.op = ast.And() if operator == "and" else ast.Or()
    return edit.replace_expressions(
        syntax,
        [(syntax.spans[node], with_comments(syntax, node, ast.unparse(updated)))],
    )


def with_comments(syntax, node, expression):
    span = syntax.spans[node]
    comments = [
        token.string
        for token in syntax.tokens
        if token.type == tokenize.COMMENT
        and span.start <= syntax.offset(*token.start) < span.end
    ]
    return (
        "(\n" + "\n".join(comments) + "\n" + expression + "\n)"
        if comments
        else expression
    )
