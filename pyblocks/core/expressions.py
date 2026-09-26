"""Compositional expression tools shared by menus, search and keyboard editing.

An ellipsis is an unfinished input in Blocks mode. It is ordinary Python source,
survives save/recovery/Undo and is diagnosed before execution; None remains a value.
"""

import ast
from dataclasses import dataclass

from pyblocks.i18n import N_

from . import edit
from .parameters import ENUM_VALUES, default_bindings, slots
from .snippets import LEVELS
from .structure import OPERATORS
from .syntax import Span
from .types import (
    Compatibility,
    annotation_types,
    compatibility,
    known_type,
    numeric_literal,
)

EMPTY = "..."


def empty(node):
    return isinstance(node, ast.Constant) and node.value is Ellipsis


@dataclass(frozen=True)
class Operation:
    label: str
    template: str
    level: str = "intermediate"
    result: str | None = None

    def source(self, value=EMPTY):
        # Double parentheses are removed only by the syntax-preserving formatter.
        source = self.template.replace("$", f"({value})")
        return (
            source
            if "#" in source
            else ast.unparse(ast.parse(source, mode="eval").body)
        )


OPERATIONS = (
    *(
        Operation(
            f"… {op} …", f"$ {op} ...", result="bool" if kind == "comparison" else None
        )
        for kind, operators in OPERATORS.items()
        if kind != "assignment operator"
        for op in operators
    ),
    Operation("not …", "not $", result="bool"),
    Operation("− …", "-$"),
    Operation("~ …", "~$", "advanced"),
    Operation(N_("Call: …(…)"), "$(...)", "beginner"),
    Operation(N_("Item: …[…]"), "$[...]"),
    Operation(N_("Attribute: ….name"), "$.attribute", "advanced"),
    Operation(N_("Slice: …[start:stop:step]"), "$[...:...:...]", "advanced"),
    Operation(N_("List: […]"), "[$]", "beginner", "list"),
    Operation(N_("Tuple: (…,)"), "($,)", result="tuple"),
    Operation(N_("Set: {…}"), "{$}", "advanced", "set"),
    Operation(N_("Dictionary: {key: value}"), "{$: ...}", result="dict"),
    Operation("… if … else …", "$ if ... else ...", "advanced"),
    Operation(N_("List comprehension"), "[$ for item in ...]", "advanced", "list"),
    Operation(
        N_("Filtered list comprehension"),
        "[$ for item in ... if ...]",
        "advanced",
        "list",
    ),
    Operation(N_("Generator"), "($ for item in ...)", "advanced"),
    Operation(
        N_("Dictionary comprehension"), "{$: ... for item in ...}", "expert", "dict"
    ),
    Operation(N_("Set comprehension"), "{$ for item in ...}", "expert", "set"),
    Operation(N_("Lambda"), "lambda item: $", "expert", "function"),
)


def public(session, node):
    return (
        isinstance(node, ast.expr)
        and (
            not isinstance(getattr(node, "ctx", None), ast.Store)
            or session.field_binding(node) is not None
            or session.editable(node, "name")
        )
        and session.editable(node)
    )


def assignable(node):
    return isinstance(node, (ast.Name, ast.Attribute, ast.Subscript)) or (
        isinstance(node, (ast.Tuple, ast.List))
        and all(assignable(n) for n in node.elts)
    )


def operation_fits(session, node, operation):
    return not isinstance(getattr(node, "ctx", None), ast.Store) or assignable(
        ast.parse(
            operation.source(session.document.syntax.text(node)), mode="eval"
        ).body
    )


def children(session, node):
    """Immediate editable expressions, including arguments hidden behind AST wrappers."""
    result = []
    for child in session.document.syntax.children[node]:
        if public(session, child):
            result.append(child)
        elif not isinstance(child, (ast.expr, ast.stmt)):
            result.extend(children(session, child))
    return tuple(result)


def expected(session, node):
    binding = session.field_binding(node)
    if binding and binding[2] is node:
        annotation = binding[1].annotation
        try:
            annotation_types(annotation)
        except ValueError:
            return None  # Ordinary function annotations can exceed block contracts.
        if annotation:
            return annotation
    parent = session.document.syntax.parent.get(node)
    if isinstance(parent, ast.Call) and parent.func is node:
        return "function | type"
    return None


def accepts(session, node, result=None, *, literal=False):
    return (
        public(session, node)
        and compatibility(expected(session, node), result, literal=literal)
        is not Compatibility.INCOMPATIBLE
    )


def input_roots(session):
    """Outermost public inputs, computed once per palette refresh."""
    selected = session.editor.selection
    if isinstance(selected, ast.expr):
        return (selected,) if public(session, selected) else ()
    syntax = session.document.syntax
    if selected is syntax.tree:
        return ()
    span = syntax.spans[selected]
    match = session.selected_match()
    candidates = []
    for slot in slots(session):
        node = slot.root or slot.node
        if (
            node in candidates
            or node is None
            or slot.binding
            or isinstance(selected, ast.Expr)
            and node is selected.value
            or not span.start <= syntax.spans[node].start < span.end
        ):
            continue
        if (
            match is None
            and next(
                (n for n in syntax.ancestors(node) if isinstance(n, ast.stmt)), None
            )
            is not selected
        ):
            continue
        if public(session, node):
            candidates.append(node)
    # A whole public input takes priority over its nested operands.
    return tuple(
        n
        for n in candidates
        if not any(
            m is not n
            and syntax.spans[m].start <= syntax.spans[n].start
            and syntax.spans[n].end <= syntax.spans[m].end
            for m in candidates
        )
    )


def targets(session, snippet, inputs=None):
    """Possible editable inputs of a selection. Multiple results require a choice."""
    if not snippet.expression:
        return ()
    actual = known_type(snippet.result_type)
    inputs = input_roots(session) if inputs is None else inputs
    return tuple(
        node
        for node in inputs
        if accepts(session, node, actual)
        and (
            not isinstance(getattr(node, "ctx", None), ast.Store)
            or assignable(snippet.body)
        )
    )


def eligible(session, snippet, inputs=None):
    selected = session.editor.selection
    if public(session, selected):
        return bool(targets(session, snippet, inputs))
    if not snippet.expression or isinstance(snippet.body, ast.Call):
        return True
    return bool(targets(session, snippet, inputs))


@dataclass(frozen=True)
class Proposal:
    label: str
    source: str = ""
    operation: Operation | None = None
    snippet: object = None


def proposals(session, level="all", *, wrap=False):
    """Contextual search entries; unknown types remain available, never guessed."""
    node = session.editor.selection
    if not public(session, node):
        return ()
    result = []
    for operation in OPERATIONS:
        if level != "all" and LEVELS.index(operation.level) > LEVELS.index(level):
            continue
        if accepts(session, node, known_type(operation.result)) and operation_fits(
            session, node, operation
        ):
            result.append(Proposal(operation.label, operation=operation))
    if wrap:
        return tuple(result)
    offset = session.document.syntax.spans[node].start
    analysis = session.analysis
    name_types = analysis.name_type_info(offset)
    available = set(analysis.available(offset))
    used = analysis.used_names
    if context := getattr(session, "context", None):
        position = context.document.syntax.spans[context.editor.selection].start
        name_types = context.analysis.name_type_info(position) | name_types
        available.update(context.analysis.available(position))
        used = used | context.analysis.used_names
    for name in sorted(available):
        if level not in {"all", "expert"} and name not in used:
            continue
        if accepts(session, node, name_types.get(name)):
            result.append(Proposal(name, name))
    for value in ("0", '""', "True", "False", "None", "[]", "{}", "()"):
        expression = ast.parse(value, mode="eval").body
        if isinstance(getattr(node, "ctx", None), ast.Store) and not assignable(
            expression
        ):
            continue
        if accepts(
            session,
            node,
            analysis.type_info(expression),
            literal=numeric_literal(expression),
        ):
            result.append(Proposal(value, value))
    for snippet in session.available_snippets:
        if snippet.historical or not snippet.expression:
            continue
        if level != "all" and LEVELS.index(snippet.level) > LEVELS.index(level):
            continue
        if targets(session, snippet):
            result.append(Proposal(snippet.help or snippet.identity, snippet=snippet))
    return tuple(result)


def compose(session, proposal, *, wrap=False):
    node = session.editor.selection
    if not public(session, node):
        raise ValueError("Select an editable expression")
    syntax = session.document.syntax
    route = syntax.path(node)
    offset = syntax.spans[node].start
    if proposal.snippet is not None:
        session.insert_snippet(
            proposal.snippet, default_bindings(session, proposal.snippet, offset)
        )
    else:
        text = (
            proposal.operation.source(
                syntax.text(node)
                if wrap or isinstance(getattr(node, "ctx", None), ast.Store)
                else EMPTY
            )
            if proposal.operation
            else proposal.source
        )
        value = ast.parse(text, mode="eval").body
        required = {
            f"from pybricks.parameters import {n.value.id}"
            for n in ast.walk(value)
            if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id in {"Port", *ENUM_VALUES}
            and session.analysis.resolve(node, n.value.id) is None
        }
        source = session._field_source(node, edit.replace(syntax, node, text))
        session.commit_insertion(source, offset, tuple(sorted(required)))
    # Continue construction at the first new input, not at the callable's name.
    syntax = session.document.syntax
    inserted = syntax.follow(route)
    offset = syntax.spans[inserted].start
    session.editor.selection = inserted
    candidates = [
        n for n in syntax.spans if empty(n) and syntax.spans[n].start >= offset
    ]
    if candidates:
        session.editor.selection = min(candidates, key=lambda n: syntax.spans[n].start)


def unwrap(session, child):
    """Keep one immediate operand; other operands are intentionally discarded."""
    node = session.editor.selection
    if child not in children(session, node):
        raise ValueError("Choose an operand of the selected expression")
    session.replace_expression(node, session.document.syntax.text(child))


def navigate(session, direction):
    syntax = session.document.syntax
    node = session.editor.selection
    if direction == "parent":
        parent = next(
            (n for n in syntax.ancestors(node) if n is not node and public(session, n)),
            None,
        )
        if parent is not None:
            session.editor.selection = parent
        else:
            session.editor.parent()
    elif direction == "child":
        values = children(session, node)
        if values:
            session.editor.selection = values[0]
        else:
            session.editor.child()
    else:
        values = [
            s.node
            for s in slots(session)
            if not s.container and not s.binding and public(session, s.node)
        ]
        if values:
            offset = syntax.spans[node].start
            if direction == "previous":
                values.reverse()
                following = [n for n in values if syntax.spans[n].start < offset]
            else:
                following = [n for n in values if syntax.spans[n].start > offset]
            session.editor.selection = (following or values)[0]
    return session.editor.selection


def copy_to(session, node, target, *, move=False):
    """Transfer a public expression with one undo step and linked input propagation."""
    if not public(session, node) or not public(session, target):
        raise ValueError("Choose editable expressions")
    syntax = session.document.syntax
    a, b = syntax.spans[node], syntax.spans[target]
    if a.start < b.end and b.start < a.end:
        raise ValueError("An expression cannot contain its destination")
    if not accepts(
        session, target, session.analysis.type_info(node), literal=numeric_literal(node)
    ):
        raise ValueError("The expression does not fit this parameter")
    changes = [(b, edit.block_text(syntax, node))]
    removals = []
    if move:
        parent = syntax.parent.get(node)
        if isinstance(parent, ast.Expr):
            removals.append(edit._removal(syntax, parent))
        else:
            changes.append((a, EMPTY))
    # Transfer between different linked inputs is resolved from original coordinates.
    grouped = {}
    direct = []
    for span, text in changes:
        changed = node if span == a else target
        binding = session.field_binding(changed)
        if binding:
            match, parameter, root = binding
            key = (match.span, parameter.name)
            root_span = syntax.spans[root]
            local = Span(span.start - root_span.start, span.end - root_span.start)
            grouped.setdefault(key, (match, parameter, root, []))[3].append(
                (local, text)
            )
        else:
            direct.append((span, text))
    for match, parameter, root, edits in grouped.values():
        value = edit.patches(
            syntax.text(root),
            edits,
        )
        direct.extend(
            (syntax.spans[n], value) for n in match.occurrences[parameter.name]
        )
    source = edit.replace_expressions(syntax, direct, removals=removals)
    session.editor.commit(source, focus=edit.map_offset(syntax.source, source, b.start))
