"""Immutable local program snapshots, including imported project modules."""

import ast
import io
import tokenize
from pathlib import Path
from tempfile import TemporaryDirectory


class Program:
    def __init__(self, path):
        self.path = Path(path).resolve()
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
                if file != self.path and not file.is_file():
                    continue
                seen.add(file)
                raw = file.read_bytes()
                encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
                source = raw.decode(encoding)
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and node.value is Ellipsis:
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
                    for name in names:
                        module = base.joinpath(*name.split("."))
                        pending.extend(
                            (module.with_suffix(".py"), module / "__init__.py")
                        )
                        pending.extend(
                            parent / "__init__.py"
                            for parent in module.parents
                            if parent.is_relative_to(root)
                        )
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
