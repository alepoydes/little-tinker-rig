"""The shared application operations used by CLI, Qt and TUI."""

import ast
import io
import tokenize
from pathlib import Path

from . import edit
from .analysis import Analysis, Scopes, identifiers, value_type
from .document import Document
from .imports import manage_imports
from .interaction import Editor
from .project import Project
from .snippets import (
    Match,
    Snippet,
    builtin_snippets,
    instantiate,
    load_collection,
    recognize,
    upgrade,
)


class Session:
    def __init__(
        self,
        path: Path,
        collections: tuple[Path, ...] = (),
        *,
        allow_draft: bool = False,
    ):
        self.project = Project(path, allow_draft=allow_draft)
        for collection in collections:
            resolved = collection.resolve()
            if resolved not in self.project.collections:
                self.project.collections.append(resolved)
        self.editor = Editor(self.project.document)
        self.snippets = builtin_snippets() + tuple(
            s for path in self.project.collections for s in load_collection(path)
        )
        identities = [s.identity for s in self.snippets if not s.historical]
        if len(identities) != len(set(identities)):
            raise ValueError("Collections define duplicate current snippet identities")
        for snippet in self.snippets:
            collection = snippet.identity.split("/")[0]
            pinned = self.project.pins.get(collection)
            if pinned and not snippet.historical and pinned != snippet.version:
                raise ValueError(
                    f"Collection {collection!r} requires version {pinned}, installed {snippet.version}"
                )
        self._reset_cache()

    def _reset_cache(self):
        self._revision = None
        self._matches: tuple[Match, ...] = ()
        self._analysis = None
        self._expanded = set()

    @classmethod
    def fragment(cls, text, snippets):
        """A detached editing session: no file, imports or executable context."""
        session = cls.__new__(cls)
        session.project = None
        session.editor = Editor(Document(edit.reindent(text, 0), fragment=True))
        session.snippets = snippets
        session._reset_cache()
        return session

    def with_imports(self, source, required=()):
        if self.document.fragment:
            return source
        return manage_imports(source, required, retain=self.document.state.scratch)

    @property
    def document(self):
        return self.editor.document

    @property
    def matches(self) -> tuple[Match, ...]:
        self._refresh()
        return self._matches

    @property
    def analysis(self) -> Analysis:
        self._refresh()
        return self._analysis

    def _refresh(self):
        if self._revision is not self.document.syntax:
            self._analysis = Analysis(self.document.syntax)
            for snippet in self.snippets:
                body = snippet.body
                if (
                    snippet.expression
                    and snippet.result_type
                    and isinstance(body, ast.Call)
                    and isinstance(body.func, ast.Attribute)
                ):
                    receiver = getattr(body.func.value, "template_parameter", None)
                    parameter = next(
                        (p for p in snippet.parameters if p.name == receiver), None
                    )
                    if parameter and parameter.annotation:
                        self._analysis.method_types[
                            parameter.annotation, body.func.attr
                        ] = value_type(snippet.result_type)
            self._matches = recognize(
                self.document.syntax, self.snippets, self._analysis
            )
            self._revision = self.document.syntax
            self._expanded.clear()

    @property
    def visible_matches(self) -> tuple[Match, ...]:
        self._refresh()
        return tuple(
            match for match in self._matches if match.span not in self._expanded
        )

    def selected_match(self) -> Match | None:
        span = self.document.syntax.spans[self.editor.selection]
        return next(
            (
                m
                for m in self.visible_matches
                if m.span.start <= span.start and span.end <= m.span.end
            ),
            None,
        )

    def toggle_expansion(self) -> None:
        self._refresh()
        selected = self.document.syntax.spans[self.editor.selection]
        match = next(
            (
                m
                for m in self._matches
                if m.span.start <= selected.start and selected.end <= m.span.end
            ),
            None,
        )
        if match is None:
            raise ValueError("Select a recognized snippet to expand or collapse")
        if match.span in self._expanded:
            self._expanded.remove(match.span)
        else:
            self._expanded.add(match.span)

    def selected_text(self) -> str:
        match = self.selected_match()
        span = (
            match.span if match else self.document.syntax.spans[self.editor.selection]
        )
        if match and not match.snippet.expression:
            _, span, _ = edit.statement_group(
                self.document.syntax, self._match_nodes(match)
            )
        elif isinstance(self.editor.selection, ast.stmt):
            span = self.document.syntax.block_span(self.editor.selection)
        return self.document.state.source[span.start : span.end]

    def destination(self) -> edit.Target:
        """Default insertion is after the containing statement, or end of module."""
        syntax = self.document.syntax
        if self.editor.selection is syntax.tree:
            suite = syntax.suites[0]
            return edit.Target(suite, len(suite.statements))
        node = self.editor.statement()
        match = self.selected_match()
        if match and not match.snippet.expression:
            node = self._match_nodes(match)[-1]
        suite = syntax.statement_suite[node]
        if isinstance(node, ast.Pass):
            return edit.Target(suite, 0)
        return edit.Target(suite, suite.statements.index(node) + 1)

    def insert_snippet(
        self,
        snippet: Snippet,
        bindings: dict[str, str],
        target: edit.Target | None = None,
    ) -> None:
        syntax = self.document.syntax
        expansion = instantiate(snippet, bindings, identifiers(syntax.tree))
        if snippet.expression:
            if not isinstance(self.editor.selection, ast.expr):
                raise ValueError("Select an expression to replace with this snippet")
            offset = syntax.spans[self.editor.selection].start
            source = edit.replace(syntax, self.editor.selection, expansion.source)
        else:
            target = target or self.destination()
            offset = self.insertion_offset(target)
            source = edit.insert(syntax, target, expansion.source)
        self.commit_insertion(source, offset, expansion.imports)

    def insertion_offset(self, target):
        syntax = self.document.syntax
        statements = target.suite.statements
        if len(statements) == 1 and isinstance(statements[0], ast.Pass):
            return syntax.block_span(statements[0]).start
        return edit.target_position(syntax, target)[0]

    def commit_insertion(self, source, offset, required=(), scratch=None):
        imported = self.with_imports(source, required)
        self.editor.commit(
            imported, scratch, focus=edit.map_offset(source, imported, offset)
        )

    def _replace_match(self, match: Match, source: str) -> str:
        syntax = self.document.syntax
        if match.snippet.expression:
            return edit.patches(syntax.source, [(match.span, f"({source})")])
        nodes = self._match_nodes(match)
        suite, span, _ = edit.statement_group(syntax, nodes)
        indent = syntax.position(match.span.start)[1]
        if (
            not source.strip()
            and len(nodes) == len(suite.statements)
            and not isinstance(suite.owner, ast.Module)
        ):
            source = "pass"
        return edit.patches(syntax.source, [(span, edit.reindent(source, indent))])

    def _match_nodes(self, match: Match) -> tuple[ast.stmt, ...]:
        syntax = self.document.syntax
        first = syntax.at(match.span.start)
        first = next(
            n
            for n in syntax.ancestors(first)
            if isinstance(n, ast.stmt) and syntax.spans[n].start == match.span.start
        )
        suite = syntax.statement_suite[first]
        return tuple(
            n
            for n in suite.statements
            if match.span.start <= syntax.spans[n].start < match.span.end
        )

    def edit_python(self, source: str) -> None:
        match = self.selected_match()
        result = (
            self._replace_match(match, source)
            if match
            else edit.replace(self.document.syntax, self.editor.selection, source)
        )
        self.editor.commit(self.with_imports(result))

    def edit_parameters(self, bindings: dict[str, str]) -> None:
        match = self.selected_match()
        if match is None:
            raise ValueError("Select a recognized snippet")
        unknown = bindings.keys() - {p.name for p in match.snippet.parameters}
        if unknown:
            raise ValueError(f"Unknown parameters: {', '.join(sorted(unknown))}")
        changes = []
        for name, expression in bindings.items():
            ast.parse(expression, mode="eval")
            for node in match.occurrences.get(name, ()):
                changes.append((self.document.syntax.spans[node], expression))
        self.editor.commit(edit.replace_expressions(self.document.syntax, changes))

    def begin_move(self):
        match = self.selected_match()
        nodes = (
            self._match_nodes(match) if match and not match.snippet.expression else None
        )
        return self.editor.begin_move(nodes)

    def upgrade_selected(self) -> None:
        match = self.selected_match()
        if match is None or not match.snippet.historical:
            raise ValueError("Select a snippet recognized from a historical template")
        current = next(
            s
            for s in self.snippets
            if s.identity == match.snippet.identity and not s.historical
        )
        expansion = upgrade(match, current, identifiers(self.document.syntax.tree))
        comments = [
            token.string
            for token in tokenize.generate_tokens(
                io.StringIO(self.selected_text()).readline
            )
            if token.type == tokenize.COMMENT
        ]
        replacement = "\n".join([*comments, expansion.source])
        source = self._replace_match(match, replacement)
        self.editor.commit(self.with_imports(source, expansion.imports))

    def extract_selection(self):
        """Return detached text and the valid remainder, without changing state."""
        match = self.selected_match()
        source = (
            self._replace_match(match, "None" if match.snippet.expression else "")
            if match
            else edit.delete(self.document.syntax, self.editor.selection)
        )
        return edit.reindent(self.selected_text(), 0), source

    def to_scratch(self, position=None) -> None:
        text, source = self.extract_selection()
        scratch = list(self.document.state.scratch)
        scratch.insert(len(scratch) if position is None else position, text)
        self.editor.commit(source, tuple(scratch))

    def set_scratch(self, index: int | None, text: str) -> None:
        scratch = list(self.document.state.scratch)
        if index is None:
            scratch.append(text)
        else:
            if not 0 <= index < len(scratch):
                raise ValueError("Scratch index outside workspace")
            scratch[index] = text
        self.editor.commit(self.document.state.source, tuple(scratch))

    def fragment_imports(self, text):
        """Dependencies come from library definitions, never execute a module."""
        scope = Scopes(ast.parse(text))
        used = {
            node.id
            for node, _ in scope.references
            if scope.resolve(node, node.id) is None
        }
        required = set()
        for snippet in self.snippets:
            for node in snippet.imports:
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    if name in used:
                        single = (
                            ast.ImportFrom(
                                module=node.module, names=[alias], level=node.level
                            )
                            if isinstance(node, ast.ImportFrom)
                            else ast.Import(names=[alias])
                        )
                        required.add(ast.unparse(single))
        return tuple(sorted(required))

    def restore_scratch(self, index: int, target=None, *, fragment=None) -> None:
        scratch = self.document.state.scratch
        if not 0 <= index < len(scratch):
            raise ValueError("Scratch index outside workspace")
        text, remainder = (scratch[index], "") if fragment is None else fragment
        syntax = self.document.syntax
        node = target if isinstance(target, ast.expr) else self.editor.selection
        expression = False
        if isinstance(node, ast.expr) and not isinstance(target, edit.Target):
            try:
                ast.parse(text.strip(), mode="eval")
                expression = True
            except SyntaxError:
                pass
        if expression:
            offset = syntax.spans[node].start
            source = edit.replace(syntax, node, text)
        else:
            target = target or self.destination()
            offset = self.insertion_offset(target)
            source = edit.insert(syntax, target, text)
        remaining = (
            scratch[:index]
            + ((remainder,) if remainder.strip() else ())
            + scratch[index + 1 :]
        )
        self.commit_insertion(source, offset, self.fragment_imports(text), remaining)
