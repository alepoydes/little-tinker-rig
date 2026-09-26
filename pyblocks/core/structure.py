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
    old = (
        node.arg
        if isinstance(node, ast.arg)
        else node.id if isinstance(node, ast.Name) else node.name
    )
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
        if ref is node:
            continue
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


def declare_scope(session, node, name, kind):
    """Declare one outer binding at the start of the containing function."""
    if (
        kind not in {"global", "nonlocal"}
        or not name.isidentifier()
        or keyword.iskeyword(name)
    ):
        raise ValueError("Choose a scope and a Python variable name")
    syntax = session.document.syntax
    function = next(
        (
            n
            for n in syntax.ancestors(node)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ),
        None,
    )
    if function is None:
        raise ValueError("Select code inside a function")
    cls = ast.Global if kind == "global" else ast.Nonlocal
    scope = session.analysis.defined_scopes[function]
    changes = []
    for declaration in ast.walk(function):
        if (
            not isinstance(declaration, (ast.Global, ast.Nonlocal))
            or session.analysis.scopes[declaration] is not scope
            or name not in declaration.names
        ):
            continue
        if isinstance(declaration, cls):
            return False
        names = [n for n in declaration.names if n != name]
        changes.append(
            (
                syntax.spans[declaration],
                ast.unparse(type(declaration)(names=names)) if names else "",
            )
        )
    index = int(bool(ast.get_docstring(function)))
    suite = next(s for s in syntax.suites if s.owner is function and s.field == "body")
    offset, indent = edit.target_position(syntax, edit.Target(suite, index))
    changes.append((Span(offset, offset), " " * indent + kind + " " + name + "\n"))
    return session.editor.commit(edit.patches(syntax.source, changes), focus=offset)


def add_import(session, module, names=""):
    """An explicit import belongs to the user header and survives unused inputs."""
    statement = f"from {module} import {names}" if names.strip() else f"import {module}"
    tree = ast.parse(statement)
    if len(tree.body) != 1 or not isinstance(
        tree.body[0], (ast.Import, ast.ImportFrom)
    ):
        raise ValueError("Enter a module and imported names")
    syntax = session.document.syntax
    signature = ast.dump(tree.body[0])
    if any(ast.dump(n) == signature for n in syntax.tree.body):
        return False
    offset = 0
    for index, node in enumerate(syntax.tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)) or (
            index == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            offset = syntax.block_span(node).end
        else:
            break
    # Managed imports end with a boundary comment. Keep explicit imports outside it.
    from .imports import managed_section

    section = managed_section(syntax.source)
    if section:
        offset = max(offset, section.end)
    return session.editor.commit(
        edit.patches(
            syntax.source, [(Span(offset, offset), ast.unparse(tree.body[0]) + "\n")]
        ),
        focus=offset,
    )


def function_field(session, function, kind):
    """Add an editable decorator or return annotation without a Python dialog."""
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError("Select a function")
    syntax = session.document.syntax
    if kind == "decorator":
        offset = syntax.spans[function].start
        text = "@(...)\n" + " " * function.col_offset
        source = edit.patches(syntax.source, [(Span(offset, offset), text)])
        focus = offset + 2
    elif kind == "returns":
        if function.returns is not None:
            session.editor.selection = function.returns
            return
        offset = sequence(syntax, function).span.end + 1
        source = edit.patches(syntax.source, [(Span(offset, offset), " -> ...")])
        focus = offset + 4
    else:
        raise ValueError("Unknown function field")
    session.editor.commit(source, focus=focus)


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
        if self.kind not in {"operands", "comparisons"}:
            if isinstance(self.node, (ast.List, ast.Tuple, ast.Set)):
                nodes = self.node.elts
            elif isinstance(self.node, ast.Dict):
                nodes = [
                    n for n in (*self.node.keys, *self.node.values) if n is not None
                ]
            else:
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
        if self.kind == "comparisons":
            operators = [
                self.syntax.source[s.start : s.end]
                for s, _, _ in operator_spans(self.syntax, self.node)
            ]
            if action == "insert":
                operators.insert(
                    max(0, index - 1),
                    operators[min(max(0, index - 1), len(operators) - 1)],
                )
            elif action == "remove":
                operators.pop(max(0, index - 1))
            replacement = "".join(
                f"({value})" + (" " + operators[i] + " " if i < len(operators) else "")
                for i, value in enumerate(values)
            )
            if self.suffix:
                replacement = "(\n" + self.suffix + "\n" + replacement + "\n)"
            return edit.replace_expressions(self.syntax, [(self.span, replacement)])
        if self.kind == "operands":
            operator = " and " if isinstance(self.node.op, ast.And) else " or "
            # Explicit grouping preserves evaluation order when inserting another
            # logical expression. replace_expressions removes only safe brackets.
            replacement = operator.join(f"({value})" for value in values)
            if self.suffix:
                replacement = "(\n" + self.suffix + "\n" + replacement + "\n)"
            return edit.replace_expressions(self.syntax, [(self.span, replacement)])
        replacement = join_items(values)
        if isinstance(self.node, ast.Tuple) and len(values) == 1:
            replacement = replacement.rstrip().rstrip(",") + ","
        if comments:
            replacement += "\n" + "\n".join(t.string for t in comments) + "\n"
        if isinstance(self.node, ast.Set) and not values:
            return edit.replace_expressions(
                self.syntax, [(self.syntax.spans[self.node], "set()")]
            )
        if self.span == self.syntax.spans[self.node]:
            replacement = "(" + replacement + ")"
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
    if isinstance(node, (ast.BoolOp, ast.Compare)):
        span = syntax.spans[node]
        items = tuple(
            syntax.spans[n]
            for n in (
                node.values
                if isinstance(node, ast.BoolOp)
                else (node.left, *node.comparators)
            )
        )
        comments = "\n".join(
            t.string
            for t in syntax.tokens_between(span.start, span.end)
            if t.type == tokenize.COMMENT
            and not any(s.contains(syntax.offset(*t.start)) for s in items)
        )
        return Sequence(
            syntax,
            node,
            syntax.spans[node],
            items,
            "operands" if isinstance(node, ast.BoolOp) else "comparisons",
            2,
            comments,
        )
    if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        span = syntax.spans[node]
        start = span.start
        kind = "entries" if isinstance(node, ast.Dict) else "items"
        if isinstance(node, ast.Tuple) and not syntax.text(node).startswith("("):
            return Sequence(
                syntax, node, span, tuple(syntax.spans[n] for n in node.elts), kind
            )
    elif isinstance(node, ast.Call):
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
            if token.string in {"(", "[", "{"} and depth == 0:
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
OPERATORS["assignment operator"] = tuple(
    op + "=" for op in OPERATORS["binary operator"]
)


def operator_spans(syntax, node):
    if isinstance(node, ast.BinOp):
        operands, kind = (node.left, node.right), "binary operator"
    elif isinstance(node, ast.Compare):
        operands, kind = (node.left, *node.comparators), "comparison"
    elif isinstance(node, ast.BoolOp):
        operands, kind = node.values, "boolean operator"
    elif isinstance(node, ast.AugAssign):
        operands, kind = (node.target, node.value), "assignment operator"
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

    if isinstance(node, ast.AugAssign):
        if operator not in OPERATORS["assignment operator"]:
            raise ValueError("Choose an assignment operator")
        span, _, _ = next(operator_spans(syntax, node))
        source = edit.patches(syntax.source, [(span, operator)])
        syntax.validate(source)
        return source
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
