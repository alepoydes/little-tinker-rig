"""Literal decorator metadata shared by loading, migration and authoring."""

import ast
import keyword
import re

from little_tinker_rig.i18n import N_

from .presentation import PALETTE
from .syntax import Span, Syntax

LEVELS = ("beginner", "intermediate", "advanced", "expert")
DECORATORS = {"inline_block", "block"}
CATEGORIES = {
    "program": N_("Program"),
    "values": N_("Values and calculations"),
    "data": N_("Variables and collections"),
    "functions": N_("Functions"),
    "movement": N_("Motors and movement"),
    "input": N_("Sensors and input"),
    "output": N_("Light and sound"),
    "devices": N_("Devices and communication"),
}
FIELDS = {
    "level",
    "icon",
    "color",
    "names",
    "kind",
    "context",
    "category",
    "family",
    "variant",
    "advanced",
    "bindings",
    "title",
    "group",
    "readout",
}


def module_category(tree):
    """Read the optional static category shared by a module's block definitions."""
    declarations = [node for node in tree.body if category_declaration(node)]
    if len(declarations) > 1:
        raise ValueError("A block module has one __category__ declaration")
    if not declarations:
        return ""
    node = declarations[0]
    if not isinstance(node.value, ast.Constant) or node.value.value not in CATEGORIES:
        raise ValueError("Unknown block module category")
    return node.value.value


def category_declaration(node):
    return (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "__category__"
    )


def decorator(function):
    for item in function.decorator_list:
        target = item.func if isinstance(item, ast.Call) else item
        if isinstance(target, ast.Name) and target.id in DECORATORS:
            return item
    return None


def metadata(function):
    item = decorator(function)
    if item is None:
        return None
    if len(function.decorator_list) != 1:
        raise ValueError(f"{function.name}: a block has exactly one static decorator")
    values = {}
    mode = item.func.id if isinstance(item, ast.Call) else item.id
    if isinstance(item, ast.Call):
        if item.args:
            raise ValueError(f"{function.name}: block metadata uses keyword arguments")
        for entry in item.keywords:
            if entry.arg not in FIELDS or entry.arg in values:
                raise ValueError(
                    f"{function.name}: unknown or repeated block property {entry.arg!r}"
                )
            try:
                values[entry.arg] = ast.literal_eval(entry.value)
            except (ValueError, TypeError) as error:
                raise ValueError(
                    f"{function.name}: block properties must be literals"
                ) from error
    level = values.get("level", "intermediate")
    icon, color = values.get("icon", "▶"), values.get("color", "snippet")
    names = values.get("names", ())
    if level not in LEVELS:
        raise ValueError(f"{function.name}: unknown block level {level!r}")
    if not isinstance(icon, str) or not icon.strip() or icon.splitlines() != [icon]:
        raise ValueError(f"{function.name}: icon must be nonempty single-line text")
    if not isinstance(color, str) or not (
        color in PALETTE or re.fullmatch(r"#[0-9a-fA-F]{6}", color)
    ):
        raise ValueError(f"{function.name}: color must name a palette role or #RRGGBB")
    if (
        not isinstance(names, (tuple, list))
        or any(
            not isinstance(name, str)
            or not all(
                p.isidentifier() and not keyword.iskeyword(p) for p in name.split(".")
            )
            for name in names
        )
        or len(names) != len(set(names))
    ):
        raise ValueError(
            f"{function.name}: names must list unique lexical declarations"
        )
    if mode == "block" and names:
        raise ValueError(f"{function.name}: function block locals are private")
    if values.get("kind") not in (None, "statement", "expression"):
        raise ValueError(f"{function.name}: kind must be statement or expression")
    if values.get("context") not in (None, "loop", "async"):
        raise ValueError(f"{function.name}: unsupported template context")
    if mode == "block" and values.get("context"):
        raise ValueError(
            f"{function.name}: a function block cannot require its caller's context"
        )
    if values.get("category", "") not in ("", *CATEGORIES):
        raise ValueError(f"{function.name}: unknown catalog category")
    if type(values.get("readout", False)) is not bool:
        raise ValueError(f"{function.name}: readout must be a boolean")
    title, group = values.get("title", ""), values.get("group", ())
    if not isinstance(title, str) or (
        title and (not title.strip() or len(title.splitlines()) != 1)
    ):
        raise ValueError(f"{function.name}: title must be single-line text")
    if (
        not isinstance(group, (tuple, list))
        or len(group) > 2
        or any(
            not isinstance(part, str)
            or not part.strip()
            or len(part.splitlines()) != 1
            or "/" in part
            for part in group
        )
    ):
        raise ValueError(
            f"{function.name}: group needs up to two nonempty path segments"
        )
    family = values.get("family", "")
    if not isinstance(family, str) or (
        family and not re.fullmatch(r"[\w.-]+(?:/[\w.-]+)+", family)
    ):
        raise ValueError(f"{function.name}: family needs a complete block identity")
    variant = values.get("variant")
    if variant is not None and (
        not isinstance(variant, str)
        or not variant.strip()
        or len(variant.splitlines()) != 1
    ):
        raise ValueError(f"{function.name}: variant needs a short label")
    arguments = [
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
    ]
    parameters = {arg.arg for arg in arguments}
    advanced = values.get("advanced", ())
    optional = {
        arg.arg
        for arg, default in zip(
            arguments,
            [None]
            * (
                len(arguments)
                - len(function.args.kwonlyargs)
                - len(function.args.defaults)
            )
            + function.args.defaults
            + function.args.kw_defaults,
            strict=True,
        )
        if default is not None
    }
    if (
        not isinstance(advanced, (tuple, list))
        or not all(isinstance(name, str) and name in optional for name in advanced)
        or len(set(advanced)) != len(advanced)
    ):
        raise ValueError(
            f"{function.name}: advanced fields need distinct optional parameters"
        )
    bindings = values.get("bindings", {})
    if not isinstance(bindings, dict) or any(
        name not in parameters
        or not isinstance(key, str)
        or not key.isidentifier()
        or keyword.iskeyword(key)
        for name, key in bindings.items()
    ):
        raise ValueError(f"{function.name}: invalid family parameter bindings")
    if len({bindings.get(name, name) for name in parameters}) != len(parameters):
        raise ValueError(f"{function.name}: family parameter bindings must be unique")
    return dict(
        values,
        mode="inline" if mode == "inline_block" else "function",
        level=level,
        icon=icon,
        color=color,
        names=tuple(names),
        advanced=tuple(advanced),
        group=tuple(group),
    )


def change_property(source, function_name, name, value):
    """Edit the decorator's literal text, preserving the surrounding Python."""
    from .edit import patches

    syntax = Syntax(source, fragment=True)
    function = next(
        (
            node
            for node in syntax.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        ),
        None,
    )
    if function is None:
        raise ValueError(f"Unknown block {function_name!r}")
    item = decorator(function)
    expression = repr(value)
    if item is None:
        offset = syntax.offset(function.lineno)
        span, replacement = (
            Span(offset, offset),
            f"@inline_block({name}={expression})\n",
        )
    elif isinstance(item, ast.Name):
        span, replacement = syntax.spans[item], f"{item.id}({name}={expression})"
    elif keyword := next((entry for entry in item.keywords if entry.arg == name), None):
        span, replacement = syntax.spans[keyword.value], expression
    elif item.keywords:
        last = item.keywords[-1]
        offset = syntax.spans[last.value].end
        separator = (
            ",\n" + " " * last.col_offset if item.end_lineno > item.lineno else ", "
        )
        span, replacement = Span(offset, offset), f"{separator}{name}={expression}"
    else:
        offset = syntax.spans[item].end - 1
        span, replacement = Span(offset, offset), f"{name}={expression}"
    result = patches(source, [(span, replacement)])
    updated = next(
        node
        for node in ast.parse(result).body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    metadata(updated)
    return result
