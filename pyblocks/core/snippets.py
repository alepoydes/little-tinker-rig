"""Static Python-function templates: binding, hygienic expansion and recognition."""

import ast
import copy
import tomllib
from bisect import bisect_left
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from .analysis import Analysis, Scopes, annotation_text, identifiers, value_type
from .syntax import Span, Syntax


@dataclass(frozen=True)
class Parameter:
    name: str
    default: str | None
    annotation: str | None


@dataclass(frozen=True)
class Snippet:
    identity: str
    version: str
    parameters: tuple[Parameter, ...]
    body: tuple[ast.stmt, ...] | ast.expr
    imports: tuple[ast.Import | ast.ImportFrom, ...]
    help: str
    locals: dict[str, str]
    historical: bool = False
    result_type: str | None = None

    @property
    def expression(self) -> bool:
        return isinstance(self.body, ast.expr)

    @cached_property
    def specificity(self) -> int:
        roots = (self.body,) if self.expression else self.body
        return sum(
            1
            for root in roots
            for node in ast.walk(root)
            if not isinstance(node, ast.expr_context)
            and not hasattr(node, "template_parameter")
        )


@dataclass(frozen=True)
class Expansion:
    source: str
    imports: tuple[str, ...]


@dataclass(frozen=True)
class Match:
    snippet: Snippet
    span: Span
    bindings: dict[str, ast.expr]
    locals: dict[str, str]
    occurrences: dict[str, tuple[ast.expr, ...]]


def load_module(
    source: str, collection: str, version: str, *, historical: bool = False
) -> tuple[Snippet, ...]:
    """Read definitions without importing or evaluating any template code."""
    result = []
    for function in ast.parse(source).body:
        if not isinstance(function, ast.FunctionDef):
            continue
        if function.decorator_list or function.args.vararg or function.args.kwarg:
            raise ValueError(
                f"{function.name}: decorators and variadic parameters are unsupported"
            )
        args = function.args
        positional = [*args.posonlyargs, *args.args]
        defaults = [None] * (len(positional) - len(args.defaults)) + args.defaults
        parameters = tuple(
            Parameter(
                arg.arg,
                ast.unparse(default) if default is not None else None,
                (
                    (
                        arg.annotation.value
                        if isinstance(arg.annotation, ast.Constant)
                        and isinstance(arg.annotation.value, str)
                        else ast.unparse(arg.annotation)
                    )
                    if arg.annotation
                    else None
                ),
            )
            for arg, default in zip(
                positional + args.kwonlyargs, defaults + args.kw_defaults, strict=True
            )
        )
        body = list(function.body)
        help_text = ast.get_docstring(function) or ""
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)
        imports = tuple(n for n in body if isinstance(n, (ast.Import, ast.ImportFrom)))
        body = [n for n in body if n not in imports]
        if not body:
            raise ValueError(f"{function.name}: empty template")
        for node in ast.walk(ast.Module(body=body, type_ignores=[])):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == function.name
            ):
                raise ValueError(f"{function.name}: recursive template")
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                raise ValueError(
                    f"{function.name}: global/nonlocal declarations cannot be hygienic"
                )
            if isinstance(node, ast.ClassDef):
                raise ValueError(
                    f"{function.name}: classes belong in an ordinary helper module, not a template"
                )
        local_names = _template_names(function, body, imports, parameters)
        template = (
            body[0].value
            if len(body) == 1 and isinstance(body[0], ast.Return)
            else tuple(body)
        )
        if template is None:
            template = ast.Constant(None)
        result.append(
            Snippet(
                f"{collection}/{function.name}",
                version,
                parameters,
                template,
                imports,
                help_text,
                local_names,
                historical,
                annotation_text(function.returns),
            )
        )
    return tuple(result)


def _template_names(function, body, imports, parameters) -> dict[str, str]:
    """Annotate owned AST nodes with lexical keys; never rename by spelling alone."""
    scopes = Scopes(ast.Module(body=[function], type_ignores=[]))
    outer = scopes.defined_scopes[function]
    parameter_names = {p.name for p in parameters}
    dependencies = {
        alias.asname or alias.name.split(".")[0]
        for node in imports
        for alias in node.names
    }
    if parameter_names & dependencies:
        raise ValueError(
            f"{function.name}: parameters cannot shadow dependency imports"
        )
    numbers = {
        id(scope): index for index, scope in enumerate(scopes.defined_scopes.values())
    }
    result = {}
    definitions = {}
    for node in ast.walk(function):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node is not function
        ):
            owner = scopes.resolve(node, node.name)
            definitions[id(owner), node.name] = node
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            owner = scopes.resolve(node.func, node.func.id)
            definition = definitions.get((id(owner), node.func.id))
            if definition is not None:
                inner = scopes.defined_scopes[definition]
                for keyword in node.keywords:
                    if keyword.arg and keyword.arg in inner.bindings:
                        key = f"{numbers[id(inner)]}:{keyword.arg}"
                        keyword.template_names = {"arg": key}
                        result[key] = keyword.arg
        field = None
        if isinstance(node, ast.Name):
            field, name = "id", node.id
        elif isinstance(node, ast.arg):
            field, name = "arg", node.arg
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            field, name = "name", node.name
        elif (
            isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar))
            and node.name
        ):
            field, name = "name", node.name
        elif isinstance(node, ast.MatchMapping) and node.rest:
            field, name = "rest", node.rest
        elif isinstance(node, ast.alias):
            if "." in node.name and not node.asname:
                raise ValueError(
                    "Nested dotted imports in templates require an explicit alias"
                )
            field, name = "asname", node.asname or node.name
        if field is None:
            continue
        owner = scopes.resolve(node, name)
        if owner is outer and name in parameter_names and isinstance(node, ast.Name):
            node.template_parameter = name
        elif (
            owner is not None
            and owner is not scopes.root
            and not (owner is outer and name in dependencies)
        ):
            key = name if owner is outer else f"{numbers[id(owner)]}:{name}"
            node.template_names = {field: key}
            result[key] = name
    return result


def load_collection(directory: Path) -> tuple[Snippet, ...]:
    """Load collection.toml, modules and optional historical versions."""
    with (directory / "collection.toml").open("rb") as stream:
        manifest = tomllib.load(stream)
    identity, version = manifest["collection"]["id"], manifest["collection"]["version"]
    histories = []
    for history in manifest.get("history", []):
        root = (directory / history["path"]).resolve()
        if not root.is_relative_to(directory.resolve()) or root == directory.resolve():
            raise ValueError(
                "Historical templates must be in a collection subdirectory"
            )
        if not root.is_dir():
            raise ValueError(f"Historical template directory does not exist: {root}")
        histories.append((root, history["version"]))
    result = []
    for path in sorted(directory.rglob("*.py")):
        if path.name == "__init__.py" or any(
            path.resolve().is_relative_to(root) for root, _ in histories
        ):
            continue
        module = path.relative_to(directory).with_suffix("").as_posix()
        result.extend(
            load_module(
                path.read_text(encoding="utf-8"), f"{identity}/{module}", version
            )
        )
    for root, historical_version in histories:
        for path in sorted(root.rglob("*.py")):
            module = path.relative_to(root).with_suffix("").as_posix()
            result.extend(
                load_module(
                    path.read_text(encoding="utf-8"),
                    f"{identity}/{module}",
                    historical_version,
                    historical=True,
                )
            )
    identities = [(snippet.identity, snippet.version) for snippet in result]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate snippet identity and version")
    return tuple(result)


def builtin_snippets() -> tuple[Snippet, ...]:
    root = Path(__file__).parents[1] / "snippets"
    return tuple(
        snippet
        for path in sorted(root.iterdir())
        if (path / "collection.toml").is_file()
        for snippet in load_collection(path)
    )


def instantiate(
    snippet: Snippet,
    bindings: dict[str, str | ast.expr],
    occupied: set[str] | None = None,
    *,
    local_names: dict[str, str] | None = None,
) -> Expansion:
    """Substitute expressions. Repeated parameters repeat evaluation, as in source."""
    values = {}
    extra = bindings.keys() - {p.name for p in snippet.parameters}
    if extra:
        raise ValueError(f"Unknown parameters: {', '.join(sorted(extra))}")
    used = set(occupied or ())
    for parameter in snippet.parameters:
        value = bindings.get(parameter.name, parameter.default)
        if value is None:
            raise ValueError(
                f"Parameter {parameter.name!r} requires a Python expression"
            )
        expression = (
            ast.parse(value, mode="eval").body if isinstance(value, str) else value
        )
        values[parameter.name] = expression
        used.update(identifiers(expression))
    renamed = dict(local_names or {})
    for key, name in sorted(snippet.locals.items()):
        if key not in renamed:
            candidate, suffix = name, 2
            while candidate in used:
                candidate, suffix = f"{name}_{suffix}", suffix + 1
            renamed[key] = candidate
        used.add(renamed[key])

    class Substitute(ast.NodeTransformer):
        def visit_Name(self, node):
            parameter = getattr(node, "template_parameter", None)
            if parameter is not None:
                result = copy.deepcopy(values[parameter])
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    if not isinstance(
                        result,
                        (ast.Name, ast.Attribute, ast.Subscript, ast.Tuple, ast.List),
                    ):
                        raise ValueError(f"{node.id} must be an assignable expression")
                    result.ctx = node.ctx
                return ast.copy_location(result, node)
            return self.generic_visit(node)

        def generic_visit(self, node):
            for field, key in getattr(node, "template_names", {}).items():
                setattr(node, field, renamed[key])
            return super().generic_visit(node)

    tree = copy.deepcopy(
        snippet.body
        if snippet.expression
        else ast.Module(body=list(snippet.body), type_ignores=[])
    )
    tree = ast.fix_missing_locations(Substitute().visit(tree))
    return Expansion(
        ast.unparse(tree), tuple(ast.unparse(node) for node in snippet.imports)
    )


def _match(snippet: Snippet, candidate) -> tuple[dict, dict, dict] | None:
    bindings, local_names = {}, {}
    occurrences = {}

    def equal(pattern, value) -> bool:
        parameter = getattr(pattern, "template_parameter", None)
        if parameter is not None:
            if not isinstance(value, ast.expr):
                return False
            occurrences.setdefault(parameter, []).append(value)
            previous = bindings.get(parameter)
            if previous is None:
                bindings[parameter] = value
                return True
            # Load/Store is a use-site property, not part of a placeholder value.
            a, b = copy.deepcopy(previous), copy.deepcopy(value)
            for expression in (a, b):
                for node in ast.walk(expression):
                    if hasattr(node, "ctx"):
                        node.ctx = ast.Load()
            return ast.dump(a) == ast.dump(b)
        if type(pattern) is not type(value):
            return False
        if isinstance(pattern, ast.AST):
            for field, expected in ast.iter_fields(pattern):
                actual = getattr(value, field)
                key = getattr(pattern, "template_names", {}).get(field)
                if key is not None:
                    if isinstance(value, ast.alias) and actual is None:
                        actual = value.name
                    if key not in local_names:
                        namespace = key.rpartition(":")[0]
                        if any(
                            other.rpartition(":")[0] == namespace and name == actual
                            for other, name in local_names.items()
                        ):
                            return False
                        local_names[key] = actual
                    if local_names[key] != actual:
                        return False
                elif not equal(expected, actual):
                    return False
            return True
        if isinstance(pattern, (list, tuple)):
            return len(pattern) == len(value) and all(
                equal(a, b) for a, b in zip(pattern, value, strict=True)
            )
        return pattern == value

    if not equal(snippet.body, candidate):
        return None
    return (
        bindings,
        local_names,
        {name: tuple(nodes) for name, nodes in occurrences.items()},
    )


def recognize(
    syntax: Syntax, snippets: tuple[Snippet, ...], analysis=None
) -> tuple[Match, ...]:
    """Recognize whole algorithms before fragments; current forms supersede history."""
    analysis = analysis or Analysis(syntax)

    def keys(node):
        yield type(node)
        value = (
            node.value
            if isinstance(node, (ast.Expr, ast.Assign, ast.AnnAssign))
            else node
        )
        if isinstance(value, ast.Call):
            function = value.func
            if isinstance(function, ast.Attribute) and not getattr(
                function, "template_names", None
            ):
                yield (type(node), "method", function.attr)
            elif (
                isinstance(function, ast.Name)
                and not getattr(function, "template_parameter", None)
                and not getattr(function, "template_names", None)
            ):
                yield (type(node), "call", function.id)

    expressions, statements = {}, {}
    all_expressions = []
    for node, span in syntax.spans.items():
        if isinstance(node, ast.expr):
            item = (span, node)
            all_expressions.append(item)
            for key in keys(node):
                expressions.setdefault(key, []).append(item)
    for suite in syntax.suites:
        for index, node in enumerate(suite.statements):
            for key in keys(node):
                statements.setdefault(key, []).append((suite, index))
    candidates = []
    for snippet in snippets:
        if snippet.expression:
            regions = (
                all_expressions
                if getattr(snippet.body, "template_parameter", None)
                else expressions.get(tuple(keys(snippet.body))[-1], ())
            )
        else:
            count = len(snippet.body)
            regions = (
                (
                    Span(
                        syntax.spans[suite.statements[index]].start,
                        syntax.spans[suite.statements[index + count - 1]].end,
                    ),
                    tuple(suite.statements[index : index + count]),
                )
                for suite, index in statements.get(tuple(keys(snippet.body[0]))[-1], ())
                if index + count <= len(suite.statements)
            )
        for span, candidate in regions:
            result = _match(snippet, candidate)
            if result is not None:
                bindings = result[0]
                compatible = all(
                    (actual := analysis.type_of(bindings[p.name])) is None
                    or p.annotation is None
                    or actual == value_type(p.annotation)
                    for p in snippet.parameters
                    if p.name in bindings
                )
                if compatible:
                    candidates.append(Match(snippet, span, *result))
    current = {
        (m.snippet.identity, m.span) for m in candidates if not m.snippet.historical
    }
    candidates = [
        m
        for m in candidates
        if not m.snippet.historical or (m.snippet.identity, m.span) not in current
    ]
    candidates.sort(
        key=lambda m: (
            -(m.span.end - m.span.start),
            -m.snippet.specificity,
            m.snippet.historical,
            m.snippet.identity,
        )
    )
    # A prefix-maximum Fenwick index rejects overlapping candidates in O(log n).
    # Accepted intervals are never removed; their start/end coordinates suffice.
    starts = sorted({match.span.start for match in candidates})
    ends = [0] * (len(starts) + 1)
    result = []
    for match in candidates:
        index = bisect_left(starts, match.span.end)
        latest = 0
        while index:
            latest = max(latest, ends[index])
            index -= index & -index
        if latest > match.span.start:
            continue
        result.append(match)
        index = bisect_left(starts, match.span.start) + 1
        while index < len(ends):
            ends[index] = max(ends[index], match.span.end)
            index += index & -index
    return tuple(sorted(result, key=lambda match: match.span.start))


def snippet_groups(snippets):
    """Current templates grouped by their collection/module identity, in order."""
    groups = {}
    for snippet in snippets:
        if not snippet.historical:
            group = snippet.identity.rsplit("/", 1)[0]
            groups.setdefault(group, []).append(snippet)
    return groups


def upgrade(
    match: Match, current: Snippet, occupied: set[str] | None = None
) -> Expansion:
    if match.snippet.identity != current.identity:
        raise ValueError("Upgrade requires the same snippet identity")
    old = {p.name: p for p in match.snippet.parameters}
    new = {p.name: p for p in current.parameters}
    if not old.keys() <= new.keys() or any(
        new[name].default is None for name in new.keys() - old.keys()
    ):
        raise ValueError("Incompatible snippet signature")
    if match.snippet.version.split(".")[0] != current.version.split(".")[0]:
        raise ValueError("Major-version upgrades require manual editing")
    if match.snippet.expression != current.expression:
        raise ValueError("Cannot change statement/expression kind automatically")
    return instantiate(current, match.bindings, occupied, local_names=match.locals)
