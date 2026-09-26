"""Per-block source/definition projections. All edits still address source offsets."""

import ast
import textwrap
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from difflib import SequenceMatcher

from .helpers import helper_section
from .snippets import Match, instantiate
from .syntax import Span


@dataclass
class BlockDisplay:
    match: Match
    source: Span
    mode: str
    effective: str
    shown: Span
    preview: Span | None = None


class Display:
    def __init__(self, session, modes=()):
        syntax = session.document.syntax
        self.source = syntax.source
        self.helpers = helper_section(syntax.source)
        self.blocks = []
        self.pieces = []
        parts = []
        position = 0
        size = 0
        replacements = []

        def append(start, end, text):
            nonlocal size
            original = self.source[start:end]
            if original == text:
                self.pieces.append((start, end, size, size + len(text)))
            else:
                for _, a, b, c, d in SequenceMatcher(
                    None, original, text, autojunk=False
                ).get_opcodes():
                    self.pieces.append((start + a, start + b, size + c, size + d))
            parts.append(text)
            size += len(text)

        def unchanged(start, end):
            if self.helpers and start <= self.helpers.start and self.helpers.end <= end:
                append(
                    start, self.helpers.start, self.source[start : self.helpers.start]
                )
                append(self.helpers.start, self.helpers.end, "")
                append(self.helpers.end, end, self.source[self.helpers.end : end])
            else:
                append(start, end, self.source[start:end])

        modes = dict(modes)
        matches = session.visible_matches
        match_starts = [m.span.start for m in matches]
        statements = sorted(syntax.statement_suite, key=lambda n: syntax.spans[n].start)
        statement_starts = [syntax.spans[n].start for n in statements]
        commented = set()
        for owner in syntax.owned_comments:
            span = syntax.spans[owner]
            index = bisect_right(match_starts, span.start) - 1
            if index >= 0 and span.end <= matches[index].span.end:
                commented.add(matches[index].span)
        for match in matches:
            snippet = match.snippet
            if not snippet.definition and snippet.mode != "function":
                continue
            span = match.span
            if not snippet.expression:
                nodes = [
                    n
                    for n in statements[
                        bisect_left(statement_starts, span.start) : bisect_left(
                            statement_starts, span.end
                        )
                    ]
                    if span.start <= syntax.spans[n].start
                    and syntax.spans[n].end <= span.end
                ]
                if nodes:
                    span = Span(
                        min(syntax.owned_spans[n].start for n in nodes),
                        max(syntax.owned_spans[n].end for n in nodes),
                    )
            mode = modes.get((match.span.start, snippet.identity), "auto")
            effective = (
                ("source" if match.span in commented else "definition")
                if mode == "auto"
                else mode
            )
            if snippet.mode == "function":
                mode = effective = "source"
            text = self.source[span.start : span.end]
            preview = None
            if effective == "definition":
                text = instantiate(
                    snippet,
                    match.bindings,
                    local_names=match.locals,
                    formatted=True,
                ).source
                column = syntax.position(match.span.start)[1]
                if snippet.expression:
                    text = text.strip()
                    if "\n" in text:
                        preview = text
                        text = self.source[span.start : span.end]
                else:
                    text = textwrap.indent(text, " " * column) + "\n"
            block = BlockDisplay(match, span, mode, effective, Span(0, 0))
            self.blocks.append(block)
            replacements.append((span.start, span.end, text, block, False))
            if preview:
                statement = next(
                    n
                    for n in syntax.ancestors(syntax.at(match.span.start))
                    if isinstance(n, ast.stmt)
                )
                end = syntax.block_span(statement).end
                preview = textwrap.indent(preview, " " * statement.col_offset) + "\n"
                if end and self.source[end - 1] != "\n":
                    preview = "\n" + preview
                replacements.append((end, end, preview, block, True))
        for start, end, text, block, preview in sorted(
            replacements, key=lambda item: (item[0], item[1])
        ):
            unchanged(position, start)
            shown_start = size
            append(start, end, text)
            if preview:
                block.preview = Span(shown_start, size)
            else:
                block.shown = Span(shown_start, size)
            position = end
        unchanged(position, len(self.source))
        self.text = "".join(parts)
        self.by_span = {b.match.span: b for b in self.blocks}
        self.intervals = sorted(
            (
                (span, block)
                for block in self.blocks
                for span in (block.shown, block.preview)
                if span
            ),
            key=lambda pair: pair[0].start,
        )
        self.block_starts = [span.start for span, _ in self.intervals]
        self.starts = [p[0] for p in self.pieces]
        self.shown_starts = [p[2] for p in self.pieces]
        self.line_starts = [0]
        for line in self.text.splitlines(keepends=True):
            self.line_starts.append(self.line_starts[-1] + len(line))

    def forward(self, offset):
        index = max(0, bisect_right(self.starts, offset) - 1)
        a, b, c, d = self.pieces[index]
        return c + min(offset - a, d - c) if b - a == d - c else c

    def backward(self, offset):
        index = max(0, bisect_right(self.shown_starts, offset) - 1)
        a, b, c, d = self.pieces[index]
        return a + min(offset - c, b - a) if b - a == d - c else a

    def position(self, offset):
        index = bisect_right(self.line_starts, offset) - 1
        return index + 1, offset - self.line_starts[index]

    def block_at(self, offset):
        index = bisect_right(self.block_starts, offset) - 1
        if index >= 0 and self.intervals[index][0].contains(offset):
            return self.intervals[index][1]
        return None

    def bounds(self, span):
        start, end = self.forward(span.start), self.forward(span.end)
        for block in self.blocks:
            if (
                span.start <= block.match.span.start
                and block.match.span.end <= span.end
            ):
                start = min(start, block.shown.start)
                end = max(
                    end, block.shown.end, block.preview.end if block.preview else 0
                )
        return Span(start, end)
