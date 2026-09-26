"""Audit a pinned Pybricks checkout and adapt its source without running it.

Usage: python tools/adapt_pybricks_examples.py UPSTREAM_DIRECTORY [--write]
The catalog hashes guard the input; this tool performs only explicit API and
call-spelling migrations. Manual adaptations have separate behavior tests.
"""

import argparse
import ast
import hashlib
import json
import tokenize
from pathlib import Path

from pyblocks.core import edit
from pyblocks.core.formatting import format_source
from pyblocks.core.helpers import manage_helpers
from pyblocks.core.snippets import builtin_snippets, instantiate
from pyblocks.core.syntax import Span, Syntax

EXAMPLES = Path(__file__).resolve().parents[1] / "examples/pybricks"
# Only leading keywords in signature order can become positional arguments.
# Never move values past other values, or materialize unspecified API defaults.
POSITIONAL = {
    "Motor": ("port", "positive_direction"),
    "DriveBase": ("left_motor", "right_motor"),
    "Color": ("h", "s", "v"),
    "run": ("speed",),
    "run_time": ("speed", "time"),
    "run_angle": ("speed", "rotation_angle"),
    "run_target": ("speed", "target_angle"),
    "run_until_stalled": ("speed",),
    "drive": ("speed", "turn_rate"),
    "orientation": ("up",),
    "icon": ("icon",),
    "on": ("color",),
    "beep": ("frequency", "duration"),
}
MANUAL_ADAPTATIONS = {
    "boost_17101_auto_builder.py",
    "inventor_51515_tricky.py",
    "spike_45678_cnc.py",
    "spike_45678_grabber.py",
    "spike_45678_kiki.py",
    "technic_42099_off_roader.py",
    "technic_42099_off_roader_remote.py",
    "technic_42109_xbox.py",
    "technic_42124_buggy.py",
}


def adapt(source, filename):
    if source.startswith("# pybricks blocks file:"):
        source = source.split("\n", 1)[1]
    syntax = Syntax(source)
    changes = []
    for node in ast.walk(syntax.tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "gelo":
                changes.append(
                    (
                        syntax.spans[node],
                        syntax.text(node).replace(
                            "from gelo", "from inventor_51515_gelo", 1
                        ),
                    )
                )
            elif node.module == "pybricks.geometry":
                changes.append(
                    (
                        syntax.spans[node],
                        syntax.text(node).replace(
                            "pybricks.geometry", "pybricks.parameters", 1
                        ),
                    )
                )
            elif node.module == "pybricks.experimental":
                assert [a.name for a in node.names] == ["getchar"]
                changes.append((syntax.spans[node], ""))
        elif isinstance(node, ast.Attribute):
            if (
                node.attr == "image"
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "display"
            ):
                changes.append(
                    (Span(syntax.spans[node].end - 5, syntax.spans[node].end), "icon")
                )
            elif (
                node.attr == "done"
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "control"
            ):
                changes.append(
                    (syntax.spans[node], syntax.text(node.value.value) + ".done")
                )
        elif isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            )
            if name == "image":
                name = "icon"
            position = len(node.args)
            for kw in node.keywords:
                actual = "icon" if kw.arg == "image" and name == "icon" else kw.arg
                signature = POSITIONAL.get(name, ())
                if position >= len(signature) or actual != signature[position]:
                    break
                changes.append(
                    (Span(syntax.spans[kw].start, syntax.spans[kw.value].start), "")
                )
                position += 1
    for token in syntax.tokens:
        if token.type == tokenize.NAME and token.string == "InventorHub":
            changes.append(
                (
                    Span(syntax.offset(*token.start), syntax.offset(*token.end)),
                    "PrimeHub",
                )
            )
    source = edit.patches(source, changes)
    # These are authored, ordinary helper functions from the block library.
    helper_blocks = []
    if filename == "inventor_51515_gelo.py":
        source = "from micropython import const\n" + source
    if filename == "technic_42160_audi_remote.py":
        # Upstream uses hub.system.shutdown() without constructing hub.
        source = source.replace(
            "import pybricks.hubs",
            "from pybricks.hubs import TechnicHub\n\nhub = TechnicHub()",
            1,
        )
    if filename == "technic_42109_keyboard.py":
        helper_blocks.append(("pybricks/keyboard/read_key_code", "getchar"))
    if filename == "inventor_51515_quick_reference.py":
        source = source.replace(
            "drive_base.curve(radius, angle)", "legacy_curve(drive_base, radius, angle)"
        ).replace(
            "drive_base.curve(radius, -angle)",
            "legacy_curve(drive_base, radius, -angle)",
        )
        helper_blocks.append(("pybricks/drive/legacy_curve", "legacy_curve"))
    for identity, alias in helper_blocks:
        snippet = next(s for s in builtin_snippets() if s.identity == identity)
        expansion = instantiate(snippet, {})
        name = ast.parse(expansion.source).body[0].value.func.id
        syntax = Syntax(source)
        source = edit.patches(
            source,
            [
                (syntax.spans[node], name)
                for node in syntax.spans
                if isinstance(node, ast.Name) and node.id == alias
            ],
        )
        source, _ = manage_helpers(source, {f.name: f for f in snippet.helpers})
    return format_source(
        "# Adapted from Pybricks Projects (MIT); see LICENSE.txt and catalog.json.\n"
        + source
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    catalog = json.loads((EXAMPLES / "catalog.json").read_text())
    found = {
        p.relative_to(args.upstream).as_posix()
        for family in catalog["families"]
        for p in (args.upstream / "sets" / family).rglob("*.py")
    }
    assert found == {
        item["source"] for item in catalog["examples"]
    }, "Incomplete upstream inventory"
    for item in catalog["examples"]:
        raw = (args.upstream / item["source"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item["sha256"], item["source"]
        if item["file"] in MANUAL_ADAPTATIONS:
            continue
        adapted = adapt(raw.decode(), item["file"])
        path = EXAMPLES / item["file"]
        if args.write:
            path.write_text(adapted)
        else:
            assert ast.dump(ast.parse(adapted)) == ast.dump(
                ast.parse(path.read_text())
            ), path
    print(
        f"Verified {len(found)} pinned upstream files; "
        f"{len(catalog['examples']) - len(MANUAL_ADAPTATIONS)} structural adaptations, "
        f"{len(MANUAL_ADAPTATIONS)} manual adaptations covered by behavior tests."
    )


if __name__ == "__main__":
    main()
