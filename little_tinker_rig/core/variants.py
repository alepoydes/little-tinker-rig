"""Explicit family edits preserve fields, names, comments, and call evaluation order."""

import ast
import copy
import io
import tokenize
from collections import Counter

from little_tinker_rig.i18n import N_

from . import edit
from .analysis import identifiers
from .expressions import accepts
from .parameters import suggestions
from .snippets import Expansion, instantiate, instantiate_tree
from .source_text import rewrite
from .structure import rename_changes
from .syntax import Span
from .types import Compatibility, compatibility, known_type


def field_key(snippet, parameter):
    return snippet.bindings.get(parameter, parameter)


def _tagged(snippet, values):
    result = {}
    for parameter in snippet.parameters:
        value = values.get(parameter.name, parameter.default)
        node = (
            ast.parse(value, mode="eval").body
            if isinstance(value, str)
            else copy.deepcopy(value)
        )
        if node is not None:
            node.catalog_field = field_key(snippet, parameter.name)
        result[parameter.name] = node
    return result


def _walk(node):
    yield node
    if not hasattr(node, "catalog_field"):
        for child in ast.iter_child_nodes(node):
            yield from _walk(child)


def _calls(tree):
    return [
        node
        for node in _walk(tree)
        if isinstance(node, ast.Call) and not hasattr(node, "catalog_field")
    ]


def _callee(call):
    function = call.func
    if isinstance(function, ast.Attribute):
        return "method", function.attr
    if isinstance(function, ast.Name):
        return "function", function.id
    return None


def variant_bindings(session, match, snippet):
    """Transfer compatible public fields; expose fixed API options when available."""
    old = {
        field_key(match.snippet, parameter.name): parameter
        for parameter in match.snippet.parameters
    }
    values = {}
    for parameter in snippet.parameters:
        previous = old.get(field_key(snippet, parameter.name))
        if (
            previous
            and previous.name in match.bindings
            and compatibility(parameter.annotation, known_type(previous.annotation))
            is not Compatibility.INCOMPATIBLE
        ):
            values[parameter.name] = session.document.syntax.text(
                match.bindings[previous.name]
            )

    before = instantiate_tree(
        match.snippet, _tagged(match.snippet, match.bindings), local_names=match.locals
    )
    markers = {p.name: ast.Name(id=p.name, ctx=ast.Load()) for p in snippet.parameters}
    after = instantiate_tree(
        snippet, _tagged(snippet, markers), local_names=match.locals
    )
    old_calls, new_calls = _calls(before), _calls(after)
    if len(old_calls) == len(new_calls):
        by_key = {field_key(snippet, p.name): p.name for p in snippet.parameters}
        for old_call, new_call in zip(old_calls, new_calls, strict=True):
            if _callee(old_call) != _callee(new_call):
                continue
            slots = [*zip(old_call.args, new_call.args, strict=False)]
            keywords = {entry.arg: entry.value for entry in old_call.keywords}
            slots += [
                (keywords[k.arg], k.value)
                for k in new_call.keywords
                if k.arg in keywords
            ]
            for value, target in slots:
                key = getattr(target, "catalog_field", None)
                if key in by_key and not any(
                    hasattr(n, "catalog_field") for n in _walk(value)
                ):
                    values.setdefault(by_key[key], ast.unparse(value))
    return {
        p.name: values.get(p.name, p.default if p.default is not None else "...")
        for p in snippet.parameters
    }


def _field_order(tree):
    return [
        node.catalog_field for node in _walk(tree) if hasattr(node, "catalog_field")
    ]


def _align_call_order(before, after):
    old_calls, new_calls = _calls(before), _calls(after)
    if len(old_calls) != len(new_calls):
        return
    for old, new in zip(old_calls, new_calls, strict=True):
        if _callee(old) != _callee(new):
            continue
        common = set(_field_order(old)) & set(_field_order(new))
        order = [key for key in _field_order(old) if key in common]
        if order == [key for key in _field_order(new) if key in common]:
            continue
        positions = {entry.arg: i for i, entry in enumerate(old.keywords)}
        names = {
            entry.value.catalog_field: entry.arg
            for entry in old.keywords
            if hasattr(entry.value, "catalog_field") and entry.arg is not None
        }
        start = next(
            (
                i
                for i, arg in enumerate(new.args)
                if getattr(arg, "catalog_field", None) in names
            ),
            len(new.args),
        )
        suffix = new.args[start:]
        if suffix and all(
            getattr(arg, "catalog_field", None) in names for arg in suffix
        ):
            new.args = new.args[:start]
            new.keywords = [
                ast.keyword(arg=names[arg.catalog_field], value=arg) for arg in suffix
            ] + new.keywords
        new.keywords.sort(key=lambda entry: positions.get(entry.arg, len(positions)))


def variant_source(session, match, snippet, values):
    """Prepare the exact complete source for review, leaving state and history intact."""
    supplied = [value for value in values.values() if isinstance(value, Expansion)]
    values = {
        name: value.source if isinstance(value, Expansion) else value
        for name, value in values.items()
    }
    if (
        match.snippet.catalog_id != snippet.catalog_id
        or match.snippet.expression != snippet.expression
    ):
        raise ValueError(N_("Choose a variant from the same block family"))
    if match.snippet.historical or snippet.historical:
        raise ValueError(N_("Upgrade a historical block before changing its variant"))
    syntax = session.document.syntax
    old_fields = {
        field_key(match.snippet, name): node for name, node in match.bindings.items()
    }
    renames = [
        change
        for name in snippet.names
        if isinstance(node := old_fields.get(field_key(snippet, name)), ast.Name)
        and (value := values.get(name, node.id)) != node.id
        for change in rename_changes(session, node, value)
    ]
    # Untouched inputs can contain references to a renamed declaration. Preserve
    # explicit field edits; migrate only values copied from the original block.
    for parameter in snippet.parameters:
        node = old_fields.get(field_key(snippet, parameter.name))
        if node is None or values.get(parameter.name) != syntax.text(node):
            continue
        span = syntax.spans[node]
        values[parameter.name] = edit.patches(
            syntax.text(node),
            [
                (Span(part.start - span.start, part.end - span.start), value)
                for part, value in renames
                if span.start <= part.start and part.end <= span.end
            ],
        )
    if snippet.expression:
        node = next(
            n
            for n, span in syntax.spans.items()
            if isinstance(n, ast.expr) and span == match.span
        )
        if not accepts(session, node, known_type(snippet.result_type)):
            raise ValueError(N_("The variant result does not fit this input"))
        original = "(" + syntax.text(node) + "\n)"
    else:
        original = edit.reindent(
            edit.block_text(syntax, session._match_nodes(match)), 0
        )
    occupied = identifiers(syntax.tree) - set(match.locals.values())
    occupied -= {
        value.id
        for name, value in match.bindings.items()
        if name in match.snippet.names and isinstance(value, ast.Name)
    }
    expansion = instantiate(snippet, values, occupied, local_names=match.locals)
    before = instantiate_tree(
        match.snippet, _tagged(match.snippet, match.bindings), local_names=match.locals
    )
    tree = instantiate_tree(
        snippet, _tagged(snippet, values), occupied, local_names=match.locals
    )
    _align_call_order(before, tree)
    common = set(_field_order(before)) & set(_field_order(tree))
    if [k for k in _field_order(before) if k in common] != [
        k for k in _field_order(tree) if k in common
    ]:
        raise ValueError(
            N_(
                "This variant cannot preserve argument evaluation order; edit its Python explicitly"
            )
        )
    if snippet.expression:
        tree = ast.Module(body=[ast.Expr(value=tree)], type_ignores=[])
    replacement = rewrite(original, tree)

    def comments(text):
        return [
            t.string
            for t in tokenize.generate_tokens(io.StringIO(text).readline)
            if t.type == tokenize.COMMENT
        ]

    remaining = Counter(comments(replacement))
    missing = []
    for comment in comments(original):
        if remaining[comment]:
            remaining[comment] -= 1
        else:
            missing.append(comment)
    if missing:
        replacement = "\n".join([*missing, replacement])
        if snippet.expression:
            replacement = "(\n" + replacement + "\n)"
    source = session._replace_match(
        match,
        replacement,
        changes=[
            (span, value)
            for span, value in renames
            if not match.span.contains(span.start)
        ],
    )
    suggested = supplied + [
        value
        for parameter in snippet.parameters
        if parameter.name not in snippet.names
        and (
            value := suggestions(session, parameter, match.span.start).get(
                values.get(parameter.name)
            )
        )
    ]
    prepared = session.prepare_insertion(
        source,
        edit.map_offset(syntax.source, source, match.span.start),
        (
            *expansion.imports,
            *(entry for value in suggested for entry in value.imports),
        ),
        helpers=(
            *expansion.helpers,
            *(entry for value in suggested for entry in value.helpers),
        ),
    )
    return session.document.candidate(prepared).source
