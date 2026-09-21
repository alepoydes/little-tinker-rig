"""Conservative lexical names and diagnostics, without importing user modules."""

import ast
import builtins
from dataclasses import dataclass, field

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


class Analysis(Scopes):
    """Lexical lookup, not flow-sensitive type or definite-assignment analysis."""

    def __init__(self, syntax: Syntax):
        self.syntax = syntax
        super().__init__(syntax.tree, syntax.spans)

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
        return tuple(result)
