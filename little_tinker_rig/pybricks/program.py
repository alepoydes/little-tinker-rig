"""Immutable local program snapshots, including imported project modules."""

import ast
from pathlib import Path
from tempfile import TemporaryDirectory

from little_tinker_rig.core.placeholders import unfinished_inputs
from little_tinker_rig.core.source_file import decode_source, utf8_source


class Program:
    def __init__(self, path, sources=None):
        self.path = Path(path).resolve()
        overrides = {Path(p).resolve(): text for p, text in (sources or {}).items()}
        self.directory = TemporaryDirectory(prefix="little-tinker-rig-program-")
        self.entry = Path(self.directory.name) / self.path.name
        self.sources = {}
        root = self.path.parent
        pending, seen = [self.path], set()
        try:
            while pending:
                file = pending.pop().resolve()
                if file in seen or not file.is_relative_to(root):
                    continue
                if file != self.path and file not in overrides and not file.is_file():
                    continue
                seen.add(file)
                source = (
                    overrides[file]
                    if file in overrides
                    else decode_source(file.read_bytes())[0]
                )
                source = utf8_source(source)
                raw = source.encode("utf-8")
                tree = ast.parse(source)
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
                        names = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        if node.level:
                            base = file.parent
                            for _ in range(node.level - 1):
                                base = base.parent
                        names = [node.module or ""] + [
                            ".".join(filter(None, (node.module, alias.name)))
                            for alias in node.names
                        ]
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
