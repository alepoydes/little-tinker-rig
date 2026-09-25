"""Bundle help and examples from their authoritative repository directories."""

from pathlib import Path
from shutil import copytree, rmtree

from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        for source, name in (("doc", "help_pages"), ("examples", "examples")):
            destination = Path(self.build_lib) / "pyblocks" / name
            if destination.exists():
                rmtree(destination)
            copytree(
                Path(__file__).parent / source,
                destination,
                ignore=lambda directory, names: [
                    n
                    for n in names
                    if n == "__pycache__"
                    or n.startswith(".")
                    or n.endswith((".pyc", ".pyblocks.json"))
                ],
            )
