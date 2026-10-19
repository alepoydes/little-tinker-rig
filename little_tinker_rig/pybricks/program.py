"""Immutable local program snapshots, including imported project modules."""

import ast
from pathlib import Path
from tempfile import TemporaryDirectory

from little_tinker_rig.core.placeholders import unfinished_inputs
from little_tinker_rig.core.source_file import decode_source, utf8_source

# These imports cannot resolve to a sibling Python file on the target runtime.
INTRINSIC_IMPORTS = frozenset({"__future__", "sys"})


def _literal_exports(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _literal_exports(node.left), _literal_exports(node.right)
        return (*left, *right) if left is not None and right is not None else None
    try:
        values = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None
    if isinstance(values, (list, tuple, set)) and all(
        isinstance(name, str) and name.isidentifier() for name in values
    ):
        return tuple(values)
    return None


def _target_names(target):
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_target_names(item) for item in target.elts))
    return set()


def _literal_value(node):
    try:
        ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return False
    return True


def _package_exports_and_bindings(tree):
    """Resolve static exports and names not requiring a sibling module."""
    exports = None
    bound = set()
    declared = set()
    has_all = False
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(statement.name)
            declared.add(statement.name)
        elif isinstance(statement, ast.Import):
            names = {
                alias.asname or alias.name.split(".")[0] for alias in statement.names
            }
            bound.update(names)
            declared.update(names)
            has_all |= "__all__" in names
        elif isinstance(statement, ast.ImportFrom):
            names = {
                alias.asname or alias.name
                for alias in statement.names
                if alias.name != "*"
            }
            bound.update(names)
            declared.update(names)
            has_all |= "__all__" in names
        elif isinstance(statement, ast.Assign):
            targets = set().union(
                *(_target_names(target) for target in statement.targets)
            )
            declared.update(targets)
            if _literal_value(statement.value):
                bound.update(targets)
            else:
                bound.difference_update(targets)
            if "__all__" in targets:
                has_all = True
                exports = _literal_exports(statement.value)
        elif isinstance(statement, ast.AnnAssign):
            if statement.value is not None:
                targets = _target_names(statement.target)
                declared.update(targets)
                if _literal_value(statement.value):
                    bound.update(targets)
                else:
                    bound.difference_update(targets)
                if "__all__" in targets:
                    has_all = True
                    exports = _literal_exports(statement.value)
        elif isinstance(statement, ast.AugAssign):
            targets = _target_names(statement.target)
            declared.update(targets)
            bound.difference_update(targets)
            if "__all__" in targets:
                has_all = True
                added = _literal_exports(statement.value)
                exports = (
                    (*exports, *added)
                    if isinstance(statement.op, ast.Add)
                    and exports is not None
                    and added is not None
                    else None
                )
        elif isinstance(statement, ast.Delete):
            for target in statement.targets:
                names = _target_names(target)
                bound.difference_update(names)
                declared.difference_update(names)
                if "__all__" in names:
                    has_all = False
                    exports = None
        elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "__all__"
            ):
                has_all = True
                if call.func.attr == "append" and len(call.args) == 1:
                    try:
                        name = ast.literal_eval(call.args[0])
                    except (ValueError, TypeError, SyntaxError):
                        name = None
                    added = (
                        (name,)
                        if isinstance(name, str) and name.isidentifier()
                        else None
                    )
                elif call.func.attr == "extend" and len(call.args) == 1:
                    added = _literal_exports(call.args[0])
                else:
                    added = None
                exports = (
                    (*exports, *added)
                    if exports is not None and added is not None
                    else None
                )
    candidates = (
        exports or ()
        if has_all
        else tuple(sorted(name for name in declared if not name.startswith("_")))
    )
    return candidates, bound


class Program:
    def __init__(self, path, sources=None):
        self.path = Path(path).resolve()
        overrides = {Path(p).resolve(): text for p, text in (sources or {}).items()}
        self.directory = TemporaryDirectory(prefix="little-tinker-rig-program-")
        self.entry = Path(self.directory.name) / self.path.name
        self.sources = {}
        root = self.path.parent
        pending, seen = [self.path], set()
        parsed = {}
        package_details = {}

        def source_tree(file):
            file = file.resolve()
            if file not in parsed:
                source = (
                    overrides[file]
                    if file in overrides
                    else decode_source(file.read_bytes())[0]
                )
                source = utf8_source(source)
                parsed[file] = source, ast.parse(source, filename=str(file))
            return parsed[file]

        try:
            while pending:
                file = pending.pop().resolve()
                if file in seen or not file.is_relative_to(root):
                    continue
                if file != self.path and file not in overrides and not file.is_file():
                    continue
                seen.add(file)
                source, tree = source_tree(file)
                raw = source.encode("utf-8")
                for node in unfinished_inputs(tree):
                    from little_tinker_rig.i18n import tr

                    raise ValueError(
                        f"{file.name}:{node.lineno}: "
                        + tr("Fill this input before running the program")
                    )
                target = Path(self.directory.name) / file.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                self.sources[file] = source
                for node in ast.walk(tree):
                    names, base = [], root
                    if isinstance(node, ast.Import):
                        names = [
                            alias.name
                            for alias in node.names
                            if alias.name.split(".", 1)[0] not in INTRINSIC_IMPORTS
                        ]
                    elif isinstance(node, ast.ImportFrom):
                        if (
                            not node.level
                            and node.module
                            and node.module.split(".", 1)[0] in INTRINSIC_IMPORTS
                        ):
                            continue
                        if node.level:
                            base = file.parent
                            for _ in range(node.level - 1):
                                base = base.parent
                        module = base.joinpath(*(node.module or "").split("."))
                        package = (module / "__init__.py").resolve()
                        exports, bound = (), set()
                        if package.is_relative_to(root) and (
                            package in overrides or package.is_file()
                        ):
                            if package not in package_details:
                                package_details[package] = (
                                    _package_exports_and_bindings(
                                        source_tree(package)[1]
                                    )
                                )
                            exports, bound = package_details[package]
                        names = [node.module or ""]
                        for alias in node.names:
                            candidates = exports if alias.name == "*" else (alias.name,)
                            names.extend(
                                ".".join(filter(None, (node.module, name)))
                                for name in candidates
                                if name not in bound
                            )
                    if names:
                        pending.extend(
                            parent / "__init__.py"
                            for parent in (base, *base.parents)
                            if parent != root and parent.is_relative_to(root)
                        )
                    for name in names:
                        module = base
                        for component in filter(None, name.split(".")):
                            module = module / component
                            package = module / "__init__.py"
                            plain = module.with_suffix(".py")
                            # A regular package wins over a same-named module;
                            # a module cannot contain further imported modules.
                            if package.resolve() in overrides or package.is_file():
                                pending.append(package)
                            elif plain.resolve() in overrides or plain.is_file():
                                pending.append(plain)
                                break
                            elif not module.is_dir() and not any(
                                path.is_relative_to(module) for path in overrides
                            ):
                                break
        except BaseException:
            self.cleanup()
            raise

    def cleanup(self):
        self.directory.cleanup()

    def original_path(self, filename):
        if filename == "__main__":
            return self.path
        path = Path(filename)
        if path in self.sources:
            return path
        candidates = [
            original
            for original in self.sources
            if path == original.relative_to(self.path.parent)
            or path
            == Path(self.directory.name) / original.relative_to(self.path.parent)
        ]
        # Ambiguous module basenames must never highlight an unrelated file.
        return candidates[0] if len(candidates) == 1 else None
