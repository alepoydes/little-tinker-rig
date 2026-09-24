"""Source transformations. Inputs stay untouched; callers commit the result."""

import ast
import io
import tokenize
from dataclasses import dataclass
from difflib import SequenceMatcher

from .syntax import Span, Suite, Syntax


@dataclass(frozen=True)
class Target:
    """Insertion before statements[index], or at the end of a suite."""

    suite: Suite
    index: int


def patches(source: str, changes: list[tuple[Span, str]]) -> str:
    """Apply nonoverlapping replacements in original-source coordinates."""
    cursor = 0
    parts = []
    for span, replacement in sorted(changes, key=lambda item: item[0]):
        if not cursor <= span.start <= span.end <= len(source):
            raise ValueError("Overlapping or invalid source changes")
        parts.extend((source[cursor : span.start], replacement))
        cursor = span.end
    parts.append(source[cursor:])
    return "".join(parts)


def map_offset(previous: str, source: str, offset: int) -> int:
    """Follow an existing source character through formatting or inserted imports."""
    if source == previous:
        return min(offset, len(source))
    # Most edits preserve the viewport's prefix or suffix. Avoid a quadratic
    # character diff over a whole document, especially repeated code/indentation.
    prefix = next(
        (i for i, (a, b) in enumerate(zip(previous, source, strict=False)) if a != b),
        min(len(previous), len(source)),
    )
    if offset < prefix:
        return offset
    suffix = 0
    limit = min(len(previous), len(source)) - prefix
    while suffix < limit and previous[-suffix - 1] == source[-suffix - 1]:
        suffix += 1
    if offset >= len(previous) - suffix:
        return len(source) - (len(previous) - offset)
    old, new = (
        previous[prefix : len(previous) - suffix or None],
        source[prefix : len(source) - suffix or None],
    )
    old_lines, new_lines = old.splitlines(keepends=True), new.splitlines(keepends=True)
    old_starts, new_starts = [0], [0]
    for lines, starts in ((old_lines, old_starts), (new_lines, new_starts)):
        for line in lines:
            starts.append(starts[-1] + len(line))
    for tag, a, b, c, d in SequenceMatcher(
        None, old_lines, new_lines, autojunk=False
    ).get_opcodes():
        start, end, new_start, new_end = (
            old_starts[a],
            old_starts[b],
            new_starts[c],
            new_starts[d],
        )
        if start <= offset - prefix < end:
            if tag == "equal":
                return new_start + offset - start
            # Changes within one line retain their character-level anchor.
            if b - a == d - c == 1:
                for _, x, y, u, v in SequenceMatcher(
                    None, old[start:end], new[new_start:new_end], autojunk=False
                ).get_opcodes():
                    if x <= offset - prefix - start < y:
                        return (
                            prefix
                            + new_start
                            + u
                            + min(offset - prefix - start - x, v - u)
                        )
            return (
                prefix + new_start + min(offset - prefix - start, new_end - new_start)
            )
    return len(source)


def reindent(source: str, indent: int) -> str:
    """Shift code indentation without changing multiline string contents."""
    lines = source.splitlines(keepends=True)
    if not lines:
        return ""
    protected = set()
    strings = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.STRING:
                protected.update(range(token.start[0] + 1, token.end[0] + 1))
            kind = tokenize.tok_name[token.type]
            if kind in {"FSTRING_START", "TSTRING_START"}:
                strings.append(token.start[0])
            elif kind in {"FSTRING_END", "TSTRING_END"}:
                protected.update(range(strings.pop() + 1, token.end[0] + 1))
    except (tokenize.TokenError, IndentationError) as error:
        raise ValueError(f"Incomplete fragment: {error}") from error
    first = next((line for line in lines if line.strip()), "")
    old = len(first) - len(first.lstrip(" "))
    result = []
    for row, line in enumerate(lines, 1):
        if row in protected or not line.strip():
            result.append(line)
        elif line[:old].strip():
            raise ValueError("Fragment has inconsistent indentation")
        else:
            result.append(" " * indent + line[old:])
    return "".join(result).rstrip("\n") + "\n"


def targets(syntax: Syntax):
    for suite in syntax.suites:
        for index in range(len(suite.statements) + 1):
            yield Target(suite, index)


def target_position(syntax: Syntax, target: Target) -> tuple[int, int]:
    """Return the insertion offset and its indentation in spaces."""
    suite, index = target.suite, target.index
    if not any(suite is item for item in syntax.suites):
        raise ValueError("Insertion target belongs to another source revision")
    if not 0 <= index <= len(suite.statements):
        raise ValueError("Insertion index outside suite")
    if not suite.statements:
        return len(syntax.source), 0
    node = suite.statements[min(index, len(suite.statements) - 1)]
    span = syntax.block_span(node)
    offset = span.start if index < len(suite.statements) else span.end
    return offset, syntax.position(syntax.spans[node].start)[1]


def _insertion(syntax: Syntax, target: Target, fragment: str) -> tuple[Span, str]:
    offset, indent = target_position(syntax, target)
    span = Span(offset, offset)
    statements = target.suite.statements
    if len(statements) == 1 and isinstance(statements[0], ast.Pass):
        span = syntax.block_span(statements[0])
        # Keep comments belonging to the slot when replacing its pass.
        text = syntax.source[span.start : span.end]
        comments = "".join(
            line
            for line in text.splitlines(keepends=True)
            if line.lstrip().startswith("#")
        )
        trailing = syntax.source[syntax.spans[statements[0]].end : span.end].strip()
        if trailing.startswith("#"):
            comments += " " * indent + trailing + "\n"
    else:
        comments = ""
    text = comments + reindent(fragment, indent)
    if offset and syntax.source[offset - 1] != "\n":
        text = "\n" + text
    return span, text


def insert(syntax: Syntax, target: Target, fragment: str) -> str:
    result = patches(syntax.source, [_insertion(syntax, target, fragment)])
    syntax.validate(result)
    return result


def insertion_targets(syntax: Syntax, fragment: str):
    """Yield only destinations where the inserted fragment compiles in context."""
    for target in targets(syntax):
        try:
            insert(syntax, target, fragment)
        except (ValueError, SyntaxError):
            continue
        yield target


def statement_group(
    syntax: Syntax, nodes: ast.stmt | tuple[ast.stmt, ...]
) -> tuple[Suite, Span, int]:
    """A movable statement group is a nonempty contiguous part of one suite."""
    nodes = (nodes,) if isinstance(nodes, ast.stmt) else nodes
    if not nodes:
        raise ValueError("Select at least one statement")
    suite = syntax.statement_suite[nodes[0]]
    start = suite.statements.index(nodes[0])
    if suite.statements[start : start + len(nodes)] != nodes:
        raise ValueError("Statements must be consecutive members of one suite")
    span = Span(syntax.block_span(nodes[0]).start, syntax.block_span(nodes[-1]).end)
    return suite, span, len(nodes)


def _removal(syntax: Syntax, node: ast.stmt | tuple[ast.stmt, ...]) -> tuple[Span, str]:
    suite, span, count = statement_group(syntax, node)
    first = node if isinstance(node, ast.stmt) else node[0]
    indent = syntax.position(syntax.spans[first].start)[1]
    replacement = ""
    if len(suite.statements) == count and not isinstance(suite.owner, ast.Module):
        replacement = " " * indent + "pass\n"
    return span, replacement


def delete(syntax: Syntax, node: ast.AST) -> str:
    if isinstance(node, ast.stmt):
        result = patches(syntax.source, [_removal(syntax, node)])
    elif isinstance(node, ast.expr):
        result = patches(syntax.source, [(syntax.spans[node], "None")])
    else:
        raise ValueError("Select a statement or expression")
    syntax.validate(result)
    return result


def replace_expressions(syntax: Syntax, changes: list[tuple[Span, str]]) -> str:
    """Keep grouping only when the unparenthesized text changes the Python AST."""
    changes = [(span, text.strip()) for span, text in changes]
    for _, text in changes:
        ast.parse(text, mode="eval")
    protected = patches(syntax.source, [(span, f"({text})") for span, text in changes])
    expected = syntax.validate(protected)
    plain = patches(syntax.source, changes)
    try:
        actual = syntax.validate(plain)
    except SyntaxError:
        return protected
    return plain if ast.dump(actual) == ast.dump(expected) else protected


def replace(syntax: Syntax, node: ast.AST, fragment: str) -> str:
    if isinstance(node, ast.Module):
        result = fragment
    elif isinstance(node, ast.stmt):
        indent = syntax.position(syntax.spans[node].start)[1]
        result = patches(
            syntax.source, [(syntax.block_span(node), reindent(fragment, indent))]
        )
    elif isinstance(node, ast.expr):
        result = replace_expressions(syntax, [(syntax.spans[node], fragment)])
    else:
        raise ValueError("Select a statement or expression")
    syntax.validate(result)
    return result


def move(
    syntax: Syntax, node: ast.AST | tuple[ast.stmt, ...], target: Target | ast.expr
) -> str:
    if isinstance(node, ast.expr):
        span = syntax.spans[node]
        if isinstance(target, ast.expr):
            destination = syntax.spans[target]
            if span.start < destination.end and destination.start < span.end:
                raise ValueError("Cannot move an expression into itself")
            return replace_expressions(
                syntax, [(span, "None"), (destination, syntax.text(node))]
            )
        insertion = _insertion(syntax, target, syntax.text(node))
        if span.start <= insertion[0].start <= span.end:
            raise ValueError("Cannot move an expression into itself")
        result = patches(syntax.source, [(span, "None"), insertion])
        syntax.validate(result)
        return result
    if not isinstance(target, Target):
        raise ValueError("Only expressions fit in parameters")
    removed = _removal(syntax, node)
    span = removed[0]
    offset, _ = target_position(syntax, target)
    if span.start <= offset <= span.end:
        raise ValueError("Cannot move a block into itself or to the same position")
    insertion = _insertion(syntax, target, syntax.source[span.start : span.end])
    result = patches(syntax.source, [removed, insertion])
    syntax.validate(result)
    return result
