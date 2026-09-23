"""Editable expression slots and suggested bindings, derived entirely from source."""

import ast
from bisect import bisect_right
from dataclasses import dataclass

from . import edit
from .analysis import identifiers, value_type
from .snippets import Match, Parameter, instantiate
from .syntax import Span, Syntax


@dataclass(frozen=True)
class Slot:
    syntax: Syntax
    span: Span
    parameter: Parameter
    match: Match | None = None
    binding: bool = False


def slots(session):
    syntax = session.document.syntax
    result = []
    covered = []
    conditions = [
        syntax.spans[node.test]
        for node in ast.walk(syntax.tree)
        if isinstance(node, (ast.If, ast.While, ast.IfExp))
    ]
    for match in session.visible_matches:
        if match.snippet.expression and any(
            span.start <= match.span.start and match.span.end <= span.end
            for span in conditions
        ):
            continue
        body = match.snippet.body
        assignment = (
            not match.snippet.expression
            and len(body) == 1
            and isinstance(body[0], ast.Assign)
            and getattr(body[0].value, "template_parameter", None)
        )
        for parameter in match.snippet.parameters:
            if assignment == parameter.name and isinstance(
                match.bindings[parameter.name], ast.Call
            ):
                continue
            for node in match.occurrences.get(parameter.name, ()):
                result.append(
                    Slot(
                        syntax,
                        syntax.spans[node],
                        parameter,
                        match,
                        isinstance(getattr(node, "ctx", None), ast.Store),
                    )
                )
        if assignment and isinstance(match.bindings[assignment], ast.Call):
            covered.extend(slot.span for slot in result if slot.match is match)
        else:
            covered.append(match.span)

    covered.sort()
    covered_starts = [span.start for span in covered]
    blocked = set()

    def add(node, name, annotation=None):
        if node not in syntax.spans or node in blocked:
            return
        span = syntax.spans[node]
        index = bisect_right(covered_starts, span.start) - 1
        if index >= 0 and span.end <= covered[index].end:
            return
        if syntax.position(span.start)[0] != syntax.position(span.end)[0]:
            return
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "Port"
        ):
            name, annotation = "port", "Port"
        result.append(
            Slot(
                syntax,
                span,
                Parameter(name, None, annotation or session.analysis.type_of(node)),
                binding=isinstance(getattr(node, "ctx", None), ast.Store),
            )
        )
        blocked.update(ast.walk(node))

    # Outer expressions are useful editing units: a condition or argument can
    # be replaced as a whole without turning every identifier into a control.
    for node in ast.walk(syntax.tree):
        if isinstance(node, (ast.If, ast.While, ast.IfExp)):
            add(node.test, "condition")
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            add(node.iter, "iterable")
        elif isinstance(node, ast.arguments):
            for argument, default in zip(
                (node.posonlyargs + node.args)[
                    len(node.posonlyargs) + len(node.args) - len(node.defaults) :
                ],
                node.defaults,
                strict=True,
            ):
                add(default, argument.arg)
            for argument, default in zip(
                node.kwonlyargs, node.kw_defaults, strict=True
            ):
                if default is not None:
                    add(default, argument.arg)
        elif isinstance(node, ast.Call):
            for index, argument in enumerate(node.args):
                add(argument, f"argument {index + 1}")
            for keyword in node.keywords:
                add(keyword.value, keyword.arg or "arguments")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in (
                node.targets if isinstance(node, ast.Assign) else (node.target,)
            ):
                if isinstance(target, ast.Name):
                    add(target, "name", "identifier")
            if node.value is not None and not isinstance(node.value, ast.Call):
                add(node.value, "value")
    return tuple(sorted(result, key=lambda item: item.span))


def has_choices(session, slot):
    if slot.binding:
        return False
    current = slot.syntax.source[slot.span.start : slot.span.end]
    return any(
        value != current for value in _choices(session, slot.parameter, slot.span.start)
    )


def choices(session, parameter, offset):
    return tuple(dict.fromkeys(_choices(session, parameter, offset)))


def _choices(session, parameter, offset):
    kind = value_type(parameter.annotation)
    if kind is None and parameter.name in {"test", "condition"}:
        kind = "bool"
    enums = {
        "Port": tuple(f"Port.{port}" for port in getattr(session, "ports", "ABCDEF")),
        "Direction": ("Direction.CLOCKWISE", "Direction.COUNTERCLOCKWISE"),
        "Stop": ("Stop.COAST", "Stop.BRAKE", "Stop.HOLD"),
        "Color": (
            "Color.BLACK",
            "Color.WHITE",
            "Color.RED",
            "Color.GREEN",
            "Color.BLUE",
            "Color.YELLOW",
            "Color.NONE",
        ),
    }
    if kind in enums:
        yield from enums[kind]
        return
    if parameter.default is not None and kind in {None, "number", "bool", "str"}:
        yield parameter.default
    if kind == "bool":
        yield from ("True", "False")
    names = session.analysis.name_types(offset)
    if context := getattr(session, "context", None):
        position = context.document.syntax.spans[context.editor.selection].start
        names = context.analysis.name_types(position) | names
    yield from (
        name for name, actual in names.items() if actual == kind and kind is not None
    )
    if parameter.default is not None and names.get(parameter.default) == kind:
        yield parameter.default
    if kind is None:
        yield from (
            name
            for name, actual in names.items()
            if actual not in {"type", "function", "module"}
        )
    # Static library definitions supply readings without importing user modules.
    for snippet in session.snippets:
        body = snippet.body
        if not (
            snippet.expression
            and value_type(snippet.result_type) == kind
            and isinstance(body, ast.Call)
            and isinstance(body.func, ast.Attribute)
        ):
            continue
        receiver = getattr(body.func.value, "template_parameter", None)
        device = next((p for p in snippet.parameters if p.name == receiver), None)
        if device is not None:
            for name, actual in names.items():
                if actual == device.annotation:
                    yield instantiate(snippet, {device.name: name}).source


def default_bindings(session, snippet, offset=None):
    syntax = session.document.syntax
    offset = syntax.spans[session.editor.selection].start if offset is None else offset
    used = identifiers(syntax.tree)
    if context := getattr(session, "context", None):
        used |= identifiers(context.document.syntax.tree)
    result = {}
    roots = (snippet.body,) if snippet.expression else snippet.body
    declared = {
        getattr(node, "template_parameter", None)
        for root in roots
        for node in ast.walk(root)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    for parameter in snippet.parameters:
        value = parameter.default or parameter.name
        if parameter.annotation in {
            "Motor",
            "ColorSensor",
            "ColorDistanceSensor",
            "DriveBase",
            "UltrasonicSensor",
            "ForceSensor",
            "StopWatch",
        } and (suggested := choices(session, parameter, offset)):
            value = (
                value
                if value in suggested
                else next(
                    (
                        candidate
                        for candidate in suggested
                        if candidate not in result.values()
                    ),
                    suggested[0],
                )
            )
        if parameter.name in declared:
            base = value
            suffix = 2
            while value in used:
                value, suffix = f"{base}_{suffix}", suffix + 1
            used.add(value)
        result[parameter.name] = value
    return result


def change_parameter(session, slot, expression):
    syntax = session.document.syntax
    # The popup is attached to this revision. Publishing a new revision closes it.
    if slot.syntax is not syntax:
        raise ValueError("Document changed; choose the parameter again")
    ast.parse(expression, mode="eval")
    if slot.match is not None:
        session.editor.commit(
            edit.replace_expressions(
                syntax,
                [
                    (syntax.spans[node], expression)
                    for node in slot.match.occurrences[slot.parameter.name]
                ],
            )
        )
    else:
        session.editor.selection = next(
            node
            for node, span in syntax.spans.items()
            if span == slot.span and isinstance(node, ast.expr)
        )
        session.editor.replace(expression)
