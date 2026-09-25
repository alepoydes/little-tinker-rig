"""Editable expression slots and suggested bindings, derived entirely from source."""

import ast
from bisect import bisect_right
from dataclasses import dataclass

from . import edit
from .analysis import annotation_types, attribute_path, identifiers, value_type
from .snippets import Match, Parameter, instantiate
from .structure import OPERATORS, change_operator, name_span, operator_spans, rename
from .syntax import Span, Syntax
from .types import Compatibility, compatibility, known_type

ENUM_VALUES = {
    "Direction": ("CLOCKWISE", "COUNTERCLOCKWISE"),
    "Stop": ("COAST", "BRAKE", "HOLD"),
    "Color": ("BLACK", "WHITE", "RED", "GREEN", "BLUE", "YELLOW", "NONE"),
    "Button": (
        "CENTER",
        "LEFT",
        "RIGHT",
        "BLUETOOTH",
        "LEFT_PLUS",
        "LEFT_MINUS",
        "RIGHT_PLUS",
        "RIGHT_MINUS",
    ),
    "Side": ("TOP", "BOTTOM", "LEFT", "RIGHT", "FRONT", "BACK"),
    "Icon": (
        "HEART",
        "HAPPY",
        "SAD",
        "CIRCLE",
        "SQUARE",
        "UP",
        "DOWN",
        "LEFT",
        "RIGHT",
    ),
}


@dataclass(frozen=True)
class Slot:
    syntax: Syntax
    span: Span
    parameter: Parameter
    match: Match | None = None
    binding: bool = False
    node: ast.AST | None = None
    field: str = ""
    root: ast.AST | None = None
    container: bool = False
    operator_index: int = 0


def slots(session):
    syntax = session.document.syntax
    result = {}
    covered = []
    covered_spans = set()
    bindings = []
    declarations = sorted(
        (span.start, node)
        for node, span in syntax.spans.items()
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.arg)
        )
        or isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Store)
    )
    declaration_starts = [start for start, _ in declarations]

    def add(
        node,
        name,
        annotation=None,
        match=None,
        parameter=None,
        field="",
        root=None,
        container=False,
    ):
        span = name_span(syntax, node) if field else syntax.spans.get(node)
        if span is None:
            return
        if (
            not container
            and syntax.position(span.start)[0] != syntax.position(span.end)[0]
        ):
            return
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "Port"
        ):
            name, annotation = "port", "Port"
        if parameter is not None and root is not None and node is not root:
            parameter = Parameter(
                parameter.name,
                None,
                annotation if field else session.analysis.type_of(node),
            )
        result.setdefault(
            span,
            Slot(
                syntax,
                span,
                parameter
                or Parameter(name, None, annotation or session.analysis.type_of(node)),
                match,
                bool(field) or isinstance(getattr(node, "ctx", None), ast.Store),
                node,
                field,
                root,
                container,
            ),
        )

    def expression(
        node, name="value", annotation=None, match=None, parameter=None, root=None
    ):
        if not isinstance(node, ast.expr):
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            name, annotation = "name", "identifier"
        if isinstance(
            node, (ast.BoolOp, ast.BinOp, ast.Compare, ast.UnaryOp, ast.Call)
        ):
            add(node, name, annotation, match, parameter, root=root, container=True)
        if match is None and syntax.spans[node] in covered_spans:
            return
        if isinstance(node, (ast.Name, ast.Constant)) or (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in {"Port", *ENUM_VALUES}
        ):
            add(
                node,
                name,
                annotation or ("function" if name == "function" else None),
                match,
                parameter,
                root=root,
            )
        elif isinstance(node, ast.Attribute):
            expression(
                node.value, "object", match=match, parameter=parameter, root=root
            )
            add(
                node,
                "attribute",
                "identifier",
                match,
                parameter,
                field="attr",
                root=root,
            )
        elif isinstance(node, ast.Call):
            if not session.simplified_range(node):
                expression(
                    node.func, "function", match=match, parameter=parameter, root=root
                )
            for index, arg in enumerate(node.args):
                expression(
                    arg,
                    f"argument {index + 1}",
                    match=match,
                    parameter=parameter,
                    root=root,
                )
            for kw in node.keywords:
                if kw.arg:
                    add(
                        kw,
                        "keyword",
                        "identifier",
                        match,
                        parameter,
                        field="keyword",
                        root=root,
                    )
                expression(
                    kw.value,
                    kw.arg or "arguments",
                    match=match,
                    parameter=parameter,
                    root=root,
                )
        else:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.expr):
                    expression(child, "value", None, match, parameter, root)
                elif isinstance(child, ast.comprehension):
                    expression(child.target, "name", "identifier")
                    expression(child.iter, "iterable")
                    for test in child.ifs:
                        expression(test, "condition")

    for match in session.visible_matches:
        covered.append(match.span)
        covered_spans.add(match.span)
        for parameter in match.snippet.parameters:
            if parameter.name in match.snippet.names:
                continue
            for node in match.occurrences.get(parameter.name, ()):
                bindings.append((syntax.spans[node], match, parameter, node))
                expression(
                    node, parameter.name, parameter.annotation, match, parameter, node
                )
        # Only published declarations are name fields in a decorated block.
        for _, node in declarations[
            bisect_right(declaration_starts, match.span.start - 1) : bisect_right(
                declaration_starts, match.span.end - 1
            )
        ]:
            span = syntax.spans[node]
            if match.span.start <= span.start and span.end <= match.span.end:
                if not session.editable(node, "name"):
                    continue
                published = next(
                    (
                        name
                        for name, key in match.snippet.names.items()
                        if node in match.named.get(key, ())
                    ),
                    None,
                )
                owner = match if published else None
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    add(node, published or "name", "identifier", owner, field="id")
                elif isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    add(
                        node,
                        published or "function name",
                        "identifier",
                        owner,
                        field="name",
                    )
                elif isinstance(node, ast.arg):
                    add(
                        node, published or "parameter", "identifier", owner, field="arg"
                    )

    covered.sort()
    starts = [span.start for span in covered]

    def visit(node):
        span = syntax.spans.get(node)
        if span is not None:
            index = bisect_right(starts, span.start) - 1
            if index >= 0 and span.end <= covered[index].end:
                return
        if isinstance(node, (ast.If, ast.While, ast.IfExp)):
            expression(node.test, "condition", "bool")
        if isinstance(node, ast.expr):
            expression(node)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add(node, "function name", "identifier", field="name")
        elif isinstance(node, ast.arg):
            add(node, "parameter", "identifier", field="arg")
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(syntax.tree)
    for node in syntax.spans:
        if (
            isinstance(node, ast.Call)
            and not session.simplified_range(node)
            and session.editable(node.func)
        ):
            expression(node.func, "function")
    bindings.sort(key=lambda item: item[0])
    binding_starts = [item[0].start for item in bindings]
    for node in syntax.spans:
        if not session.editable(node):
            continue
        for span, kind, index in operator_spans(syntax, node):
            position = bisect_right(binding_starts, syntax.spans[node].start) - 1
            match = root = None
            name = "operator"
            if position >= 0 and syntax.spans[node].end <= bindings[position][0].end:
                _, match, parameter, root = bindings[position]
                name = parameter.name
            result[span] = Slot(
                syntax,
                span,
                Parameter(name, None, kind),
                match,
                binding=True,
                node=node,
                field="operator",
                root=root,
                operator_index=index,
            )
    return tuple(result[span] for span in sorted(result))


def has_choices(session, slot):
    if slot.binding and slot.field != "operator":
        return False
    current = slot.syntax.source[slot.span.start : slot.span.end]
    return any(
        value != current for value in _choices(session, slot.parameter, slot.span.start)
    )


def choices(session, parameter, offset):
    return tuple(dict.fromkeys(_choices(session, parameter, offset)))


def _choices(session, parameter, offset):
    expected = parameter.annotation
    if expected in OPERATORS:
        yield from OPERATORS[expected]
        return
    kind = value_type(parameter.annotation)
    if kind is None and parameter.name in {"test", "condition"}:
        expected = kind = "bool"
    if kind == "Port":
        yield from (f"Port.{port}" for port in getattr(session, "ports", "ABCDEF"))
        return
    if kind in ENUM_VALUES:
        yield from (f"{kind}.{member}" for member in ENUM_VALUES[kind])
        return
    if parameter.default is not None and kind in {None, "number", "bool", "str"}:
        yield parameter.default
    if kind == "bool":
        yield from ("True", "False")
    names = session.analysis.name_type_info(offset)
    if context := getattr(session, "context", None):
        position = context.document.syntax.spans[context.editor.selection].start
        names = context.analysis.name_type_info(position) | names
    yield from (
        name
        for name, actual in names.items()
        if kind is not None
        and actual is not None
        and compatibility(expected, actual) is not Compatibility.INCOMPATIBLE
    )
    if kind is None:
        yield from (
            name
            for name, actual in names.items()
            if actual is None or actual.name not in {"type", "function", "module"}
        )
    # Static library definitions supply readings without importing user modules.
    for snippet in session.snippets:
        body = snippet.body
        if not (
            snippet.expression
            and kind is not None
            and known_type(snippet.result_type) is not None
            and compatibility(expected, known_type(snippet.result_type))
            is not Compatibility.INCOMPATIBLE
            and isinstance(body, ast.Call)
            and isinstance(body.func, ast.Attribute)
        ):
            continue
        root, _ = attribute_path(body.func)
        receiver = getattr(root, "template_parameter", None)
        device = next((p for p in snippet.parameters if p.name == receiver), None)
        if device is not None:
            for name, actual in names.items():
                if (
                    actual is not None
                    and compatibility(device.annotation, actual)
                    is Compatibility.COMPATIBLE
                ):
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
        if set(annotation_types(parameter.annotation)) & {
            "Motor",
            "ColorSensor",
            "ColorDistanceSensor",
            "DriveBase",
            "UltrasonicSensor",
            "ForceSensor",
            "StopWatch",
            "Car",
            "Remote",
            "PrimeHub",
            "InventorHub",
            "MoveHub",
            "TechnicHub",
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
    if slot.field == "operator":
        source = change_operator(syntax, slot.node, slot.operator_index, expression)
    elif slot.field:
        import keyword

        if not expression.isidentifier() or keyword.iskeyword(expression):
            raise ValueError("Enter a Python identifier")
        if slot.field in {"id", "name", "arg"}:
            source = rename(session, slot.node, expression)
        else:
            source = edit.patches(syntax.source, [(slot.span, expression)])
            syntax.validate(source)
    else:
        source = edit.replace_expressions(syntax, [(slot.span, expression)])
    if slot.match is not None and slot.field not in {"id", "name", "arg"}:
        root = slot.root or slot.node
        root_span = syntax.spans[root]
        length = len(source) - len(syntax.source)
        replacement = source[root_span.start : root_span.end + length]
        source = edit.replace_expressions(
            syntax,
            [
                (syntax.spans[node], replacement)
                for node in slot.match.occurrences[slot.parameter.name]
            ],
        )
    session.editor.commit(source, focus=slot.span.start)
