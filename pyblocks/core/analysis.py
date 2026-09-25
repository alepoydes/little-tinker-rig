"""Conservative lexical names and diagnostics, without importing user modules."""

import ast
import builtins
import inspect
from dataclasses import dataclass, field
from functools import cached_property

from pyblocks.i18n import language, tr

from .syntax import Span, Syntax


@dataclass
class Scope:
    node: ast.AST
    parent: "Scope | None"
    bindings: dict[str, int] = field(default_factory=dict)
    global_names: set[str] = field(default_factory=set)
    nonlocal_names: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Diagnostic:
    span: Span
    message: str
    severity: str = "warning"


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


class Scopes:
    """Lexical bindings shared by diagnostics and hygienic template expansion."""

    def __init__(self, tree: ast.AST, positions: dict[ast.AST, Span] | None = None):
        self.positions = positions or {}
        self.root = Scope(tree, None)
        self.scopes: dict[ast.AST, Scope] = {}
        self.defined_scopes: dict[ast.AST, Scope] = {}
        self.references: list[tuple[ast.Name, Scope]] = []
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

    def _bind(self, scope: Scope, name: str, node: ast.AST) -> None:
        offset = self.positions.get(node, Span(0, 0)).start
        scope.bindings[name] = min(scope.bindings.get(name, offset), offset)

    def _visit(self, node: ast.AST, scope: Scope) -> None:
        self.scopes[node] = scope
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                self.references.append((node, scope))
            elif isinstance(node.ctx, ast.Store):
                self._bind(scope, node.id, node)
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
                self._bind(scope, node.name, node)
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
            return
        if isinstance(
            node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            inner = Scope(node, scope)
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


NUMBER_UNITS = {
    "number",
    "int",
    "float",
    "deg",
    "deg/s",
    "mm",
    "mm/s",
    "ms",
    "s",
    "%",
    "N",
}


def value_type(annotation):
    return "number" if annotation in NUMBER_UNITS else annotation


def annotation_types(annotation):
    """Accepted simple type alternatives in a template hint, without evaluation."""
    return tuple(
        value_type(part.strip())
        for part in (annotation or "").split("|")
        if part.strip()
    )


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
        """Conservative hints, not a type checker or a restriction on user input."""
        if isinstance(node, ast.Constant):
            return (
                "bool"
                if isinstance(node.value, bool)
                else (
                    "number"
                    if isinstance(node.value, (int, float, complex))
                    else "str" if isinstance(node.value, str) else None
                )
            )
        if isinstance(node, ast.Name):
            offset = self.syntax.spans.get(node, Span(len(self.syntax.source), 0)).start
            return self._binding_type(
                self.resolve(node, node.id), node.id, offset, seen
            )
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name in {"int", "float", "abs", "min", "max", "len", "sum", "round"}:
                    return "number"
                if name in {"bool", "str", "list", "tuple", "dict", "set"}:
                    return name
                if name[0].isupper():
                    return name
            elif isinstance(node.func, ast.Attribute):
                return self.method_types.get(
                    (self.type_of(node.func.value, seen), node.func.attr)
                )
        if (
            isinstance(node, ast.Compare)
            or isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.Not)
        ):
            return "bool"
        if isinstance(node, ast.BoolOp):
            return (
                "bool"
                if all(self.type_of(value, seen) == "bool" for value in node.values)
                else None
            )
        if isinstance(node, ast.UnaryOp):
            return self.type_of(node.operand, seen)
        if isinstance(node, ast.BinOp):
            left, right = self.type_of(node.left, seen), self.type_of(node.right, seen)
            return left if left == right else None
        if isinstance(node, (ast.List, ast.ListComp)):
            return "list"
        if isinstance(node, (ast.Tuple, ast.Dict, ast.Set)):
            return type(node).__name__.lower()
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id[0].isupper()
        ):
            return node.value.id
        return None

    def _binding_type(self, scope, name, offset, seen):
        key = (id(scope), name)
        if key in seen:
            return None
        entries = [entry for entry in self.values.get(key, ()) if entry[0] <= offset]
        if not entries:
            return None
        _, value, annotation = max(entries, key=lambda item: item[0])
        return value_type(annotation) or self.type_of(value, seen | {key})

    def name_type(self, name, offset):
        node = self.syntax.at(offset)
        return self._binding_type(self.resolve(node, name), name, offset, frozenset())

    def name_types(self, offset):
        node = self.syntax.at(offset)
        return {
            name: self._binding_type(
                self.resolve(node, name), name, offset, frozenset()
            )
            for name in self.available(offset)
            if name in self.used_names
        }

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
        for node, scope in self.references:
            name = node.id
            origin = scope
            if name in scope.global_names:
                scope = self.root
            elif name in scope.nonlocal_names:
                scope = scope.parent
            found = name in vars(builtins) or name in {
                "__name__",
                "__file__",
                "__package__",
            }
            while scope and not found:
                if name in scope.bindings:
                    found = (
                        scope is not self.root
                        or origin is not self.root
                        or (scope.bindings[name] <= self.syntax.spans[node].start)
                    )
                    break
                if "*" in scope.bindings:
                    found = True  # A star import makes precise lookup impossible.
                scope = scope.parent
            if not found:
                result.append(
                    Diagnostic(self.syntax.spans[node], f"Name {name!r} is not defined")
                )
        for node in ast.walk(self.syntax.tree):
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
                    function_signature(definition).bind(
                        *[None for arg in node.args],
                        **dict.fromkeys(kw.arg for kw in node.keywords),
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
