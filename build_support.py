"""Package the repository's Markdown help without keeping a second source copy."""

from pathlib import Path
from shutil import copytree

from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        copytree(
            Path(__file__).parent / "doc",
            Path(self.build_lib) / "pyblocks" / "help_pages",
            dirs_exist_ok=True,
        )
