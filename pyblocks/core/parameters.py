"""Editable expression slots and suggested bindings, derived entirely from source."""

import ast
from dataclasses import dataclass

from . import edit
from .analysis import identifiers
from .snippets import Match, Parameter
from .syntax import Span, Syntax


@dataclass(frozen=True)
class Slot:
    syntax: Syntax
    span: Span
    parameter: Parameter
    match: Match | None = None


def slots(session):
    syntax = session.document.syntax
    result = []
    covered = []
    for match in session.visible_matches:
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
                result.append(Slot(syntax, syntax.spans[node], parameter, match))
        if assignment and isinstance(match.bindings[assignment], ast.Call):
            covered.extend(slot.span for slot in result if slot.match is match)
        else:
            covered.append(match.span)

    def add(node, name, annotation=None):
        if node not in syntax.spans:
            return
        span = syntax.spans[node]
        if any(item.start <= span.start and span.end <= item.end for item in covered):
            return
        if syntax.position(span.start)[0] != syntax.position(span.end)[0]:
            return
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "Port"
        ):
            name, annotation = "port", "Port"
        result.append(Slot(syntax, span, Parameter(name, None, annotation)))
        covered.append(span)

    # Outer expressions are useful editing units: a condition or argument can
    # be replaced as a whole without turning every identifier into a control.
    for node in ast.walk(syntax.tree):
        if isinstance(node, (ast.If, ast.While, ast.IfExp)):
            add(node.test, "condition")
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            add(node.iter, "iterable")
        elif isinstance(node, ast.Call):
            for index, argument in enumerate(node.args):
                add(argument, f"argument {index + 1}")
            for keyword in node.keywords:
                add(keyword.value, keyword.arg or "arguments")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            if node.value is not None and not isinstance(node.value, ast.Call):
                add(node.value, "value")
    return tuple(sorted(result, key=lambda item: item.span))


def choices(session, parameter, offset):
    available = session.analysis.available(offset)
    typed = []
    for node in ast.walk(session.document.syntax.tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        constructor = ast.unparse(node.value.func).rsplit(".", 1)[-1]
        if constructor == parameter.annotation:
            typed.extend(
                target.id
                for target in node.targets
                if isinstance(target, ast.Name) and target.id in available
            )
    if parameter.name == "port":
        return tuple(
            f"Port.{port}" if parameter.annotation == "Port" else repr(port)
            for port in "ABCDEF"
        )
    if parameter.name in {"test", "condition"}:
        return ("True", "False", *available)
    values = [*typed]
    if parameter.default is not None:
        values.append(parameter.default)
    values.extend(
        name for name in available if name in identifiers(session.document.syntax.tree)
    )
    return tuple(dict.fromkeys(values))


def default_bindings(session, snippet, offset=None):
    syntax = session.document.syntax
    offset = syntax.spans[session.editor.selection].start if offset is None else offset
    used = identifiers(syntax.tree)
    result = {}
    roots = (snippet.body,) if snippet.expression else snippet.body
    declared = {
        getattr(node, "template_parameter", None)
        for root in roots
        for node in ast.walk(root)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    for parameter in snippet.parameters:
        suggested = choices(session, parameter, offset)
        value = parameter.default or parameter.name
        if (
            parameter.annotation
            in {
                "Motor",
                "ColorSensor",
                "ColorDistanceSensor",
                "DriveBase",
                "UltrasonicSensor",
                "ForceSensor",
            }
            and suggested
        ):
            value = suggested[0]
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
