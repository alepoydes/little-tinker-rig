"""Conservative lexical names and diagnostics, without importing user modules."""

import ast
import builtins
import inspect
from dataclasses import dataclass, field
from functools import cached_property

from little_tinker_rig.i18n import language, tr

from .syntax import Span, Syntax
from .types import (
    NUMERIC,
    Compatibility,
    ValueType,
    compatibility,
    known_type,
    numeric_literal,
)
from .types import annotation_types as parsed_types


@dataclass
class Scope:
    node: ast.AST
    parent: "Scope | None"
    bindings: dict[str, int] = field(default_factory=dict)
    global_names: set[str] = field(default_factory=set)
    nonlocal_names: set[str] = field(default_factory=set)
    initialized: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Diagnostic:
    span: Span
    message: str
    severity: str = "warning"


def attribute_path(node):
    """Separate a receiver from a dotted member path, without evaluating it."""
    path = []
    while isinstance(node, ast.Attribute):
        path.append(node.attr)
        node = node.value
    return node, ".".join(reversed(path))


def identifiers(tree: ast.AST) -> set[str]:
    """All explicit names, including bindings not represented by ast.Name."""
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            result.add(node.id)
        elif isinstance(node, ast.arg):
            result.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result.add(node.name)
        elif isinstance(node, ast.alias):
            result.add(node.asname or node.name.split(".")[0])
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
            if node.name:
                result.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            result.add(node.rest)
    return result


def annotation_nodes(tree):
    """Annotation syntax is distinct from executable parameter expressions."""
    return {
        child
        for node in ast.walk(tree)
        for annotation in (
            getattr(node, "annotation", None),
            getattr(node, "returns", None),
        )
        if annotation is not None
        for child in ast.walk(annotation)
    }


class Scopes:
    """Lexical bindings shared by diagnostics and hygienic template expansion."""

    def __init__(self, tree: ast.AST, positions: dict[ast.AST, Span] | None = None):
        self.positions = positions or {}
        self.root = Scope(tree, None)
        self.scopes: dict[ast.AST, Scope] = {}
        self.defined_scopes: dict[ast.AST, Scope] = {}
        self.references: list[tuple[ast.Name, Scope]] = []
        self.reference_bindings: dict[ast.Name, Scope | None] = {}
        self.deferred_writes = set()
        self._visit(tree, self.root)
        # Declarations govern an entire lexical scope. Resolve after all outer
        # bindings are known, visiting enclosing scopes before their children.
        for scope in self.defined_scopes.values():
            for name in scope.global_names | scope.nonlocal_names:
                if name not in scope.bindings:
                    continue
                owner = self.root if name in scope.global_names else scope.parent
                while owner and name not in owner.bindings and owner is not self.root:
                    owner = owner.parent
                if owner:
                    offset = scope.bindings.pop(name)
                    owner.bindings[name] = min(owner.bindings.get(name, offset), offset)
                    self.deferred_writes.add((id(owner), name))

    def _bind(self, scope: Scope, name: str, node: ast.AST, *, initialize=True) -> None:
        offset = self.positions.get(node, Span(0, 0)).start
        scope.bindings[name] = min(scope.bindings.get(name, offset), offset)
        if initialize:
            scope.initialized.add(name)

    def _reference(self, node, scope):
        self.references.append((node, scope))
        while scope and node.id not in scope.initialized:
            scope = scope.parent
        self.reference_bindings[node] = scope

    def _visit(self, node: ast.AST, scope: Scope) -> None:
        self.scopes[node] = scope
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                self._reference(node, scope)
            elif isinstance(node.ctx, ast.Store):
                self._bind(scope, node.id, node)
            return
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                self._reference(node.target, scope)
            if node.value is not None:
                self._visit(node.value, scope)
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (
                    isinstance(node, ast.AnnAssign)
                    and node.value is None
                    and isinstance(target, ast.Name)
                ):
                    self.scopes[target] = scope
                    self._bind(scope, target.id, target, initialize=False)
                else:
                    self._visit(target, scope)
            if isinstance(node, ast.AnnAssign):
                self._visit(node.annotation, scope)
            return
        if isinstance(node, (ast.For, ast.AsyncFor)):
            self._visit(node.iter, scope)
            self._visit(node.target, scope)
            for child in (*node.body, *node.orelse):
                self._visit(child, scope)
            return
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            names = (
                scope.global_names
                if isinstance(node, ast.Global)
                else scope.nonlocal_names
            )
            names.update(node.names)
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                self.scopes[alias] = scope
                self._bind(scope, alias.asname or alias.name.split(".")[0], node)
            return
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
        ):
            if not isinstance(node, ast.Lambda):
                for decorator in node.decorator_list:
                    self._visit(decorator, scope)
            if isinstance(node, ast.ClassDef):
                for expression in [*node.bases, *node.keywords]:
                    self._visit(expression, scope)
            else:
                for default in [*node.args.defaults, *node.args.kw_defaults]:
                    if default:
                        self._visit(default, scope)
                arguments = [
                    *node.args.posonlyargs,
                    *node.args.args,
                    *node.args.kwonlyargs,
                ]
                arguments.extend(
                    arg for arg in (node.args.vararg, node.args.kwarg) if arg
                )
                for arg in arguments:
                    if arg.annotation:
                        self._visit(arg.annotation, scope)
                if getattr(node, "returns", None):
                    self._visit(node.returns, scope)
            # Methods close over the enclosing function, not class attributes.
            parent = scope.parent if isinstance(scope.node, ast.ClassDef) else scope
            inner = Scope(node, parent)
            self.defined_scopes[node] = inner
            if not isinstance(node, ast.ClassDef):
                for arg in arguments:
                    self.scopes[arg] = inner
                    self._bind(inner, arg.arg, arg)
            body = node.body if isinstance(node.body, list) else [node.body]
            for child in body:
                self._visit(child, inner)
            if not isinstance(node, ast.Lambda):
                self._bind(scope, node.name, node)
            return
        if isinstance(
            node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            # Only the outermost iterable can see the class namespace.
            parent = scope.parent if isinstance(scope.node, ast.ClassDef) else scope
            inner = Scope(node, parent)
            self.defined_scopes[node] = inner
            for index, generator in enumerate(node.generators):
                self._visit(generator.iter, scope if index == 0 else inner)
                self._visit(generator.target, inner)
                for condition in generator.ifs:
                    self._visit(condition, inner)
            for field in ("elt", "key", "value"):
                if hasattr(node, field):
                    self._visit(getattr(node, field), inner)
            return
        if isinstance(node, ast.NamedExpr):
            self._visit(node.value, scope)
            target_scope = scope
            while isinstance(
                target_scope.node,
                (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
            ):
                target_scope = target_scope.parent
            self._visit(node.target, target_scope)
            return
        if (
            isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar))
            and node.name
        ):
            self._bind(scope, node.name, node)
        if isinstance(node, ast.MatchMapping) and node.rest:
            self._bind(scope, node.rest, node)
        for child in ast.iter_child_nodes(node):
            self._visit(child, scope)

    def resolve(self, node: ast.AST, name: str) -> Scope | None:
        scope = self.scopes[node]
        if name in scope.global_names:
            scope = self.root
        elif name in scope.nonlocal_names:
            scope = scope.parent
        while scope:
            if name in scope.bindings:
                return scope
            scope = scope.parent
        return None


def value_type(annotation):
    values = annotation_types(annotation)
    return " | ".join(dict.fromkeys(values)) if values else None


def annotation_types(annotation):
    """Accepted simple type alternatives in a template hint, without evaluation."""
    try:
        return tuple(
            "number" if value.name in NUMERIC else value.name
            for value in parsed_types(annotation)
        )
    except ValueError:
        return ()


def annotation_text(node):
    if node is None:
        return None
    return (
        node.value
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        else ast.unparse(node)
    )


class Analysis(Scopes):
    """Lexical lookup, not flow-sensitive type or definite-assignment analysis."""

    def __init__(self, syntax: Syntax):
        self.syntax = syntax
        self.used_names = identifiers(syntax.tree)
        super().__init__(syntax.tree, syntax.spans)
        self.values = {}
        self.method_types = {}
        self.expression_types = {}
        self.contracts = []
        self.imports = {}
        for node in ast.walk(syntax.tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                for target in targets:
                    if isinstance(target, ast.Name):
                        self.values.setdefault(
                            (id(self.resolve(target, target.id)), target.id), []
                        ).append(
                            (
                                syntax.spans[target].start,
                                node.value,
                                annotation_text(getattr(node, "annotation", None)),
                            )
                        )
            elif isinstance(node, ast.arg):
                self.values[(id(self.scopes[node]), node.arg)] = [
                    (-1, None, annotation_text(node.annotation))
                ]
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    self.values[(id(self.scopes[node]), name)] = [
                        (-1, None, "type" if alias.name[0].isupper() else "module")
                    ]
                    self.imports[id(self.scopes[node]), name] = (
                        f"{node.module}.{alias.name}"
                        if isinstance(node, ast.ImportFrom)
                        else alias.name if alias.asname else name
                    )
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                self.values[(id(self.scopes[node]), node.name)] = [
                    (-1, None, "type" if isinstance(node, ast.ClassDef) else "function")
                ]

    @cached_property
    def definitions(self):
        candidates = {}
        for node in ast.walk(self.syntax.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                key = (id(self.resolve(node, node.name)), node.name)
                candidates.setdefault(key, []).append(node)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                key = (id(self.resolve(node, node.id)), node.id)
                candidates.setdefault(key, []).append(node)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    key = (id(self.resolve(node, name)), name)
                    candidates.setdefault(key, []).append(node)
        return {
            key: nodes[0]
            for key, nodes in candidates.items()
            if len(nodes) == 1
            and isinstance(nodes[0], (ast.FunctionDef, ast.AsyncFunctionDef))
            and not nodes[0].decorator_list
        }

    def call_definition(self, call):
        if not isinstance(call.func, ast.Name):
            return None
        return self.definitions.get(
            (id(self.resolve(call.func, call.func.id)), call.func.id)
        )

    def type_of(self, node, seen=frozenset()):
        """Broad display category derived from the same detailed type model."""
        value = self.type_info(node, seen)
        return (
            "number"
            if value and value.name in NUMERIC
            else value.name if value else None
        )

    def type_info(self, node, seen=frozenset()):
        if node in self.expression_types:
            return self.expression_types[node]
        if isinstance(node, ast.Constant):
            name = "None" if node.value is None else type(node.value).__name__
            return (
                ValueType(name)
                if name in {"None", "bool", "int", "float", "complex", "str", "bytes"}
                else None
            )
        if isinstance(node, ast.Name):
            offset = self.syntax.spans.get(node, Span(len(self.syntax.source), 0)).start
            return self._binding_type(
                self.resolve(node, node.id), node.id, offset, seen
            )
        if isinstance(node, ast.Call):
            definition = self.call_definition(node)
            if definition is not None:
                return known_type(annotation_text(definition.returns))
            if isinstance(node.func, ast.Name):
                name = node.func.id
                owner = self.resolve(node.func, name)
                if owner is None:
                    if name in {
                        "int",
                        "float",
                        "bool",
                        "str",
                        "list",
                        "tuple",
                        "dict",
                        "set",
                    }:
                        return ValueType(name)
                    if name == "len":
                        return ValueType("int")
                    if name in {"abs", "min", "max", "sum", "round"}:
                        values = [self.type_info(arg, seen) for arg in node.args]
                        first = values[0] if values else None
                        return (
                            first
                            if first
                            and first.name in NUMERIC
                            and all(value == first for value in values)
                            else None
                        )
                imported = self.imports.get((id(owner), name), "")
                if (
                    imported.startswith("pybricks.")
                    and imported.rsplit(".", 1)[-1][0].isupper()
                ):
                    return ValueType(imported.rsplit(".", 1)[-1])
            elif isinstance(node.func, ast.Attribute):
                receiver, path = attribute_path(node.func)
                return known_type(
                    self.method_types.get((self.type_of(receiver, seen), path))
                )
        if (
            isinstance(node, ast.Compare)
            or isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.Not)
        ):
            return ValueType("bool")
        if isinstance(node, ast.BoolOp):
            values = [self.type_info(value, seen) for value in node.values]
            return values[0] if all(value == values[0] for value in values) else None
        if isinstance(node, ast.UnaryOp):
            return self.type_info(node.operand, seen)
        if isinstance(node, ast.BinOp):
            left, right = self.type_info(node.left, seen), self.type_info(
                node.right, seen
            )
            if not left or not right:
                return None
            if left.name in NUMERIC and right.name in NUMERIC:
                name = (
                    "float"
                    if "float" in (left.name, right.name)
                    or isinstance(node.op, ast.Div)
                    else "int" if left.name == right.name == "int" else "number"
                )
                if isinstance(node.op, (ast.Add, ast.Sub, ast.Mod)):
                    unit = left.unit if left.unit == right.unit else None
                elif isinstance(node.op, ast.Mult):
                    unit = (
                        left.unit or right.unit
                        if not (left.unit and right.unit)
                        else None
                    )
                elif isinstance(node.op, (ast.Div, ast.FloorDiv)):
                    unit = left.unit if not right.unit else None
                else:
                    unit = None
                return ValueType(name, unit)
            return (
                left
                if left == right
                and left.name in {"str", "list", "tuple"}
                and isinstance(node.op, ast.Add)
                else None
            )
        if isinstance(node, (ast.List, ast.ListComp)):
            return ValueType("list")
        if isinstance(node, (ast.Tuple, ast.Dict, ast.Set)):
            return ValueType(type(node).__name__.lower())
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            imported = self.imports.get(
                (id(self.resolve(node.value, node.value.id)), node.value.id), ""
            )
            if imported.startswith("pybricks.parameters."):
                return ValueType(imported.rsplit(".", 1)[-1])
        return None

    def _binding_type(self, scope, name, offset, seen):
        key = (id(scope), name)
        if key in seen:
            return None
        entries = [entry for entry in self.values.get(key, ()) if entry[0] <= offset]
        if not entries:
            return None
        _, value, annotation = max(entries, key=lambda item: item[0])
        return known_type(annotation) or self.type_info(value, seen | {key})

    def name_type(self, name, offset):
        node = self.syntax.at(offset)
        value = self._binding_type(self.resolve(node, name), name, offset, frozenset())
        return value_type(str(value)) if value else None

    def name_types(self, offset):
        return {
            name: value_type(str(value)) if value else None
            for name, value in self.name_type_info(offset).items()
        }

    def name_type_info(self, offset):
        node = self.syntax.at(offset)
        return {
            name: self._binding_type(
                self.resolve(node, name), name, offset, frozenset()
            )
            for name in self.available(offset)
            if name in self.used_names
        }

    def apply_contracts(self, matches):
        """Use recognized declarations and results without rewriting user source."""
        expressions = {
            span: node
            for node, span in self.syntax.spans.items()
            if isinstance(node, ast.expr)
        }
        for match in matches:
            if match.snippet.expression and match.snippet.result_type:
                node = expressions.get(match.span)
                value = known_type(match.snippet.result_type)
                if node is not None and value is not None:
                    self.expression_types[node] = value
            for parameter in match.snippet.parameters:
                if parameter.name in match.snippet.names:
                    continue
                for node in match.occurrences.get(parameter.name, ()):
                    if (
                        not isinstance(getattr(node, "ctx", None), ast.Store)
                        and parameter.annotation
                    ):
                        self.contracts.append((node, parameter.annotation))
            for target, annotation in match.declarations:
                key = (id(self.resolve(target, target.id)), target.id)
                offset = self.syntax.spans[target].start
                entries = self.values.get(key, ())
                self.values[key] = [
                    (
                        start,
                        value,
                        declared or (annotation if start == offset else None),
                    )
                    for start, value, declared in entries
                ]
                value = self.syntax.parent[target].value
                if value is not None:
                    self.contracts.append((value, annotation))

    def available(self, offset: int) -> tuple[str, ...]:
        node = self.syntax.at(offset)
        scope = self.scopes.get(node, self.root)
        names = set(dir(builtins))
        origin = scope
        while scope:
            names.update(
                name
                for name, start in scope.bindings.items()
                if start <= offset or (scope is self.root and origin is not self.root)
            )
            scope = scope.parent
        return tuple(sorted(names))

    def diagnostics(self) -> tuple[Diagnostic, ...]:
        if getattr(self, "_diagnostic_language", None) != language():
            self._diagnostic_cache = self._diagnostics()
            self._diagnostic_language = language()
        return self._diagnostic_cache

    def _diagnostics(self) -> tuple[Diagnostic, ...]:
        result = []
        contracts = list(self.contracts)
        deferred_annotations = (
            annotation_nodes(self.syntax.tree)
            if any(
                isinstance(node, ast.ImportFrom)
                and node.module == "__future__"
                and any(alias.name == "annotations" for alias in node.names)
                for node in self.syntax.tree.body
            )
            else set()
        )
        for node, scope in self.references:
            name = node.id
            origin = scope
            owner = self.resolve(node, name)
            if owner is not None:
                # Closures run later; their enclosing values need not exist at
                # definition time. Reads in the same execution scope do.
                deferred = False
                while scope is not None and scope is not owner:
                    deferred |= isinstance(
                        scope.node,
                        (
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                            ast.Lambda,
                            ast.GeneratorExp,
                        ),
                    )
                    scope = scope.parent
                found = (
                    deferred
                    or node in deferred_annotations
                    or self.reference_bindings.get(node) is owner
                    or (id(owner), name) in self.deferred_writes
                )
            else:
                found = name in vars(builtins) or name in {
                    "__name__",
                    "__file__",
                    "__package__",
                }
                scope = origin
                while scope and not found:
                    found = "*" in scope.bindings
                    scope = scope.parent
            if not found:
                result.append(
                    Diagnostic(
                        self.syntax.spans[node],
                        tr("Name {name!r} is not defined before this use", name=name),
                    )
                )
        for node in ast.walk(self.syntax.tree):
            if isinstance(node, ast.Constant) and node.value is Ellipsis:
                result.append(
                    Diagnostic(
                        self.syntax.spans[node],
                        tr("Fill this input before running the program"),
                        "error",
                    )
                )
            pairs = ()
            if isinstance(node, ast.BinOp) and isinstance(
                node.op, (ast.Add, ast.Sub, ast.Mod)
            ):
                pairs = ((node.left, node.right),)
            elif isinstance(node, ast.Compare):
                pairs = (
                    (left, right)
                    for left, right, operation in zip(
                        [node.left, *node.comparators[:-1]],
                        node.comparators,
                        node.ops,
                        strict=True,
                    )
                    if isinstance(
                        operation, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
                    )
                )
            for left_node, right_node in pairs:
                left, right = self.type_info(left_node), self.type_info(right_node)
                if (
                    left
                    and right
                    and left.name in NUMERIC
                    and right.name in NUMERIC
                    and left.unit
                    and right.unit
                    and left.unit != right.unit
                ):
                    contracts.append((right_node, f"number[{left.unit}]"))
            if isinstance(node, ast.AnnAssign) and node.value is not None:
                contracts.append((node.value, annotation_text(node.annotation)))
            if isinstance(node, ast.Return) and node.value is not None:
                owner = self.scopes[node].node
                if isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    contracts.append((node.value, annotation_text(owner.returns)))
            if not isinstance(node, ast.Call):
                continue
            if any(isinstance(arg, ast.Starred) for arg in node.args) or any(
                kw.arg is None for kw in node.keywords
            ):
                continue
            message = None
            definition = self.call_definition(node)
            if definition is not None:
                try:
                    bound = function_signature(definition).bind(
                        *node.args,
                        **{kw.arg: kw.value for kw in node.keywords},
                    )
                    for arg in [
                        *definition.args.posonlyargs,
                        *definition.args.args,
                        *definition.args.kwonlyargs,
                    ]:
                        if arg.arg in bound.arguments:
                            contracts.append(
                                (
                                    bound.arguments[arg.arg],
                                    annotation_text(arg.annotation),
                                )
                            )
                except TypeError:
                    message = tr(
                        "Arguments do not match {signature}",
                        signature=definition.name
                        + "("
                        + ast.unparse(definition.args)
                        + ")",
                    )
            elif (
                isinstance(node.func, ast.Name)
                and node.func.id == "range"
                and self.resolve(node.func, "range") is None
            ):
                if not 1 <= len(node.args) <= 3 or node.keywords:
                    message = tr("range expects one to three positional arguments")
                elif (
                    len(node.args) == 3
                    and isinstance(node.args[2], ast.Constant)
                    and node.args[2].value == 0
                ):
                    message = tr("range step cannot be zero")
            if message:
                result.append(Diagnostic(self.syntax.spans[node], message, "error"))
        seen = set()
        for node, expected in contracts:
            if not expected or (node, expected) in seen:
                continue
            seen.add((node, expected))
            actual = self.type_info(node)
            try:
                status = compatibility(expected, actual, literal=numeric_literal(node))
            except ValueError:
                continue  # Ordinary Python may use annotations outside block grammar.
            if status is Compatibility.INCOMPATIBLE:
                result.append(
                    Diagnostic(
                        self.syntax.spans[node],
                        tr(
                            "Expected {expected}, got {actual}",
                            expected=expected,
                            actual=str(actual),
                        ),
                        "error",
                    )
                )
        return tuple(result)


def function_signature(definition):
    """An inspect signature made only from syntax; defaults are never evaluated."""
    args = definition.args
    positional = args.posonlyargs + args.args
    defaults = [inspect.Parameter.empty] * (len(positional) - len(args.defaults))
    defaults += [ast.unparse(value) for value in args.defaults]
    parameters = [
        inspect.Parameter(
            arg.arg,
            (
                inspect.Parameter.POSITIONAL_ONLY
                if i < len(args.posonlyargs)
                else inspect.Parameter.POSITIONAL_OR_KEYWORD
            ),
            default=default,
        )
        for i, (arg, default) in enumerate(zip(positional, defaults, strict=True))
    ]
    if args.vararg:
        parameters.append(
            inspect.Parameter(args.vararg.arg, inspect.Parameter.VAR_POSITIONAL)
        )
    parameters.extend(
        inspect.Parameter(
            arg.arg,
            inspect.Parameter.KEYWORD_ONLY,
            default=(
                inspect.Parameter.empty if default is None else ast.unparse(default)
            ),
        )
        for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True)
    )
    if args.kwarg:
        parameters.append(
            inspect.Parameter(args.kwarg.arg, inspect.Parameter.VAR_KEYWORD)
        )
    return inspect.Signature(parameters)
