"""Explicit source-preserving migration of legacy inline template modules."""

import ast
import json
import re
import tomllib

from .analysis import annotation_text
from .block_metadata import decorator
from .edit import patches
from .presentation import block_icon, snippet_role
from .snippets import load_module
from .syntax import Span, Syntax
from .types import canonical


def module_levels(manifest, module):
    return {
        key.rsplit("/", 1)[1]: value
        for key, value in manifest.get("levels", {}).items()
        if key.rsplit("/", 1)[0] == module
    }


def remove_levels(source, module=None):
    """Remove migrated assignments, retaining unrelated manifest information."""
    values = tomllib.loads(source).get("levels", {})
    remaining = {
        key: value
        for key, value in values.items()
        if module is not None and key.rsplit("/", 1)[0] != module
    }
    if remaining == values:
        return source
    match = re.search(r"(?m)^[ \t]*\[levels\][ \t]*(?:#[^\n]*)?$", source)
    if match is None:
        raise ValueError("Migrate a collection.toml with an explicit [levels] table")
    end = re.search(r"(?m)^[ \t]*\[", source[match.end() :])
    finish = match.end() + end.start() if end else len(source)
    comments = [
        line[line.index("#") :]
        for line in source[match.start() : finish].splitlines()
        if "#" in line
    ]
    table = (
        (
            "[levels]\n"
            + "".join(
                f"{json.dumps(key)} = {json.dumps(value)}\n"
                for key, value in remaining.items()
            )
        )
        if remaining
        else ""
    )
    return (
        source[: match.start()]
        + "\n".join(comments)
        + ("\n" if comments else "")
        + table
        + source[finish:]
    )


def migrate_collection(directory):
    """Return validated replacement files; the caller chooses when to save them."""
    from .snippets import load_collection

    directory = directory.resolve()
    source = (directory / "collection.toml").read_text(encoding="utf-8")
    manifest = tomllib.loads(source)
    if manifest["collection"].get("format", 1) == 2:
        load_collection(directory)
        return {}
    load_collection(directory)
    roots = [
        (directory / item["path"]).resolve() for item in manifest.get("history", ())
    ]
    identity, version = manifest["collection"]["id"], manifest["collection"]["version"]
    changes = {}
    for path in sorted(directory.rglob("*.py")):
        if not path.resolve().is_relative_to(directory):
            raise ValueError("Collection modules must stay inside the collection")
        if path.name == "__init__.py" or any(
            path.resolve().is_relative_to(root) for root in roots
        ):
            continue
        name = path.relative_to(directory).as_posix()
        module = name.removesuffix(".py")
        changes[name] = migrate_module(
            path.read_text(encoding="utf-8"),
            f"{identity}/{module}",
            version,
            module_levels(manifest, module),
        )
    updated = remove_levels(source)
    table = re.search(r"(?m)^[ \t]*\[collection\][ \t]*(?:#[^\n]*)?$", updated)
    if table is None:
        raise ValueError(
            "Migrate a collection.toml with an explicit [collection] table"
        )
    following = re.search(r"(?m)^[ \t]*\[", updated[table.end() :])
    end = table.end() + following.start() if following else len(updated)
    body = updated[table.end() : end]
    if "format" in manifest["collection"]:
        body, count = re.subn(
            r"""(?m)^([ \t]*(?:format|"format"|'format')[ \t]*=[ \t]*)1(?=[ \t]*(?:#|$))""",
            r"\g<1>2",
            body,
            count=1,
        )
        if not count:
            raise ValueError("Collection format must be a standalone assignment")
    else:
        body = "\nformat = 2" + body
    updated = updated[: table.end()] + body + updated[end:]
    changes["collection.toml"] = updated
    load_collection(directory, overrides=changes)
    return changes


def migrate_module(source, collection, version, levels=None):
    """Add declarative metadata without changing the expanded Python algorithm."""
    levels = levels or {}
    syntax = Syntax(source, fragment=True)
    if any(
        isinstance(node, ast.FunctionDef) and decorator(node)
        for node in syntax.tree.body
    ):
        load_module(source, collection, version, legacy=False)
        return source
    snippets = {
        s.identity.rsplit("/", 1)[1]: s
        for s in load_module(source, collection, version, legacy=True)
    }
    changes = []
    for function in syntax.tree.body:
        if not isinstance(function, ast.FunctionDef) or decorator(function):
            continue
        snippet = snippets[function.name]
        roots = (snippet.body,) if snippet.expression else snippet.body
        names = {
            node.template_parameter
            for root in roots
            for node in ast.walk(root)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and hasattr(node, "template_parameter")
        }
        # A declaration template publishes its function and parameter names.
        # Algorithm temporaries remain private unless the author publishes them.
        for node in roots:
            if isinstance(node, ast.FunctionDef):
                names.add(node.name)
                names.update(
                    f"{node.name}.{arg.arg}"
                    for arg in (
                        *node.args.posonlyargs,
                        *node.args.args,
                        *node.args.kwonlyargs,
                    )
                )
            if (
                isinstance(node, ast.For)
                and len(node.body) == 1
                and isinstance(node.body[0], ast.Pass)
            ):
                names.update(
                    item.id
                    for item in ast.walk(node.target)
                    if isinstance(item, ast.Name) and item.id != "_"
                )
        options = {
            "level": levels.get(function.name, snippet.level),
            "icon": block_icon(snippet),
            "color": snippet_role(snippet),
        }
        if options["level"] == "standard":
            options["level"] = "intermediate"
        if names:
            options["names"] = tuple(sorted(names))
        result = annotation_text(function.returns)
        if result in {"statement", "loop"}:
            options["kind" if result == "statement" else "context"] = result
            annotation = syntax.spans[function.returns]
            arrow = next(
                token
                for token in syntax.tokens_between(
                    syntax.spans[function].start, annotation.start
                )
                if token.string == "->"
            )
            changes.append((Span(syntax.offset(*arrow.start), annotation.end), ""))
        elif function.returns is not None:
            normalized = canonical(result)
            if normalized != result:
                changes.append((syntax.spans[function.returns], repr(normalized)))
        for arg in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        ):
            if arg.annotation is not None:
                annotation = annotation_text(arg.annotation)
                normalized = canonical(annotation)
                if normalized != annotation:
                    changes.append((syntax.spans[arg.annotation], repr(normalized)))
        offset = syntax.offset(function.lineno)
        definition = (
            "@inline_block("
            + ", ".join(f"{key}={value!r}" for key, value in options.items())
            + ")\n"
        )
        changes.append((Span(offset, offset), definition))
    result = patches(source, changes)
    load_module(result, collection, version, legacy=False)
    return result
