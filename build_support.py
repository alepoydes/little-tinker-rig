"""Bundle authored help, examples and lessons; downloaded parts stay in user storage."""

from pathlib import Path
from shutil import copytree, rmtree

from setuptools.command.build_py import build_py

LESSON_SUFFIXES = {".py", ".json", ".md", ".txt", ".ldr", ".mpd", ".png", ".svg"}


class BuildPy(build_py):
    def run(self):
        super().run()
        for source, name in (
            ("doc", "help_pages"),
            ("examples", "examples"),
            ("lessons", "lesson_data"),
        ):
            destination = Path(self.build_lib) / "little_tinker_rig" / name
            if destination.exists():
                rmtree(destination)
            copytree(
                Path(__file__).parent / source,
                destination,
                ignore=lambda directory, names, lesson=source == "lessons": [
                    n
                    for n in names
                    if n == "__pycache__"
                    or n.startswith(".")
                    or n.endswith((".pyc", ".ltr.json", ".pyblocks.json"))
                    or (
                        lesson
                        and (
                            n == "ldraw"
                            or (
                                Path(n).suffix not in LESSON_SUFFIXES
                                and not (Path(directory) / n).is_dir()
                            )
                        )
                    )
                ],
            )
