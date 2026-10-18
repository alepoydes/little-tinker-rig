"""The shared application operations used by CLI, Qt and TUI."""

import ast
import io
import tokenize
from bisect import bisect_right
from pathlib import Path

from . import edit
from .analysis import (
    Analysis,
    Scopes,
    annotation_types,
    attribute_path,
    identifiers,
)
from .document import Document
from .helpers import START as HELPERS_START
from .helpers import helper_section, manage_helpers
from .imports import manage_imports
from .interaction import Editor
from .paths import personal_collection
from .project import Project
from .snippets import (
    Match,
    Snippet,
    builtin_snippets,
    function_snippets,
    instantiate,
    load_collection,
    outer_matches,
    recognize,
    upgrade,
)
from .syntax import Syntax


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
        self.set_snippets(self.load_snippets())

    @property
    def collection_paths(self):
        personal = personal_collection()
        roots = [*self.project.collections]
        if (personal / "collection.toml").is_file():
            roots.append(personal)
        return tuple(dict.fromkeys(path.resolve() for path in roots))

    def load_snippets(self, overrides=None):
        """Read connected collections, optionally substituting a validated candidate."""
        overrides = overrides or {}
        return builtin_snippets() + tuple(
            s
            for path in self.collection_paths
            for s in (overrides[path] if path in overrides else load_collection(path))
        )

    def validate_snippets(self, snippets):
        identities = [s.identity for s in snippets if not s.historical]
        if len(identities) != len(set(identities)):
            raise ValueError("Collections define duplicate current snippet identities")
        helpers = {}
        for snippet in snippets:
            if snippet.historical:
                continue
            for name, signature in snippet.helper_signatures.items():
                previous = helpers.setdefault(name, (signature, snippet.identity))
                if previous[0] != signature:
                    raise ValueError(
                        f"Helper name {name!r} conflicts between "
                        f"{previous[1]!r} and {snippet.identity!r}; rename one function"
                    )
        for snippet in snippets if self.project else ():
            collection = snippet.identity.split("/")[0]
            pinned = self.project.pins.get(collection)
            if pinned and not snippet.historical and pinned != snippet.version:
                raise ValueError(
                    f"Collection {collection!r} requires version {pinned}, installed {snippet.version}"
                )

    def set_snippets(self, snippets):
        """Refresh recognition without committing, formatting or rewriting source."""
        self.validate_snippets(snippets)
        self.snippets = snippets
        self._helpers = {
            node.name: node
            for snippet in snippets
            if not snippet.historical
            for node in snippet.helpers
        }
        self._helper_imports = {
            name: tuple(text for _, text in signature[1])
            for snippet in snippets
            if not snippet.historical
            for name, signature in snippet.helper_signatures.items()
        }
        self.document.prepare = None if self.document.fragment else self._prepare_source
        self._reset_cache()

    def _prepare_source(self, source, scratch):
        if not self._helpers and HELPERS_START not in source:
            return source
        source, functions = manage_helpers(source, self._helpers, retain=scratch)
        required = tuple(
            text
            for function in functions
            if function is self._helpers.get(function.name)
            for text in self._helper_imports[function.name]
        )
        return manage_imports(source, required, retain=scratch)

    def _reset_cache(self):
        self._reporter_choices = {}
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
        context = getattr(self, "context", None)
        if self.document.fragment:
            # Scratch may use live program values; insertion checks ordering later.
            self._analysis.ambient_names = (
                frozenset(context.analysis.root.initialized)
                if context is not None
                else frozenset()
            )
        return self._analysis

    def _refresh(self):
        if self._revision is not self.document.syntax:
            self._analysis = Analysis(self.document.syntax)
            if self.document.fragment:
                # Scratch deliberately omits imports. Only unambiguous library
                # dependencies supply hints for its otherwise unbound names.
                imports = {}
                for snippet in self.snippets:
                    for node in snippet.imports:
                        for alias in node.names:
                            name = alias.asname or alias.name.split(".")[0]
                            path = (
                                f"{node.module}.{alias.name}"
                                if isinstance(node, ast.ImportFrom)
                                else alias.name if alias.asname else name
                            )
                            imports.setdefault(name, set()).add(path)
                self._analysis.imports.update(
                    {
                        (id(None), name): next(iter(paths))
                        for name, paths in imports.items()
                        if len(paths) == 1
                    }
                )
            for snippet in self.snippets:
                body = snippet.body
                if (
                    snippet.expression
                    and snippet.result_type
                    and isinstance(body, ast.Call)
                    and isinstance(body.func, ast.Attribute)
                ):
                    root, path = attribute_path(body.func)
                    receiver = getattr(root, "template_parameter", None)
                    parameter = next(
                        (p for p in snippet.parameters if p.name == receiver), None
                    )
                    if parameter and parameter.annotation:
                        for kind in annotation_types(parameter.annotation):
                            self._analysis.method_types[kind, path] = (
                                snippet.result_type
                            )
            recognized = recognize(
                self.document.syntax, self.snippets, self._analysis, nested=True
            )
            self._matches = outer_matches(recognized)
            self.input_contracts = {
                self.document.syntax.spans[node]: parameter.annotation
                for match in recognized
                if match.snippet.expression
                for parameter in match.snippet.parameters
                if parameter.annotation and parameter.name not in match.snippet.names
                for node in match.occurrences.get(parameter.name, ())
            }
            self._analysis.apply_contracts(self._matches)
            self._match_starts = [match.span.start for match in self._matches]
            self._revision = self.document.syntax
            self._expanded.clear()
            self._user_snippets = function_snippets(self.document.syntax)

    @property
    def available_snippets(self):
        self._refresh()
        context = getattr(self, "context", None)
        local = self._user_snippets
        if context:
            context._refresh()
            names = {s.identity for s in local}
            local += tuple(s for s in context._user_snippets if s.identity not in names)
        return self.snippets + local

    @property
    def visible_matches(self) -> tuple[Match, ...]:
        self._refresh()
        return (
            tuple(match for match in self._matches if match.span not in self._expanded)
            if self._expanded
            else self._matches
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

    def enclosing_match(self, node):
        self._refresh()
        span = self.document.syntax.spans[node]
        index = bisect_right(self._match_starts, span.start) - 1
        if index >= 0:
            match = self._matches[index]
            if span.end <= match.span.end and match.span not in self._expanded:
                return match
        return None

    def field_binding(self, node):
        """The declared expression containing a node, if it belongs to a block."""
        match = self.enclosing_match(node)
        if match:
            spans = self.document.syntax.spans
            span = spans[node]
            for parameter in match.snippet.parameters:
                if parameter.name in match.snippet.names:
                    continue
                for root in match.occurrences.get(parameter.name, ()):
                    if spans[root].start <= span.start and span.end <= spans[root].end:
                        return match, parameter, root
        return None

    def editable(self, node, part="expression"):
        """Structural edits follow declared fields; explicit Python editing is free."""
        match = self.enclosing_match(node)
        if match is None:
            return True
        if (
            part == "expression"
            and match.snippet.expression
            and self.document.syntax.spans[node] == match.span
        ):
            return True
        if part == "name":
            return match.snippet.mode == "legacy" or any(
                node in nodes for nodes in match.named.values()
            )
        if self.field_binding(node) is not None:
            return True
        if (
            part == "operator"
            and isinstance(node, ast.AugAssign)
            and not match.snippet.expression
            and len(match.snippet.body) == 1
            and isinstance(match.snippet.body[0], ast.AugAssign)
        ):
            template = match.snippet.body[0]
            return bool(
                getattr(template.value, "template_parameter", None)
                and self.editable(node.target, "name")
            )
        # A generic assignment publishes both its target and its value. Explicit
        # structural tools may turn its name into an attribute or unpacking target;
        # ordinary name editing still performs a lexical rename.
        if (
            part == "expression"
            and isinstance(getattr(node, "ctx", None), ast.Store)
            and self.editable(node, "name")
            and not match.snippet.expression
            and len(match.snippet.body) == 1
            and isinstance(match.snippet.body[0], ast.Assign)
            and getattr(match.snippet.body[0].value, "template_parameter", None)
        ):
            return True
        if part == "sequence":
            if isinstance(node, ast.Call):
                parent = self.document.syntax.parent.get(node)
                return (
                    self.field_binding(node.func) is not None
                    or match.snippet.expression
                    and self.document.syntax.spans[node] == match.span
                    or isinstance(parent, (ast.Expr, ast.Assign, ast.AnnAssign))
                    and parent.value is node
                    and self.document.syntax.spans[parent] == match.span
                )
            if isinstance(node, ast.BoolOp):
                return all(
                    self.field_binding(value) is not None for value in node.values
                )
            if isinstance(node, ast.Compare):
                return all(
                    self.field_binding(value) is not None
                    for value in (node.left, *node.comparators)
                )
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return self.editable(node, "name") and all(
                    self.editable(arg, "name")
                    for arg in (
                        *node.args.posonlyargs,
                        *node.args.args,
                        *node.args.kwonlyargs,
                    )
                )
        return False

    def _field_source(self, node, source):
        if binding := self.field_binding(node):
            match, parameter, root = binding
            span = self.document.syntax.spans[root]
            length = len(source) - len(self.document.state.source)
            replacement = source[span.start : span.end + length]
            source = edit.replace_expressions(
                self.document.syntax,
                [
                    (self.document.syntax.spans[item], replacement)
                    for item in match.occurrences[parameter.name]
                ],
            )
        return source

    def _commit_field(self, node, source, *, focus):
        self.editor.commit(self._field_source(node, source), focus=focus)

    def replace_expression(self, node, text):
        if not self.editable(node):
            raise ValueError("Expand the block to edit its fixed implementation")
        self._commit_field(
            node,
            edit.replace(self.document.syntax, node, text),
            focus=self.document.syntax.spans[node].start,
        )

    def change_sequence(self, sequence, index, action, text=None):
        from .structure import sequence as list_sequence

        if sequence.syntax is not self.document.syntax:
            raise ValueError("Document changed; choose the list again")
        if not self.editable(sequence.node, "sequence"):
            raise ValueError("Expand the block to edit its fixed implementation")
        route = self.document.syntax.path(sequence.node)
        self._commit_field(
            sequence.node,
            sequence.change(index, action, text),
            focus=sequence.span.start,
        )
        syntax = self.document.syntax
        node = syntax.follow(route)
        self.editor.selection = node
        updated = list_sequence(syntax, node)
        if updated and updated.items:
            index = max(
                0,
                min(
                    index + {"left": -1, "right": 1}.get(action, 0),
                    len(updated.items) - 1,
                ),
            )
            span = updated.items[index]
            candidates = [
                n
                for n, s in syntax.spans.items()
                if isinstance(n, ast.expr) and span.start <= s.start < span.end
            ]
            if candidates:
                self.editor.selection = min(
                    candidates,
                    key=lambda n: (
                        not (isinstance(n, ast.Constant) and n.value is Ellipsis),
                        syntax.spans[n].start,
                        -syntax.spans[n].end,
                    ),
                )

    def accepts_target(self, target):
        if isinstance(target, ast.expr):
            return self.editable(target)
        suite, index = target.suite, target.index
        if self.enclosing_match(suite.owner):
            return len(suite.statements) == 1 and isinstance(
                suite.statements[0], ast.Pass
            )
        if 0 < index < len(suite.statements):
            before = self.enclosing_match(suite.statements[index - 1])
            after = self.enclosing_match(suite.statements[index])
            if before is not None and before is after:
                return False
        return True

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
            loop = next(
                (
                    n
                    for n in self.document.syntax.ancestors(self.editor.selection)
                    if isinstance(n, ast.For)
                    and isinstance(n.iter, ast.Call)
                    and isinstance(n.iter.func, ast.Name)
                    and n.iter.func.id == "range"
                ),
                None,
            )
            if loop is None:
                raise ValueError("Select a recognized snippet to expand or collapse")
            span = self.document.syntax.spans[loop]
        else:
            span = match.span
        if span in self._expanded:
            self._expanded.remove(span)
        else:
            self._expanded.add(span)

    def simplified_range(self, call):
        self._refresh()
        parent = self.document.syntax.parent.get(call)
        return (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "range"
            and len(call.args) in {1, 3}
            and not call.keywords
            and isinstance(parent, ast.For)
            and parent.iter is call
            and self.analysis.resolve(call.func, "range") is None
            and self.document.syntax.spans[parent] not in self._expanded
        )

    @property
    def expanded_spans(self):
        self._refresh()
        return frozenset(self._expanded)

    def selected_nodes(self):
        if isinstance(self.editor.selection, ast.expr) and self.field_binding(
            self.editor.selection
        ):
            return self.editor.selection
        match = self.selected_match()
        if not match:
            return self.editor.selection
        if not match.snippet.expression:
            return self._match_nodes(match)
        syntax = self.document.syntax
        return next(
            node
            for node in syntax.ancestors(syntax.at(match.span.start))
            if isinstance(node, ast.expr) and syntax.spans[node] == match.span
        )

    def selected_text(self) -> str:
        return edit.block_text(self.document.syntax, self.selected_nodes())

    def destination(self) -> edit.Target:
        """Default insertion is after the containing statement, or end of module."""
        syntax = self.document.syntax
        if self.editor.selection is syntax.tree:
            suite = syntax.suites[0]
            return edit.Target(suite, len(suite.statements))
        node = self.editor.statement()
        if isinstance(node, ast.Pass):
            return edit.Target(syntax.statement_suite[node], 0)
        match = self.selected_match()
        if match and not match.snippet.expression:
            node = self._match_nodes(match)[-1]
        suite = syntax.statement_suite[node]
        return edit.Target(suite, suite.statements.index(node) + 1)

    def expand_snippet(self, snippet, bindings):
        """Public declarations may satisfy missing names; helpers must not capture them."""
        occupied = identifiers(self.document.syntax.tree)
        declared = set(self.analysis.value_names)
        if context := getattr(self, "context", None):
            occupied.update(identifiers(context.document.syntax.tree))
            declared.update(context.analysis.value_names)
        return instantiate(snippet, bindings, occupied, declared=declared)

    def insert_snippet(
        self,
        snippet: Snippet,
        bindings: dict[str, str],
        target: edit.Target | None = None,
    ) -> None:
        syntax = self.document.syntax
        expansion = self.expand_snippet(snippet, bindings)
        if (
            snippet.expression
            and target is None
            and not (
                isinstance(snippet.body, ast.Call)
                and not isinstance(self.editor.selection, ast.expr)
            )
        ):
            if not isinstance(self.editor.selection, ast.expr):
                raise ValueError("Select an expression to replace with this snippet")
            if not self.accepts_target(self.editor.selection):
                raise ValueError("Expand the block to edit its fixed implementation")
            offset = syntax.spans[self.editor.selection].start
            source = edit.replace(syntax, self.editor.selection, expansion.source)
            source = self._field_source(self.editor.selection, source)
        else:
            target = target or self.destination()
            if not self.accepts_target(target):
                raise ValueError("Expand the block to edit its fixed implementation")
            offset = self.insertion_offset(target)
            source = edit.insert(syntax, target, expansion.source)
        self.commit_insertion(
            source, offset, expansion.imports, helpers=expansion.helpers
        )

    def insertion_offset(self, target):
        syntax = self.document.syntax
        statements = target.suite.statements
        if len(statements) == 1 and isinstance(statements[0], ast.Pass):
            return syntax.block_span(statements[0]).start
        return edit.target_position(syntax, target)[0]

    def prepare_insertion(
        self, source, offset, required=(), scratch=None, *, helpers=()
    ):
        """Prepare helper and import edits without changing document state."""
        prepared = source
        if helpers and not self.document.fragment:
            definitions = {
                node.name: node for text in helpers for node in ast.parse(text).body
            }
            syntax = Syntax(source)
            scopes = Scopes(syntax.tree)
            start = offset
            while start < len(source) and source[start] in " \t":
                start += 1
            inserted = next(
                n
                for n in syntax.ancestors(syntax.at(start))
                if isinstance(n, (ast.Call, ast.stmt, ast.Module))
            )
            for node in ast.walk(inserted):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in definitions
                ):
                    owner = scopes.resolve(node.func, node.func.id)
                    if owner is not None and owner is not scopes.root:
                        raise ValueError(
                            f"Helper name {node.func.id!r} conflicts with a local binding"
                        )
            prepared, _ = manage_helpers(
                source,
                definitions,
                retain=self.document.state.scratch if scratch is None else scratch,
                required=definitions,
            )
        return self.with_imports(prepared, required)

    def commit_insertion(
        self, source, offset, required=(), scratch=None, *, helpers=(), scratch_ids=None
    ):
        imported = self.prepare_insertion(
            source, offset, required, scratch, helpers=helpers
        )
        self.editor.commit(
            imported,
            scratch,
            focus=edit.map_offset(source, imported, offset),
            scratch_ids=scratch_ids,
        )

    def change_variant(self, snippet, bindings):
        from .variants import variant_source

        match = self.selected_match()
        if match is None:
            raise ValueError("Select a recognized block")
        source = variant_source(self, match, snippet, bindings)
        self.editor.commit(
            source,
            focus=edit.map_offset(self.document.state.source, source, match.span.start),
        )

    def _replace_match(self, match: Match, source: str, *, changes=()) -> str:
        syntax = self.document.syntax
        if match.snippet.expression:
            return edit.replace_expressions(syntax, [(match.span, source), *changes])
        nodes = self._match_nodes(match)
        suite, span, _ = edit.statement_group(syntax, nodes)
        indent = syntax.position(match.span.start)[1]
        if (
            not source.strip()
            and len(nodes) == len(suite.statements)
            and not isinstance(suite.owner, ast.Module)
        ):
            source = "pass"
        return edit.patches(
            syntax.source, [(span, edit.reindent(source, indent)), *changes]
        )

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

    def upgraded_source(self) -> str:
        match = self.selected_match()
        if match is None or not match.snippet.historical:
            raise ValueError("Select a snippet recognized from a historical template")
        current = next(
            (
                s
                for s in self.snippets
                if s.identity == match.snippet.identity and not s.historical
            ),
            None,
        )
        if current is None:
            raise ValueError("This block has no current definition to upgrade to")
        expansion = upgrade(match, current, identifiers(self.document.syntax.tree))
        comments = [
            token.string
            for token in tokenize.generate_tokens(
                io.StringIO(self.selected_text()).readline
            )
            if token.type == tokenize.COMMENT
        ]
        replacement = "\n".join([*comments, expansion.source])
        if match.snippet.mode == "function":
            # A named definition is shared by every call, including Scratch.
            source = self.document.state.source
        else:
            source = self._replace_match(match, replacement)
        syntax = Syntax(source)
        section = helper_section(source)
        if section:
            definitions = {n.name: n for n in current.helpers}
            source = edit.patches(
                source,
                [
                    (
                        syntax.spans[n],
                        getattr(definitions[n.name], "source_text", None)
                        or ast.unparse(definitions[n.name]),
                    )
                    for n in syntax.tree.body
                    if isinstance(n, ast.FunctionDef)
                    and n.name in definitions
                    and section.contains(syntax.spans[n].start)
                ],
            )
        return self.document.candidate(
            self.with_imports(source, expansion.imports)
        ).source

    def upgrade_selected(self) -> None:
        self.editor.commit(self.upgraded_source())

    def extract_selection(self):
        """Return detached text and the valid remainder, without changing state."""
        nodes = self.selected_nodes()
        source = edit.delete(self.document.syntax, nodes)
        if isinstance(nodes, ast.expr) and not isinstance(
            self.document.syntax.parent.get(nodes), ast.Expr
        ):
            source = self._field_source(nodes, source)
        return edit.reindent(self.selected_text(), 0), source

    def to_scratch(self, position=None) -> None:
        text, source = self.extract_selection()
        scratch = list(self.document.state.scratch)
        identities = list(self.document.state.scratch_ids)
        position = len(scratch) if position is None else position
        scratch.insert(position, text)
        identities.insert(position, object())
        self.editor.commit(source, tuple(scratch), scratch_ids=identities)

    def set_scratch(self, index: int | None, text: str, *, group=None) -> None:
        scratch = list(self.document.state.scratch)
        identities = list(self.document.state.scratch_ids)
        if index is None:
            scratch.append(text)
            identities.append(object())
        else:
            if not 0 <= index < len(scratch):
                raise ValueError("Scratch index outside workspace")
            scratch[index] = text
        self.editor.commit(
            self.document.state.source,
            tuple(scratch),
            scratch_ids=identities,
            group=group,
        )

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
            if not self.accepts_target(node):
                raise ValueError("Expand the block to edit its fixed implementation")
            offset = syntax.spans[node].start
            source = edit.replace(syntax, node, text)
            source = self._field_source(node, source)
        else:
            target = target or self.destination()
            if not self.accepts_target(target):
                raise ValueError("Expand the block to edit its fixed implementation")
            offset = self.insertion_offset(target)
            source = edit.insert(syntax, target, text)
        remaining = (
            scratch[:index]
            + ((remainder,) if remainder.strip() else ())
            + scratch[index + 1 :]
        )
        identities = self.document.state.scratch_ids
        self.commit_insertion(
            source,
            offset,
            self.fragment_imports(text),
            remaining,
            scratch_ids=identities[:index]
            + ((identities[index],) if remainder.strip() else ())
            + identities[index + 1 :],
        )
