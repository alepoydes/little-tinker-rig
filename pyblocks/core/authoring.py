"""Editable template sources; drafts never replace the working collection.

Validation and preview use the same static loader as insertion. Template code is
never imported or evaluated. Saving changes definitions, never program text.
"""

import ast
import json
import re
import tomllib
from pathlib import Path

from .edit import reindent
from .project import atomic_write
from .snippets import instantiate, load_collection, load_module

BUILTINS = Path(__file__).resolve().parents[1] / "snippets"
STARTERS = {
    "action": 'def my_action(value=1):\n    """Show a value."""\n    print(value)\n',
    "expression": 'def my_expression(value=1) -> "number":\n    """Double a value."""\n    return value * 2\n',
    "sequence": 'def my_sequence(motor: "Motor" = motor, speed: "deg/s" = 300, duration: "ms" = 500):\n    """Run a motor for a time, then brake."""\n    from pybricks.tools import wait\n\n    motor.run(speed)\n    wait(duration)\n    motor.brake()\n',
}


def collection_root(path: Path) -> Path:
    return next(
        parent
        for parent in path.resolve().parents
        if (parent / "collection.toml").is_file()
    )


def user_collection(parent: Path) -> Path:
    root = parent / "blocks"
    manifest = root / "collection.toml"
    if not manifest.exists():
        if root.exists() and any(root.iterdir()):
            raise ValueError(f"{root} is not a block collection")
        root.mkdir(parents=True, exist_ok=True)
        atomic_write(manifest, '[collection]\nid = "my_blocks"\nversion = "1.0.0"\n')
    return root.resolve()


def module_levels(manifest, module):
    return {
        key: value
        for key, value in manifest.get("levels", {}).items()
        if key.rsplit("/", 1)[0] == module
    }


def update_levels(source, module, levels):
    """Replace one module's assignments, preserving unrelated TOML sections."""
    parsed = tomllib.loads(source)
    values = parsed.get("levels", {}).copy()
    values = {
        key: value for key, value in values.items() if key.rsplit("/", 1)[0] != module
    }
    values.update(levels)
    table = "[levels]\n" + "".join(
        f"{json.dumps(key, ensure_ascii=False)} = {json.dumps(value)}\n"
        for key, value in sorted(values.items())
    )
    match = re.search(r"(?m)^\[levels\][ \t]*(?:#[^\n]*)?$", source)
    if match:
        end = re.search(r"(?m)^\s*\[", source[match.end() :])
        finish = match.end() + end.start() if end else len(source)
        return source[: match.start()] + table + "\n" + source[finish:]
    if parsed.get("levels"):
        raise ValueError("Use a [levels] table in collection.toml to edit levels here")
    return source.rstrip() + "\n\n" + table


def template_from_source(source: str, imports=(), *, expression=False) -> str:
    """Capture a fragment as a draft. Parameter choices remain explicit in Python."""
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
    return 'def my_block():\n    """Describe this block."""\n' + reindent(body, 4)


class DefinitionDraft:
    """One module, including unsaved levels and recoverable invalid Python."""

    def __init__(self, path: Path):
        self.path = path.resolve()
        self.root = collection_root(self.path)
        self.relative = self.path.relative_to(self.root).as_posix()
        self.module = self.path.relative_to(self.root).with_suffix("").as_posix()
        self.read_only = self.path.is_relative_to(BUILTINS)
        self.saved_source = (
            self.path.read_text(encoding="utf-8") if self.path.exists() else None
        )
        manifest = tomllib.loads(
            (self.root / "collection.toml").read_text(encoding="utf-8")
        )
        self.identity = manifest["collection"]["id"] + "/" + self.module
        self.version = manifest["collection"]["version"]
        self.saved_levels = module_levels(manifest, self.module)
        self.source = self.saved_source or ""
        self.preview_source = self.source
        self.levels = self.saved_levels.copy()
        if not self.read_only and self.draft_path.exists():
            draft = json.loads(self.draft_path.read_text(encoding="utf-8"))
            self.source, self.levels = draft["source"], draft["levels"]
            self.saved_source, self.saved_levels = (
                draft["base_source"],
                draft["base_levels"],
            )
            self.preview_source = draft.get("preview_source", self.saved_source or "")

    @property
    def draft_path(self):
        return self.root / ".drafts" / (self.relative + ".json")

    @property
    def dirty(self):
        return self.source != self.saved_source or self.levels != self.saved_levels

    def persist(self):
        if self.read_only:
            return
        if not self.dirty:
            self.draft_path.unlink(missing_ok=True)
            return
        self.draft_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(
            self.draft_path,
            json.dumps(
                {
                    "source": self.source,
                    "levels": self.levels,
                    "base_source": self.saved_source,
                    "base_levels": self.saved_levels,
                    "preview_source": self.preview_source,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )

    def inspect(self):
        """Return AST and templates, with loader failures located in the source."""
        tree = ast.parse(self.source, filename=str(self.path))
        # compile checks duplicate arguments and invalid control context but does
        # not resolve or evaluate template defaults such as motor=motor.
        compile(tree, str(self.path), "exec")
        snippets = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                try:
                    module = ast.Module(body=[node], type_ignores=[])
                    loaded = load_module(
                        ast.unparse(module), self.identity, self.version
                    )
                    for snippet in loaded:
                        instantiate(
                            snippet,
                            {
                                p.name: p.name
                                for p in snippet.parameters
                                if p.default is None
                            },
                        )
                    snippets.extend(loaded)
                except (ValueError, SyntaxError) as error:
                    raise SyntaxError(
                        str(error),
                        (
                            str(self.path),
                            node.lineno,
                            node.col_offset + 1,
                            self.source.splitlines()[node.lineno - 1],
                        ),
                    ) from error
            elif not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                raise SyntaxError(
                    "Place dependencies and code inside template functions",
                    (
                        str(self.path),
                        node.lineno,
                        node.col_offset + 1,
                        self.source.splitlines()[node.lineno - 1],
                    ),
                )
        identities = [s.identity for s in snippets]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate block name in this module")
        self.preview_source = self.source
        return tree, tuple(snippets)

    def candidate(self):
        tree, _ = self.inspect()
        names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        levels = {
            f"{self.module}/{name}": self.levels.get(
                f"{self.module}/{name}", "intermediate"
            )
            for name in names
        }
        manifest = (self.root / "collection.toml").read_text(encoding="utf-8")
        updated = update_levels(manifest, self.module, levels)
        snippets = load_collection(
            self.root,
            overrides={self.relative: self.source, "collection.toml": updated},
        )
        return updated, snippets, levels

    def save(self, validate=None):
        if self.read_only:
            raise ValueError("Built-in definitions are read-only; copy the block first")
        current = self.path.read_text(encoding="utf-8") if self.path.exists() else None
        manifest_path = self.root / "collection.toml"
        manifest = manifest_path.read_text(encoding="utf-8")
        if (
            current != self.saved_source
            or module_levels(tomllib.loads(manifest), self.module) != self.saved_levels
        ):
            raise ValueError(
                "Definition changed outside this editor; reopen it before saving"
            )
        updated, snippets, levels = self.candidate()
        if validate:
            validate(self.root, snippets)
        self.persist()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(self.path, self.source)
        try:
            atomic_write(manifest_path, updated)
        except OSError:
            if current is None:
                self.path.unlink()
            else:
                atomic_write(self.path, current)
            raise
        self.saved_source = self.source
        self.levels = levels
        self.saved_levels = levels.copy()
        self.draft_path.unlink(missing_ok=True)
        return snippets
