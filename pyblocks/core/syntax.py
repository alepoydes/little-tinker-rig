"""A disposable structural index over one immutable source string.

Public offsets count Unicode characters; AST columns count UTF-8 bytes. The
conversion belongs here, so frontends never need to interpret AST coordinates.
"""

import ast
import io
import tokenize
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from functools import cached_property


@dataclass(frozen=True, order=True)
class Span:
    """Half-open character interval [start, end)."""

    start: int
    end: int

    def contains(self, offset: int) -> bool:
        return self.start <= offset < self.end


@dataclass(frozen=True)
class Suite:
    """An ordered statement list owned by an AST field, e.g. If.orelse."""

    owner: ast.AST
    field: str
    statements: tuple[ast.stmt, ...]


def parse(source: str, *, fragment: bool = False) -> ast.Module:
    """Validate syntax *and* compiler context without executing the program."""
    tree = ast.parse(source)
    if not fragment:
        compile(tree, "<pyblocks>", "exec", dont_inherit=True)
    return tree


class Syntax:
    """Index one source revision. Nodes and suites must not cross revisions."""

    def __init__(self, source: str, *, fragment: bool = False):
        self.source = source
        self.fragment = fragment
        self.tree = self.validate(source)
        self.lines = source.splitlines(keepends=True)
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line))
        self.spans = {self.tree: Span(0, len(source))}
        self.parent: dict[ast.AST, ast.AST] = {}
        self.children: dict[ast.AST, list[ast.AST]] = {self.tree: []}
        self.suites: list[Suite] = []
        self.statement_suite: dict[ast.stmt, Suite] = {}

        def visit(node: ast.AST, parent: ast.AST) -> None:
            if hasattr(node, "end_lineno") and node.end_lineno is not None:
                start = self._ast_offset(node.lineno, node.col_offset)
                decorators = getattr(node, "decorator_list", ())
                if decorators:
                    start = (
                        self._ast_offset(decorators[0].lineno, decorators[0].col_offset)
                        - 1
                    )  # Include the @, which is outside the expression's span.
                self.spans[node] = Span(
                    start, self._ast_offset(node.end_lineno, node.end_col_offset)
                )
                self.parent[node] = parent
                self.children[parent].append(node)
                self.children[node] = []
                parent = node
            for field, value in ast.iter_fields(node):
                if isinstance(value, list):
                    if (value and all(isinstance(n, ast.stmt) for n in value)) or (
                        node is self.tree and field == "body"
                    ):
                        suite = Suite(node, field, tuple(value))
                        self.suites.append(suite)
                        self.statement_suite.update((n, suite) for n in value)
                    for child in value:
                        if isinstance(child, ast.AST):
                            visit(child, parent)
                elif isinstance(value, ast.AST):
                    visit(value, parent)

        visit(self.tree, self.tree)
        self.owned_spans = dict(self.spans)
        for node in self.statement_suite:
            try:
                self.owned_spans[node] = self.block_span(node)
            except ValueError:
                pass  # Non-isolated fmt:off statements keep their exact AST span.

        # Wide suites need logarithmic hit testing. Prefix maxima retain the
        # original first-owner rule even for overlapping f-string AST spans.
        self._child_ranges = {}
        for parent, children in self.children.items():
            if len(children) <= 8:
                continue
            ordered = sorted(
                enumerate(children), key=lambda pair: self.owned_spans[pair[1]].start
            )
            starts, ends, longest = [], [], 0
            for _, child in ordered:
                span = self.owned_spans[child]
                starts.append(span.start)
                longest = max(longest, span.end)
                ends.append(longest)
            self._child_ranges[parent] = (ordered, starts, ends)

    def validate(self, source):
        return parse(source, fragment=self.fragment)

    def path(self, node):
        """Follow a node through expression edits and managed-prefix changes."""
        result = []
        while node is not self.tree:
            parent = self.parent[node]
            index = self.children[parent].index(node)
            # Imports/helpers can be added before the user's statements.
            result.append(
                index - len(self.children[parent]) if parent is self.tree else index
            )
            node = parent
        return tuple(reversed(result))

    def follow(self, path):
        node = self.tree
        for index in path:
            node = self.children[node][index]
        return node

    @cached_property
    def tokens(self):
        return tuple(tokenize.generate_tokens(io.StringIO(self.source).readline))

    @cached_property
    def token_starts(self):
        return tuple(self.offset(*token.start) for token in self.tokens)

    def tokens_between(self, start, end):
        return self.tokens[
            bisect_left(self.token_starts, start) : bisect_left(self.token_starts, end)
        ]

    def _ast_offset(self, line: int, byte_column: int) -> int:
        prefix = self.lines[line - 1].encode("utf-8")[:byte_column]
        return self.starts[line - 1] + len(prefix.decode("utf-8"))

    def offset(self, line: int, column: int = 0) -> int:
        """Convert a 1-based line and 0-based character column to an offset."""
        if line < 1 or line > len(self.starts) or column < 0:
            raise ValueError("Position outside source")
        end = self.starts[line] if line < len(self.starts) else len(self.source)
        result = self.starts[line - 1] + column
        if result > end:
            raise ValueError("Column outside line")
        return result

    def position(self, offset: int) -> tuple[int, int]:
        """Convert a character offset to (1-based line, 0-based column)."""
        if not 0 <= offset <= len(self.source):
            raise ValueError("Offset outside source")
        row = bisect_right(self.starts, offset) - 1
        if row == len(self.lines) and self.lines and not self.lines[-1].endswith("\n"):
            row -= 1
        return row + 1, offset - self.starts[row]

    def at(self, offset: int) -> ast.AST:
        """Deepest owner; attached comments and indentation belong to statements."""
        if not 0 <= offset <= len(self.source):
            raise ValueError("Offset outside source")
        spans, starts = self.comment_index
        index = bisect_right(starts, offset) - 1
        if index >= 0 and spans[index].contains(offset):
            return self.comment_owners[spans[index]]
        node = self.tree
        while True:
            if node in self._child_ranges:
                ordered, starts, ends = self._child_ranges[node]
                index = bisect_right(starts, offset) - 1
                found = None
                while index >= 0 and ends[index] > offset:
                    order, candidate = ordered[index]
                    if self.owned_spans[candidate].contains(offset) and (
                        found is None or order < found[0]
                    ):
                        found = (order, candidate)
                    index -= 1
                child = found[1] if found else None
            else:
                child = next(
                    (
                        n
                        for n in self.children[node]
                        if self.owned_spans[n].contains(offset)
                    ),
                    None,
                )
            if child is None:
                return node
            node = child

    def ancestors(self, node: ast.AST):
        """Yield the node and successive indexed parents, ending at Module."""
        while True:
            yield node
            if node not in self.parent:
                break
            node = self.parent[node]

    def text(self, node: ast.AST) -> str:
        span = self.spans[node]
        return self.source[span.start : span.end]

    @cached_property
    def comment_owners(self):
        """Comments attach to code, independently of blank-line formatting."""
        statements = sorted(self.statement_suite, key=lambda n: self.spans[n].start)
        starts = [self.spans[n].start for n in statements]
        result = {}
        for token in self.tokens:
            if token.type != tokenize.COMMENT:
                continue
            span = Span(self.offset(*token.start), self.offset(*token.end))
            line, column = token.start
            prefix = self.lines[line - 1][:column]
            if token.string.startswith(("#!", "# -*-", "# coding", "# ---")) or (
                line == 1
                and any(
                    word in token.string.lower()
                    for word in ("copyright", "license", "adapted from")
                )
            ):
                owner = self.tree
            elif prefix.strip():
                index = bisect_right(starts, span.start) - 1
                owner = next(
                    (
                        n
                        for n in reversed(statements[: index + 1])
                        if n.end_lineno >= line
                    ),
                    self.tree,
                )
            else:
                index = bisect_right(starts, span.start)
                following = next(
                    (n for n in statements[index:] if n.col_offset <= column), None
                )
                same_suite = following is not None and not any(
                    text.strip()
                    and not text.lstrip().startswith("#")
                    and len(text) - len(text.lstrip()) < column
                    for text in self.lines[line : following.lineno - 1]
                )
                if (
                    following is not None
                    and following.col_offset == column
                    and same_suite
                ):
                    owner = following
                else:
                    owner = next(
                        (
                            n
                            for n in reversed(statements[:index])
                            if n.col_offset < column
                            and any(s.owner is n for s in self.suites)
                        ),
                        self.tree,
                    )
            result[span] = owner
        # A docstring belongs to its definition, never to a separate action block.
        for node in self.spans:
            if (
                isinstance(
                    node,
                    (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                )
                and ast.get_docstring(node) is not None
            ):
                result[self.spans[node.body[0]]] = node
        return result

    @cached_property
    def owned_comments(self):
        result = {}
        for span, owner in self.comment_owners.items():
            result.setdefault(owner, []).append(span)
        return result

    @cached_property
    def comment_index(self):
        spans = sorted(self.comment_owners)
        return spans, [span.start for span in spans]

    def block_span(self, node: ast.stmt) -> Span:
        """Whole lines, including adjacent leading and inline comments.

        Blank lines do not detach leading comments. File headers stay with the file.
        A non-isolated statement (e.g. fmt:off with semicolons) is rejected:
        editing a partial line as a statement could silently change neighbours.
        """
        span = self.spans[node]
        first, column = self.position(span.start)
        last, _ = self.position(span.end)
        prefix = self.lines[first - 1][:column]
        suffix = self.source[span.end : self.starts[last]]
        if prefix.strip() or (suffix.strip() and not suffix.lstrip().startswith("#")):
            raise ValueError("Statement must occupy its own lines; format it first")
        for comment in self.owned_comments.get(node, ()):
            first = min(first, self.position(comment.start)[0])
            last = max(last, self.position(comment.end)[0])
        return Span(self.starts[first - 1], self.starts[last])
