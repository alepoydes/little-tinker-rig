"""Reachable ordinary functions for generated block calls; no source execution."""

import ast
import copy
import io
import tokenize

from .analysis import Scopes, function_signature
from .block_metadata import metadata
from .edit import patches
from .imports import import_entries, managed_section
from .source_text import function_source
from .syntax import Span, Syntax

START = "# --- automatically managed helpers ---"
END = "# --- user program ---"


def helper_section(source):
    if START not in source and END not in source:
        return None
    return managed_section(source, START, END)


def dependencies(tree):
    """Module/global references; local bindings never keep a helper alive."""
    scopes = Scopes(tree)
    return {
        node.id
        for node, _ in scopes.references
        if (owner := scopes.resolve(node, node.id)) is None or owner is scopes.root
    }


def helper_signature(function, imports):
    """Runtime code and the global imports it resolves, independent of layout."""
    used = dependencies(ast.Module(body=[function], type_ignores=[]))
    return ast.dump(function), tuple(
        sorted({(name, text) for name, text in import_entries(imports) if name in used})
    )


def manage_helpers(source, available, *, retain=(), required=()):
    """Keep reachable helpers, preserving existing implementations and user text.

    `available` maps authored names to definitions. Existing definitions take
    precedence, including when their library was edited or disconnected.
    Explicit insertion requires matching implementations for existing names.
    """
    syntax = Syntax(source)
    section = helper_section(source)
    existing, user = {}, []
    for node in syntax.tree.body:
        if section and section.contains(syntax.spans[node].start):
            if not isinstance(node, ast.FunctionDef) or node.decorator_list:
                raise ValueError(
                    "Managed helper section may contain only undecorated functions"
                )
            if node.name in existing:
                raise ValueError(f"Duplicate managed helper {node.name!r}")
            existing[node.name] = node
        else:
            user.append(node)
    for name in required:
        if name in existing and ast.dump(existing[name]) != ast.dump(available[name]):
            raise ValueError(
                f"Helper {name!r} already has a different definition; "
                "upgrade it explicitly or rename the block"
            )
    candidates = dict(available, **existing)
    tree = ast.Module(body=user, type_ignores=[])
    referenced = dependencies(tree)
    for fragment in retain:
        try:
            referenced.update(dependencies(Syntax(fragment, fragment=True).tree))
        except (SyntaxError, ValueError):
            try:
                for token in tokenize.generate_tokens(io.StringIO(fragment).readline):
                    if token.type == tokenize.NAME:
                        referenced.add(token.string)
            except (tokenize.TokenError, IndentationError):
                pass
    occupied = Scopes(tree).root.bindings
    selected, visited = [], set()

    def keep(name):
        if name in visited or name not in candidates:
            return
        if name in occupied:
            if name in existing or name in required:
                raise ValueError(
                    f"Helper name {name!r} conflicts with an existing binding"
                )
            return
        visited.add(name)
        function = candidates[name]
        for dependency in sorted(
            dependencies(ast.Module(body=[function], type_ignores=[]))
        ):
            keep(dependency)
        selected.append(function)

    for name in sorted(referenced):
        keep(name)
    if not selected and not section:
        return source, ()
    definitions = []
    for function in selected:
        if function.name in existing:
            span = syntax.block_span(function)
            # Section markers belong to the section, never to a function's text.
            start = max(span.start, section.start + len(START) + 1)
            definitions.append(source[start : span.end].strip())
        else:
            definitions.append(
                getattr(function, "source_text", None) or ast.unparse(function)
            )
    header = (
        START + "\n" + "\n\n".join(definitions) + "\n" + END + "\n" if selected else ""
    )
    if section:
        result = patches(source, [(section, header)])
    elif header:
        offset = 0
        for index, node in enumerate(user):
            docstring = (
                index == 0
                and isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
            if not docstring and not isinstance(node, (ast.Import, ast.ImportFrom)):
                offset = syntax.block_span(node).start
                break
            offset = syntax.block_span(node).end
        imports = managed_section(source)
        if imports:
            offset = max(offset, imports.end)
        result = patches(source, [(Span(offset, offset), header + "\n")])
    else:
        result = source
    return result, tuple(selected)


def function_dependencies(tree):
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    scopes = Scopes(tree)
    dependencies = {}
    for name, function in functions.items():
        # Block defaults belong to the insertion site, not the helper module.
        nodes = (
            set(ast.walk(ast.Module(body=function.body, type_ignores=[])))
            if metadata(function)
            else set(ast.walk(function))
        )
        dependencies[name] = {
            node.id
            for node, _ in scopes.references
            if node in nodes
            and node.id in functions
            and scopes.resolve(node, node.id) is scopes.root
        }
    return functions, dependencies


def helper_functions(tree, roots, *, source=""):
    """Emit reachable functions once, retaining their authored Python names."""
    functions, dependencies = function_dependencies(tree)

    def reachable(names):
        found = set()

        def visit(name):
            if name in found:
                return
            found.add(name)
            for dependency in sorted(dependencies[name]):
                visit(dependency)

        for name in names:
            visit(name)
        return found

    included = reachable(roots)
    implementations = {}
    for name in included:
        function = copy.deepcopy(functions[name])
        options = metadata(function)
        if options and options["mode"] == "inline":
            raise ValueError(
                f"{name}: inline templates cannot be called as helper functions"
            )
        if function.decorator_list and not options:
            raise ValueError(f"{name}: helper decorators are unsupported")
        function.decorator_list = []
        if options:
            function.args.defaults = []
            function.args.kw_defaults = [None] * len(function.args.kwonlyargs)
        implementations[name] = function
    # Block defaults are insertion expressions, unlike ordinary function defaults.
    # Internal Python calls must pass the fields that the library UI supplies.
    scopes = Scopes(tree)
    for name, caller in functions.items():
        for node in ast.walk(caller):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in implementations
                and metadata(functions[node.func.id])
                and scopes.resolve(node.func, node.func.id) is scopes.root
            ):
                continue
            if any(isinstance(arg, ast.Starred) for arg in node.args) or any(
                keyword.arg is None for keyword in node.keywords
            ):
                continue
            try:
                function_signature(implementations[node.func.id]).bind(
                    *node.args,
                    **{keyword.arg: keyword.value for keyword in node.keywords},
                )
            except TypeError as error:
                raise ValueError(
                    f"{name}: calls to block {node.func.id!r} must supply every field; "
                    "block defaults are insertion expressions"
                ) from error
    result, visited = [], set()

    def emit(name):
        if name in visited:
            return
        visited.add(name)
        for dependency in sorted(dependencies[name]):
            emit(dependency)
        function = implementations[name]
        if source:
            function.source_text = function_source(source, functions[name], function)
        result.append(function)

    for name in sorted(included):
        emit(name)
    return tuple(result)


def referenced_helpers(scopes, function):
    functions = {
        n.name
        for n in scopes.root.node.body
        if isinstance(n, ast.FunctionDef) and n is not function
    }
    nodes = {node for root in function.body for node in ast.walk(root)}
    return tuple(
        node
        for node, _ in scopes.references
        if node in nodes
        and node.id in functions
        and scopes.resolve(node, node.id) is scopes.root
    )
