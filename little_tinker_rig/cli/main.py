"""The CLI prints transformations unless --write is explicitly requested."""

import argparse
import ast
import json
import sys
from dataclasses import asdict
from pathlib import Path

from little_tinker_rig.core import edit
from little_tinker_rig.core.presentation import regions
from little_tinker_rig.core.session import Session


def _position(value: str) -> tuple[int, int]:
    try:
        line, _, column = value.partition(":")
        return int(line), int(column or "0")
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Use LINE:COLUMN (lines from 1, columns from 0)"
        ) from error


def _bindings(values: list[str]) -> dict[str, str]:
    result = {}
    for value in values:
        name, separator, expression = value.partition("=")
        if not separator:
            raise ValueError("Parameter must be NAME=EXPRESSION")
        result[name] = expression
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="little-tinker-rig", description="Structural editing of ordinary Python"
    )
    result.add_argument(
        "--collection",
        type=Path,
        action="append",
        default=[],
        help="Additional snippet collection directory",
    )
    commands = result.add_subparsers(dest="command", required=True)
    version = commands.add_parser(
        "next-block-version",
        help="Archive saved definitions and start a new collection version",
    )
    version.add_argument("directory", type=Path)
    version.add_argument("version", help="New MAJOR.MINOR.PATCH version")
    migration = commands.add_parser(
        "migrate-blocks", help="Convert a legacy block collection to source decorators"
    )
    migration.add_argument("directory", type=Path)
    migration.add_argument(
        "--write",
        action="store_true",
        help="Apply the validated migration; otherwise print its diff",
    )
    for name in (
        "inspect",
        "diagnose",
        "snippets",
        "format",
        "delete",
        "replace",
        "move",
        "insert",
        "upgrade",
        "scratch",
        "restore",
        "qt",
        "tui",
        "run",
        "controller",
    ):
        command = commands.add_parser(name)
        command.add_argument("file", type=Path)
        if name in {
            "delete",
            "replace",
            "move",
            "insert",
            "upgrade",
            "scratch",
            "restore",
        }:
            command.add_argument("--at", type=_position, default=(1, 0))
        if name in {
            "format",
            "delete",
            "replace",
            "move",
            "insert",
            "upgrade",
            "scratch",
            "restore",
            "controller",
        }:
            command.add_argument(
                "--write",
                action="store_true",
                help="Save result and Scratch atomically per file",
            )
        if name == "replace":
            command.add_argument("text", help="Replacement Python")
        if name == "move":
            command.add_argument("--to", type=_position, required=True)
        if name == "insert":
            command.add_argument("snippet")
            command.add_argument("--param", action="append", default=[])
        if name == "restore":
            command.add_argument("index", type=int)
        if name == "run":
            command.add_argument("--name", help="Bluetooth hub name")
            command.add_argument(
                "--transport", choices=("ble", "usb", "virtual"), default="ble"
            )
            command.add_argument(
                "--model",
                choices=("inventor", "boost", "technic"),
                default="inventor",
                help="Virtual hub model",
            )
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "next-block-version":
            from little_tinker_rig.core.versions import next_version

            next_version(arguments.directory, arguments.version)
            print(f"Started collection version {arguments.version}")
            return 0
        if arguments.command == "migrate-blocks":
            from difflib import unified_diff

            from little_tinker_rig.core.migration import migrate_collection
            from little_tinker_rig.core.project import atomic_write

            changes = migrate_collection(arguments.directory)
            originals = {
                name: (arguments.directory / name).read_text(encoding="utf-8")
                for name in changes
            }
            if arguments.write:
                written = []
                try:
                    for name, source in changes.items():
                        if source != originals[name]:
                            atomic_write(arguments.directory / name, source)
                            written.append(name)
                except OSError:
                    for name in reversed(written):
                        atomic_write(arguments.directory / name, originals[name])
                    raise
            else:
                for name, source in changes.items():
                    print(
                        "".join(
                            unified_diff(
                                originals[name].splitlines(keepends=True),
                                source.splitlines(keepends=True),
                                fromfile=name,
                                tofile=name,
                            )
                        ),
                        end="",
                    )
            return 0
        if arguments.command == "controller":
            from little_tinker_rig.core.project import atomic_write

            source = (
                Path(__file__).parents[1] / "pybricks" / "hub_controller.py"
            ).read_text(encoding="utf-8")
            if arguments.write:
                atomic_write(arguments.file, source)
            else:
                print(source, end="")
            return 0
        if arguments.command in {"qt", "tui"}:
            if arguments.command == "qt":
                from little_tinker_rig.qt.app import launch
            else:
                from little_tinker_rig.tui.app import launch
            return launch(arguments.file, tuple(arguments.collection))
        if arguments.command == "run":
            import asyncio

            from little_tinker_rig.pybricks.connection import run_file

            asyncio.run(
                run_file(
                    arguments.file, arguments.name, arguments.transport, arguments.model
                )
            )
            return 0
        session = Session(arguments.file, tuple(arguments.collection))
        editor, document = session.editor, session.document
        if hasattr(arguments, "at"):
            editor.select(document.syntax.offset(*arguments.at))
        command = arguments.command
        if command == "inspect":
            print(
                json.dumps(
                    {
                        "source": document.state.source,
                        "regions": [
                            asdict(r) for r in regions(document.syntax, session.matches)
                        ],
                        "snippets": [
                            {
                                "id": m.snippet.identity,
                                "version": m.snippet.version,
                                "historical": m.snippet.historical,
                                "span": asdict(m.span),
                                "bindings": {
                                    k: ast.unparse(v) for k, v in m.bindings.items()
                                },
                            }
                            for m in session.matches
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if command == "diagnose":
            diagnostics = session.analysis.diagnostics()
            for diagnostic in diagnostics:
                line, column = document.syntax.position(diagnostic.span.start)
                print(f"{arguments.file}:{line}:{column}: {diagnostic.message}")
            return int(bool(diagnostics))
        if command == "snippets":
            for snippet in session.snippets:
                if not snippet.historical:
                    signature = ", ".join(
                        p.name + ("=" + p.default if p.default is not None else "")
                        for p in snippet.parameters
                    )
                    print(
                        f"{snippet.identity}({signature}) — {snippet.help.splitlines()[0] if snippet.help else ''}"
                    )
            return 0
        if command == "replace":
            session.edit_python(arguments.text)
        elif command == "delete":
            editor.delete()
        elif command == "scratch":
            session.to_scratch()
        elif command == "restore":
            session.restore_scratch(arguments.index)
        elif command == "insert":
            snippet = next(
                (
                    s
                    for s in session.snippets
                    if s.identity == arguments.snippet and not s.historical
                ),
                None,
            )
            if snippet is None:
                raise ValueError(f"Unknown snippet: {arguments.snippet}")
            session.insert_snippet(snippet, _bindings(arguments.param))
        elif command == "upgrade":
            session.upgrade_selected()
        elif command == "move":
            destination = document.syntax.offset(*arguments.to)
            moving = session.begin_move()
            candidates = moving.targets
            target = min(
                candidates,
                key=lambda t: abs(
                    edit.target_position(document.syntax, t)[0] - destination
                ),
            )
            editor.commit(edit.move(document.syntax, moving.node, target))
        if arguments.write:
            session.project.save()
        else:
            print(document.state.source, end="")
            if command in {"scratch", "restore"}:
                print(
                    json.dumps({"scratch": document.state.scratch}, ensure_ascii=False),
                    file=sys.stderr,
                )
        return 0
    except (ValueError, SyntaxError, OSError, ImportError) as error:
        print(f"little-tinker-rig: {error}", file=sys.stderr)
        return 2
