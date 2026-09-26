"""Literal decorator metadata shared by loading, migration and authoring."""

import ast
import keyword
import re

from .presentation import PALETTE
from .syntax import Span, Syntax

LEVELS = ("beginner", "intermediate", "advanced", "expert")
DECORATORS = {"inline_block", "block"}
FIELDS = {"level", "icon", "color", "names", "kind", "context"}


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
    return dict(
        values,
        mode="inline" if mode == "inline_block" else "function",
        level=level,
        icon=icon,
        color=color,
        names=tuple(names),
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
