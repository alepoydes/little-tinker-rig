"""Static Python-function templates: binding, hygienic expansion and recognition."""

import ast
import copy
import keyword
import tomllib
from bisect import bisect_left
from dataclasses import dataclass, replace
from dataclasses import field as dataclass_field
from functools import cached_property
from pathlib import Path

from pyblocks.i18n import N_

from .analysis import Analysis, Scopes, annotation_text, identifiers
from .block_metadata import LEVELS, decorator, metadata
from .helpers import helper_functions, helper_section, referenced_helpers
from .syntax import Span, Syntax
from .types import Compatibility, canonical, compatibility, numeric_literal


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
    level: str = "intermediate"
    source_path: Path | None = None
    mode: str = "legacy"
    icon: str | None = None
    color: str | None = None
    names: dict[str, str] = dataclass_field(default_factory=dict)
    helpers: tuple[ast.FunctionDef, ...] = ()
    group_help: str = ""
    context: str | None = None

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
    helpers: tuple[str, ...] = ()


@dataclass(frozen=True)
class Match:
    snippet: Snippet
    span: Span
    bindings: dict[str, ast.expr]
    locals: dict[str, str]
    occurrences: dict[str, tuple[ast.expr, ...]]
    declarations: tuple[tuple[ast.Name, str], ...] = ()
    named: dict[str, tuple[ast.AST, ...]] = dataclass_field(default_factory=dict)


def load_module(
    source: str,
    collection: str,
    version: str,
    *,
    historical: bool = False,
    legacy: bool | None = None,
) -> tuple[Snippet, ...]:
    """Read definitions without importing or evaluating any template code."""
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len({function.name for function in functions}) != len(functions):
        raise ValueError("Duplicate function name in block module")
    if legacy is None:
        legacy = not any(decorator(function) for function in functions)
    module_imports = tuple(
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    )
    group_help = ast.get_docstring(tree) or ""
    scopes = Scopes(tree)
    if not legacy:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.Import, ast.ImportFrom)):
                continue
            if node is tree.body[0] and group_help:
                continue
            raise ValueError(
                "Block modules contain only a docstring, imports and functions"
            )
        for function in functions:
            if function.decorator_list and metadata(function) is None:
                raise ValueError(f"{function.name}: unsupported helper decorator")
    result = []
    for original in functions:
        options = metadata(original)
        if options is None and not legacy:
            continue
        copies = {}
        function = copy.deepcopy(original, copies)
        if (
            (function.decorator_list and options is None)
            or function.args.vararg
            or function.args.kwarg
        ):
            raise ValueError(
                f"{function.name}: unsupported decorator or variadic block parameters"
            )
        mode = options["mode"] if options else "legacy"
        args = function.args
        positional = [*args.posonlyargs, *args.args]
        defaults = [None] * (len(positional) - len(args.defaults)) + args.defaults
        parameters = tuple(
            Parameter(
                arg.arg,
                ast.unparse(default) if default is not None else None,
                (
                    canonical(annotation_text(arg.annotation))
                    if options
                    else annotation_text(arg.annotation)
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
        result_type = annotation_text(function.returns)
        kind = (
            options.get("kind")
            if options
            else ("statement" if result_type == "statement" else None)
        )
        context = (
            options.get("context")
            if options
            else ("loop" if result_type == "loop" else None)
        )
        if options:
            result_type = canonical(result_type)
        if context == "loop":
            if len(body) != 1 or not isinstance(body[0], ast.While) or body[0].orelse:
                raise ValueError(
                    f"{function.name}: a loop template needs one while wrapper"
                )
            body = body[0].body
        if not body:
            raise ValueError(f"{function.name}: empty template")
        for node in ast.walk(ast.Module(body=body, type_ignores=[])):
            if mode != "function" and (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == function.name
            ):
                raise ValueError(f"{function.name}: recursive template")
            if mode != "function" and isinstance(node, (ast.Global, ast.Nonlocal)):
                raise ValueError(
                    f"{function.name}: global/nonlocal declarations cannot be hygienic"
                )
            if (
                mode != "function"
                and isinstance(node, ast.ClassDef)
                and not (
                    len(body) == 1
                    and node is body[0]
                    and not node.decorator_list
                    and not node.keywords
                    and len(node.body) == 1
                    and isinstance(node.body[0], ast.Pass)
                )
            ):
                raise ValueError(
                    f"{function.name}: classes belong in an ordinary helper module, not a template"
                )
            if options and isinstance(node, ast.AnnAssign):
                canonical(annotation_text(node.annotation))
        helpers = ()
        if mode == "function":
            helper_names, helpers = helper_functions(tree, (function.name,), collection)
            call = ast.Call(
                func=ast.Name(id=helper_names[function.name], ctx=ast.Load()),
                args=[ast.Name(id=arg.arg, ctx=ast.Load()) for arg in positional],
                keywords=[
                    ast.keyword(arg=arg.arg, value=ast.Name(id=arg.arg, ctx=ast.Load()))
                    for arg in args.kwonlyargs
                ],
            )
            for node in [*call.args, *(keyword.value for keyword in call.keywords)]:
                node.template_parameter = node.id
            outer = scopes.defined_scopes[original]
            has_result = any(
                isinstance(node, ast.Return)
                and node.value is not None
                and not (
                    isinstance(node.value, ast.Constant) and node.value.value is None
                )
                and scopes.scopes[node] is outer
                for node in ast.walk(original)
            )
            expression = kind == "expression" or (kind is None and has_result)
            template = call if expression else (ast.Expr(value=call),)
            for node in (template,) if expression else template:
                ast.fix_missing_locations(node)
            local_names, names = {}, {}
            imports = module_imports
        else:
            if options:
                # Resolve helper references on the original tree, before copying
                # and hygienically annotating the inline body.
                references = referenced_helpers(scopes, original)
                if references:
                    helper_names, helpers = helper_functions(
                        tree, {node.id for node in references}, collection
                    )
                    for node in references:
                        copies[id(node)].id = helper_names[node.id]
            local_names, names = _template_names(
                function, body, imports, parameters, options["names"] if options else ()
            )
            template = (
                body[0].value
                if len(body) == 1
                and isinstance(body[0], ast.Return)
                and kind != "statement"
                else tuple(body)
            )
            if kind == "expression" and not isinstance(template, ast.expr):
                raise ValueError(
                    f"{function.name}: an inline expression needs one return"
                )
            if options:
                imports = (*module_imports, *imports)
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
                result_type,
                level=options["level"] if options else "intermediate",
                mode=mode,
                icon=options["icon"] if options else None,
                color=options["color"] if options else None,
                names=names,
                helpers=helpers,
                group_help=group_help,
                context=context,
            )
        )
    return tuple(result)


def function_snippets(syntax):
    """Calls to module-level user functions, rebuilt from the current document."""

    def produces_value(node):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            return False
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            return True
        if isinstance(node, ast.Return):
            return node.value is not None and not (
                isinstance(node.value, ast.Constant) and node.value.value is None
            )
        return any(produces_value(child) for child in ast.iter_child_nodes(node))

    result = []
    section = helper_section(syntax.source)
    for node in syntax.tree.body:
        if (
            not isinstance(node, ast.FunctionDef)
            or section
            and section.contains(syntax.spans[node].start)
        ):
            continue
        args = node.args
        positional = (args.posonlyargs + args.args)[
            : len(args.posonlyargs) + len(args.args) - len(args.defaults)
        ]
        required_keywords = [
            arg
            for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True)
            if default is None
        ]
        parameters = tuple(
            Parameter(arg.arg, "None", annotation_text(arg.annotation))
            for arg in positional + required_keywords
        )

        def value(arg):
            name = ast.Name(id=arg.arg, ctx=ast.Load())
            name.template_parameter = arg.arg
            return name

        call = ast.Call(
            func=ast.Name(id=node.name, ctx=ast.Load()),
            args=[value(arg) for arg in positional],
            keywords=[
                ast.keyword(arg=arg.arg, value=value(arg)) for arg in required_keywords
            ],
        )
        call = ast.fix_missing_locations(call)
        result_type = annotation_text(node.returns)
        expression = bool(node.decorator_list) or (
            result_type != "None"
            if result_type
            else any(produces_value(n) for n in node.body)
        )
        result.append(
            Snippet(
                f"document/functions/{node.name}",
                "1",
                parameters,
                (
                    call
                    if expression
                    else (ast.fix_missing_locations(ast.Expr(value=call)),)
                ),
                (),
                ast.get_docstring(node) or node.name,
                {},
                result_type=result_type,
                level="intermediate",
                icon="ƒ",
                color="definition",
                group_help=N_("My functions"),
            )
        )
    return tuple(result)


def _template_names(function, body, imports, parameters, editable=()):
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
    declarations = {}

    def path(owner, name):
        parts = [name]
        while owner is not outer:
            if not isinstance(owner.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return None
            parts.insert(0, owner.node.name)
            owner = owner.parent
        return ".".join(parts)

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
            if isinstance(node.ctx, ast.Store):
                declarations[name] = name
        elif (
            owner is not None
            and owner is not scopes.root
            and not (owner is outer and name in dependencies)
        ):
            key = name if owner is outer else f"{numbers[id(owner)]}:{name}"
            node.template_names = {field: key}
            result[key] = name
            if not isinstance(node, ast.Name) or isinstance(node.ctx, ast.Store):
                declaration = path(owner, name)
                if declaration is not None:
                    declarations[declaration] = key
    unknown = set(editable) - declarations.keys()
    if unknown:
        raise ValueError(
            f"{function.name}: unknown editable declarations: {', '.join(sorted(unknown))}"
        )
    return result, {name: declarations[name] for name in editable}


def load_collection(
    directory: Path, *, overrides: dict[str, str] | None = None
) -> tuple[Snippet, ...]:
    """Load static templates, optionally validating unsaved relative file contents."""
    directory = directory.resolve()
    overrides = overrides or {}
    for name in overrides:
        if not (directory / name).resolve().is_relative_to(directory):
            raise ValueError("Collection overrides must stay inside the collection")

    def read(path):
        name = path.relative_to(directory).as_posix()
        return (
            overrides[name] if name in overrides else path.read_text(encoding="utf-8")
        )

    manifest = tomllib.loads(read(directory / "collection.toml"))
    identity, version = manifest["collection"]["id"], manifest["collection"]["version"]
    format_version = manifest["collection"].get("format", 1)
    if format_version not in (1, 2):
        raise ValueError("Unsupported block collection format")
    if format_version == 2 and manifest.get("levels"):
        raise ValueError(
            "Block difficulty belongs in source decorators, not collection.toml"
        )
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
    paths = set(directory.rglob("*.py")) | {
        directory / name for name in overrides if name.endswith(".py")
    }
    for path in sorted(paths):
        # Unregistered/staged history is never an active module.
        if any(
            part.startswith(".") or part in {"history", "__pycache__"}
            for part in path.relative_to(directory).parts
        ):
            continue
        if path.name == "__init__.py" or any(
            path.resolve().is_relative_to(root) for root, _ in histories
        ):
            continue
        module = path.relative_to(directory).with_suffix("").as_posix()
        result.extend(
            replace(s, source_path=path)
            for s in load_module(
                read(path),
                f"{identity}/{module}",
                version,
                legacy=False if format_version == 2 else None,
            )
        )
    for root, historical_version in histories:
        for path in sorted(root.rglob("*.py")):
            module = path.relative_to(root).with_suffix("").as_posix()
            result.extend(
                replace(s, source_path=path)
                for s in load_module(
                    read(path),
                    f"{identity}/{module}",
                    historical_version,
                    historical=True,
                )
            )
    identities = [(snippet.identity, snippet.version) for snippet in result]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate snippet identity and version")
    # Older third-party collections keep loading after the level rename.
    levels = {
        name: "intermediate" if level == "standard" else level
        for name, level in manifest.get("levels", {}).items()
    }
    names = {s.identity.removeprefix(identity + "/") for s in result}
    if levels.keys() - names or any(level not in LEVELS for level in levels.values()):
        raise ValueError("Unknown block or difficulty level in collection.toml")
    if any(
        s.mode != "legacy" and s.identity.removeprefix(identity + "/") in levels
        for s in result
    ):
        raise ValueError(
            "Block difficulty belongs in source decorators, not collection.toml"
        )
    return tuple(
        replace(s, level=levels.get(s.identity.removeprefix(identity + "/"), s.level))
        for s in result
    )


def builtin_snippets() -> tuple[Snippet, ...]:
    root = Path(__file__).parents[1] / "snippets"
    return tuple(
        snippet
        # Basic language actions precede optional robotics on the first screen.
        for path in sorted(root.iterdir(), key=lambda p: (p.name != "python", p.name))
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
    parameter_names = {p.name for p in snippet.parameters}
    extra = bindings.keys() - parameter_names - snippet.names.keys()
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
    reserved = set(used)
    for name, key in snippet.names.items():
        if name in parameter_names:
            expression = values[name]
            if not isinstance(expression, ast.Name):
                raise ValueError(f"{name} must be a declared name")
            if expression.id in (occupied or ()):
                if name in bindings:
                    raise ValueError(
                        f"Declared name {expression.id!r} conflicts with an existing name"
                    )
                candidate, suffix = expression.id, 2
                while candidate in used:
                    candidate, suffix = f"{expression.id}_{suffix}", suffix + 1
                values[name] = ast.Name(id=candidate, ctx=ast.Load())
                used.add(candidate)
                reserved.add(candidate)
            continue
        if name in bindings:
            expression = bindings[name]
            candidate = (
                ast.unparse(expression)
                if isinstance(expression, ast.AST)
                else expression
            )
            if not candidate.isidentifier() or keyword.iskeyword(candidate):
                raise ValueError(f"{name} must be a declared name")
            if candidate in reserved:
                raise ValueError(
                    f"Declared name {candidate!r} conflicts with an existing name"
                )
            renamed[key] = candidate
            reserved.add(candidate)
    used.update(renamed.values())
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
        ast.unparse(tree),
        tuple(ast.unparse(node) for node in snippet.imports),
        tuple(ast.unparse(node) for node in snippet.helpers),
    )


def _match(snippet: Snippet, candidate):
    bindings, local_names = {}, {}
    occurrences = {}
    declarations = []
    named = {}
    editable = set(snippet.names.values())

    def equal(pattern, value) -> bool:
        parameter = getattr(pattern, "template_parameter", None)
        if parameter is not None:
            if not isinstance(value, ast.expr):
                return False
            if parameter in snippet.names and not isinstance(value, ast.Name):
                return False
            occurrences.setdefault(parameter, []).append(value)
            if (
                parameter in editable
                and isinstance(value, ast.Name)
                and isinstance(value.ctx, ast.Store)
            ):
                named.setdefault(parameter, []).append(value)
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
        if isinstance(pattern, ast.AnnAssign) and isinstance(value, ast.Assign):
            if (
                len(value.targets) != 1
                or not equal(pattern.target, value.targets[0])
                or not equal(pattern.value, value.value)
            ):
                return False
            if isinstance(value.targets[0], ast.Name):
                declarations.append(
                    (value.targets[0], annotation_text(pattern.annotation))
                )
            return True
        if type(pattern) is not type(value):
            return False
        if isinstance(pattern, ast.AST):
            for field, expected in ast.iter_fields(pattern):
                actual = getattr(value, field)
                key = getattr(pattern, "template_names", {}).get(field)
                if key is not None:
                    if key in editable and (
                        not isinstance(value, ast.Name)
                        or isinstance(value.ctx, ast.Store)
                    ):
                        named.setdefault(key, []).append(value)
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
            if isinstance(pattern, ast.AnnAssign) and isinstance(
                value.target, ast.Name
            ):
                declarations.append((value.target, annotation_text(pattern.annotation)))
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
        tuple(declarations),
        {key: tuple(nodes) for key, nodes in named.items()},
    )


def recognize(
    syntax: Syntax, snippets: tuple[Snippet, ...], analysis=None
) -> tuple[Match, ...]:
    """Recognize whole algorithms before fragments; current forms supersede history."""
    analysis = analysis or Analysis(syntax)
    helper_span = helper_section(syntax.source)

    def keys(node):
        kind = ast.Assign if isinstance(node, ast.AnnAssign) else type(node)
        yield kind
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
                yield (kind, "method", function.attr)
            elif (
                isinstance(function, ast.Name)
                and not getattr(function, "template_parameter", None)
                and not getattr(function, "template_names", None)
            ):
                yield (kind, "call", function.id)

    expressions, statements = {}, {}
    all_expressions = []
    # Type annotations are Python syntax, but are not executable expressions.
    annotations = {
        child
        for node in syntax.spans
        for annotation in (
            getattr(node, "annotation", None),
            getattr(node, "returns", None),
        )
        if annotation is not None
        for child in ast.walk(annotation)
    }
    for node, span in syntax.spans.items():
        if node in annotations or helper_span and helper_span.contains(span.start):
            continue
        if isinstance(node, ast.expr):
            item = (span, node)
            all_expressions.append(item)
            for key in keys(node):
                expressions.setdefault(key, []).append(item)
    for suite in syntax.suites:
        for index, node in enumerate(suite.statements):
            if helper_span and helper_span.contains(syntax.spans[node].start):
                continue
            for key in keys(node):
                statements.setdefault(key, []).append((suite, index))
    candidates = []
    mismatches = {}
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
                errors = sum(
                    compatibility(
                        p.annotation,
                        analysis.type_info(bindings[p.name]),
                        literal=numeric_literal(bindings[p.name]),
                    )
                    is Compatibility.INCOMPATIBLE
                    for p in snippet.parameters
                    if p.name in bindings
                    and p.name not in snippet.names
                    and not isinstance(
                        getattr(bindings[p.name], "ctx", None), ast.Store
                    )
                )
                match = Match(snippet, span, *result)
                candidates.append(match)
                mismatches[id(match)] = errors
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
            mismatches[id(m)],
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
    for members in groups.values():
        members.sort(key=lambda snippet: LEVELS.index(snippet.level))
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
    if any(
        canonical(old[name].annotation) != canonical(new[name].annotation)
        for name in old
    ):
        raise ValueError("Changed parameter types or units require manual editing")
    if (
        canonical(match.snippet.result_type) != canonical(current.result_type)
        or match.snippet.names != current.names
    ):
        raise ValueError(
            "Changed result or declaration contracts require manual editing"
        )
    return instantiate(current, match.bindings, occupied, local_names=match.locals)
