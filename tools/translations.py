"""Update/check/compile gettext catalogs with the project's uv development group."""

import argparse
import ast
import io
import json
from pathlib import Path
from string import Formatter

from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

from little_tinker_rig.core.block_metadata import decorator

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "little_tinker_rig/locale"


def messages():
    catalog = Catalog(project="LittleTinker Rig", version="0.1", charset="utf-8")
    for path in sorted((ROOT / "little_tinker_rig").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {
            child: node
            for node in ast.walk(tree)
            for child in ast.iter_child_nodes(node)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            parent = parents.get(node)
            explicit = (
                isinstance(parent, ast.Call)
                and isinstance(parent.func, ast.Name)
                and parent.func.id in {"tr", "N_"}
                and parent.args[0] is node
            )
            if explicit:
                catalog.add(
                    node.value, locations=[(str(path.relative_to(ROOT)), node.lineno)]
                )
    for path in sorted((ROOT / "little_tinker_rig/snippets").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and decorator(node)
        ]
        if not functions:
            continue
        if text := ast.get_docstring(tree):
            catalog.add(text, locations=[(str(path.relative_to(ROOT)), 1)])
        for node in functions:
            if text := ast.get_docstring(node):
                catalog.add(
                    text, locations=[(str(path.relative_to(ROOT)), node.lineno)]
                )
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("update", "check", "compile"))
    action = parser.parse_args().action
    template = messages()
    languages = json.loads((LOCALES / "languages.json").read_text(encoding="utf-8"))
    failures = []
    for code in languages:
        if code == "en":
            continue
        directory = LOCALES / code / "LC_MESSAGES"
        path = directory / "little_tinker_rig.po"
        if path.exists():
            with path.open("rb") as stream:
                catalog = read_po(stream, locale=code)
        else:
            catalog = Catalog(locale=code, project="LittleTinker Rig", version="0.1")
        if action == "update":
            catalog.update(template, no_fuzzy_matching=True)
            directory.mkdir(parents=True, exist_ok=True)
            with path.open("wb") as stream:
                write_po(stream, catalog, width=88, sort_output=True)
            print(path.relative_to(ROOT))
            continue
        missing = [
            message.id
            for message in template
            if message.id
            and (catalog.get(message.id) is None or not catalog.get(message.id).string)
        ]
        for message in missing:
            failures.append(f"{code}: missing {message!r}")
        invalid = []
        for message, errors in catalog.check():
            invalid.extend(f"{code}: {message.id!r}: {error}" for error in errors)
        for message in catalog:
            if not message.id:
                continue
            if "fuzzy" in message.flags:
                invalid.append(f"{code}: unreviewed translation {message.id!r}")
            if message.python_brace_format and message.string:

                def fields(text):
                    return {
                        (name, spec, conversion)
                        for _, name, spec, conversion in Formatter().parse(text)
                        if name is not None
                    }

                try:
                    if fields(message.id) != fields(message.string):
                        raise ValueError("format fields differ")
                except ValueError as error:
                    invalid.append(f"{code}: {message.id!r}: {error}")
        failures.extend(invalid)
        if not missing and not invalid:
            compiled = io.BytesIO()
            write_mo(compiled, catalog)
            binary = directory / "little_tinker_rig.mo"
            if action == "compile":
                binary.write_bytes(compiled.getvalue())
            elif not binary.exists() or binary.read_bytes() != compiled.getvalue():
                failures.append(f"{code}: recompile the MO catalog")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Translations {action}: OK")


if __name__ == "__main__":
    main()
