"""Source-only definition drafts; validation and preview never execute code."""

import ast
import json
import tomllib
from dataclasses import replace
from pathlib import Path

from .analysis import Analysis, Scopes, annotation_nodes, annotation_text, identifiers
from .block_metadata import change_property, metadata, module_category
from .edit import reindent
from .helpers import function_dependencies
from .imports import import_entries
from .migration import migrate_module, module_levels, remove_levels
from .paths import personal_collection
from .project import atomic_write
from .snippets import instantiate, load_collection, load_module
from .syntax import Syntax
from .types import Compatibility, compatibility, numeric_literal

BUILTINS = Path(__file__).resolve().parents[1] / "snippets"
STARTERS = {
    "action": '@inline_block(level="beginner", icon="▶", color="action")\ndef my_action(value=1):\n    """Show a value."""\n    print(value)\n',
    "expression": '@inline_block(level="intermediate", icon="＝", color="value")\ndef my_expression(value: "number" = 1) -> "number":\n    """Double a value."""\n    return value * 2\n',
    "sequence": '@block(level="intermediate", icon="↻", color="action")\ndef my_sequence(motor: "Motor" = motor, speed: "number[deg/s]" = 300, duration: "int[ms]" = 500):\n    """Run a motor for a time, then brake."""\n    from pybricks.tools import wait\n\n    motor.run(speed)\n    wait(duration)\n    motor.brake()\n',
}


def collection_root(path: Path) -> Path:
    return next(
        parent
        for parent in path.resolve().parents
        if (parent / "collection.toml").is_file()
    )


def user_collection(parent: Path | None = None) -> Path:
    root = parent / "blocks" if parent is not None else personal_collection()
    manifest = root / "collection.toml"
    if not manifest.exists():
        if root.exists() and any(root.iterdir()):
            raise ValueError(f"{root} is not a block collection")
        root.mkdir(parents=True, exist_ok=True)
        atomic_write(
            manifest, '[collection]\nid = "my_blocks"\nversion = "1.0.0"\nformat = 2\n'
        )
    return root.resolve()


def template_from_source(source: str, imports=(), *, expression=False) -> str:
    """Capture ordinary source as an inline draft, preserving literal contents."""
    source = reindent(source, 0)
    tree = ast.parse(source)
    if expression:
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
            raise ValueError("Select one expression for an expression block")
        lines = source.splitlines(keepends=True)
        row = tree.body[0].lineno - 1
        lines[row] = "return " + lines[row]
        source = "".join(lines)
    body = "\n".join((*imports, source))
    return (
        '@inline_block(level="intermediate", icon="▶", color="snippet")\ndef my_block():\n    """Describe this block."""\n'
        + reindent(body, 4)
    )


def selection_imports(source, syntax, offset, *, context=None):
    """Capture only free import dependencies, with nearer bindings taking precedence."""
    selected = Scopes(ast.parse(reindent(source, 0)))
    used = {
        node.id
        for node, _ in selected.references
        if selected.resolve(node, node.id) is None
    }
    for node in annotation_nodes(selected.root.node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                used.update(identifiers(ast.parse(node.value, mode="eval")))
            except SyntaxError:
                pass
    bindings = {}
    contexts = [(context, len(context.source))] if context else []
    for current, boundary in [*contexts, (syntax, offset)]:
        scopes = Scopes(current.tree, current.spans)
        scope = scopes.scopes.get(current.at(boundary), scopes.root)
        visible = []
        while scope:
            visible.append(scope)
            scope = scope.parent
        for scope in reversed(visible):
            for node, owner in sorted(
                scopes.scopes.items(),
                key=lambda item: current.spans.get(
                    item[0], current.spans[current.tree]
                ).start,
            ):
                span = current.spans.get(node)
                if owner is not scope or span is None or span.start >= boundary:
                    continue
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.ImportFrom) and (
                        node.module == "__future__"
                        or any(a.name == "*" for a in node.names)
                    ):
                        continue
                    bindings.update(import_entries([node]))
                    continue
                name = None
                if isinstance(node, ast.Name) and isinstance(
                    node.ctx, (ast.Store, ast.Del)
                ):
                    parent = current.parent.get(node)
                    if isinstance(parent, ast.AnnAssign) and parent.value is None:
                        continue
                    name = node.id
                elif isinstance(node, ast.arg):
                    name = node.arg
                elif isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                        ast.ClassDef,
                        ast.ExceptHandler,
                        ast.MatchAs,
                        ast.MatchStar,
                    ),
                ):
                    name = node.name
                if name:
                    bindings[name] = None
    return tuple(text for name, text in bindings.items() if name in used and text)


def copy_definition(source, name):
    """Copy a block with its authored imports and reachable helper definitions."""
    syntax = Syntax(source, fragment=True)
    functions, dependencies = function_dependencies(syntax.tree)
    included = set()

    def visit(name):
        if name in included:
            return
        included.add(name)
        for dependency in dependencies[name]:
            visit(dependency)

    visit(name)
    result = (
        "\n\n".join(
            syntax.text(node)
            for node in syntax.tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            or isinstance(node, ast.FunctionDef)
            and node.name in included
        )
        + "\n"
    )
    category = module_category(syntax.tree)
    for function in functions.values():
        if function.name not in included or (options := metadata(function)) is None:
            continue
        if options.get("family"):
            result = change_property(result, function.name, "family", "")
        if category and not options.get("category"):
            result = change_property(result, function.name, "category", category)
    return result


class DefinitionDraft:
    """One Python buffer, with a saved baseline for conflict detection and recovery."""

    def __init__(self, path: Path):
        self.path = path.resolve()
        self.root = collection_root(self.path)
        self.relative = self.path.relative_to(self.root).as_posix()
        self.read_only = self.path.is_relative_to(BUILTINS)
        self.saved_source = (
            self.path.read_text(encoding="utf-8") if self.path.exists() else None
        )
        manifest = tomllib.loads(
            (self.root / "collection.toml").read_text(encoding="utf-8")
        )
        self.collection = manifest["collection"]
        history = next(
            (
                item
                for item in manifest.get("history", ())
                if self.path.is_relative_to((self.root / item["path"]).resolve())
            ),
            None,
        )
        self.historical = history is not None
        self.read_only |= self.historical
        module_root = self.root / history["path"] if history else self.root
        self.module = self.path.relative_to(module_root).with_suffix("").as_posix()
        self.identity = self.collection["id"] + "/" + self.module
        self.version = history["version"] if history else self.collection["version"]
        self.saved_levels = module_levels(manifest, self.module)
        self.legacy_levels = self.saved_levels.copy()
        self.source = self.saved_source or ""
        self.preview_source = self.source
        if not self.read_only and self.draft_path.exists():
            draft = json.loads(self.draft_path.read_text(encoding="utf-8"))
            self.source, self.saved_source = draft["source"], draft["base_source"]
            self.collection = draft.get("base_collection", self.collection)
            self.saved_levels = {
                key.rsplit("/", 1)[-1]: value
                for key, value in draft.get("base_levels", self.saved_levels).items()
            }
            self.legacy_levels = {
                key.rsplit("/", 1)[-1]: value
                for key, value in draft.get(
                    "levels", draft.get("legacy_levels", self.legacy_levels)
                ).items()
            }
            self.preview_source = draft.get("preview_source", self.saved_source or "")
        if not self.read_only:
            try:
                self.source = self.migrated_source()
            except (SyntaxError, ValueError):
                pass  # Keep invalid historical drafts verbatim until they are repaired.

    def migrated_source(self):
        if self.collection.get("format", 1) == 2:
            return self.source
        return migrate_module(
            self.source, self.identity, self.version, self.legacy_levels
        )

    @property
    def draft_path(self):
        return self.root / ".drafts" / (self.relative + ".json")

    @property
    def dirty(self):
        return self.source != self.saved_source

    def persist(self):
        if self.read_only:
            return
        if not self.dirty:
            self.draft_path.unlink(missing_ok=True)
            return
        self.draft_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "source": self.source,
            "base_source": self.saved_source,
            "base_collection": self.collection,
            "preview_source": self.preview_source,
        }
        if self.saved_levels or self.legacy_levels:
            state.update(
                base_levels=self.saved_levels, legacy_levels=self.legacy_levels
            )
        atomic_write(
            self.draft_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n"
        )

    def inspect(self):
        """Validate the whole module so shared helper dependencies remain visible."""
        syntax = Syntax(self.source)
        tree = syntax.tree
        functions = {
            node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
        }

        def error_at(message, node):
            row = getattr(node, "lineno", 1)
            return SyntaxError(
                message,
                (
                    str(self.path),
                    row,
                    getattr(node, "col_offset", 0) + 1,
                    self.source.splitlines()[row - 1] if self.source else "",
                ),
            )

        try:
            snippets = load_module(
                self.source,
                self.identity,
                self.version,
                historical=self.historical,
                legacy=(
                    False
                    if self.collection.get("format", 1) == 2 and not self.historical
                    else None
                ),
            )
        except ValueError as error:
            node = functions.get(str(error).split(":", 1)[0], tree)
            if str(error).startswith("Duplicate"):
                raise
            raise error_at(str(error), node) from error
        for snippet in snippets:
            try:
                instantiate(
                    snippet,
                    {p.name: p.name for p in snippet.parameters if p.default is None},
                )
            except (ValueError, SyntaxError) as error:
                raise error_at(
                    str(error), functions[snippet.identity.rsplit("/", 1)[1]]
                ) from error
        analysis = Analysis(syntax)
        for diagnostic in analysis.diagnostics():
            if diagnostic.severity == "error":
                raise error_at(
                    diagnostic.message, analysis.syntax.at(diagnostic.span.start)
                )
        for function in functions.values():
            args = function.args
            positional = args.posonlyargs + args.args
            defaults = [None] * (len(positional) - len(args.defaults)) + args.defaults
            for arg, default in zip(
                positional + args.kwonlyargs, defaults + args.kw_defaults, strict=True
            ):
                if default is None or arg.annotation is None:
                    continue
                # Defaults are caller expressions, not references to this module's
                # template functions (a sensor may be named like its reading block).
                default_syntax = Syntax(ast.unparse(default), fragment=True)
                actual = Analysis(default_syntax).type_info(
                    default_syntax.tree.body[0].value
                )
                try:
                    status = compatibility(
                        annotation_text(arg.annotation),
                        actual,
                        literal=numeric_literal(default),
                    )
                except ValueError:
                    continue
                if status is Compatibility.INCOMPATIBLE:
                    raise error_at(
                        f"Default for {arg.arg!r} does not match {annotation_text(arg.annotation)}",
                        default,
                    )
        snippets = tuple(
            (
                replace(
                    s,
                    level=self.saved_levels.get(s.identity.rsplit("/", 1)[1], s.level),
                )
                if s.mode == "legacy"
                else s
            )
            for s in snippets
        )
        self.preview_source = self.source
        return tree, snippets

    def candidate(self):
        self.inspect()
        manifest = (self.root / "collection.toml").read_text(encoding="utf-8")
        updated = remove_levels(manifest, self.module)
        snippets = load_collection(
            self.root,
            overrides={self.relative: self.source, "collection.toml": updated},
        )
        return updated, snippets

    def save(self, validate=None):
        if self.read_only:
            raise ValueError("This definition is read-only; copy the block first")
        current = self.path.read_text(encoding="utf-8") if self.path.exists() else None
        manifest_path = self.root / "collection.toml"
        manifest = manifest_path.read_text(encoding="utf-8")
        parsed = tomllib.loads(manifest)
        if (
            current != self.saved_source
            or module_levels(parsed, self.module) != self.saved_levels
            or parsed["collection"] != self.collection
        ):
            raise ValueError(
                "Definition changed outside this editor; reopen it before saving"
            )
        self.source = self.migrated_source()
        updated, snippets = self.candidate()
        if validate:
            validate(self.root, snippets)
        self.persist()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(self.path, self.source)
        try:
            if updated != manifest:
                atomic_write(manifest_path, updated)
        except OSError:
            if current is None:
                self.path.unlink()
            else:
                atomic_write(self.path, current)
            raise
        self.saved_source = self.source
        self.saved_levels = self.legacy_levels = {}
        self.draft_path.unlink(missing_ok=True)
        return snippets
