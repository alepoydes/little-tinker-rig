"""Keep licensed MPD assemblies, referencing parts from an external LDraw library.

Usage: python tools/prepare_ldraw_model.py source.mpd output.mpd --library complete.zip
This imports CC BY 2.0 model sections, not embedded parts or their editor metadata.
Review source attribution and geometry before distributing the resulting model.
"""

import argparse
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from pyblocks.core.ldraw import LDraw
from pyblocks.core.ldraw_parts import PartLibrary
from pyblocks.core.project import atomic_write


def prepare(source, library):
    sections = re.split(r"(?m)^0 FILE ", source)
    if sections[0].strip() or len(sections) == 1:
        raise ValueError("Expected an MPD beginning with a FILE record")
    models = []
    for section in sections[1:]:
        name, _, body = section.partition("\n")
        if name.lower().endswith(".dat"):
            continue
        if not name.lower().endswith(".ldr"):
            raise ValueError(f"Unsupported embedded resource: {name}")
        licenses = {line for line in body.splitlines() if line.startswith("0 !LICENSE")}
        if licenses != {
            "0 !LICENSE Redistributable under CCAL version 2.0 : see CAreadme.txt"
        }:
            raise ValueError(f"Review the model section's license: {name}")
        lines = ["0 FILE " + name]
        for line in body.splitlines():
            tokens = line.split(maxsplit=14)
            if (
                len(tokens) == 15
                and tokens[0] == "1"
                and tokens[14].lower().endswith(".dat")
            ):
                # OMR prefixes embedded part names with the set number. Remove
                # that namespace only; retain transforms, colors and assembly order.
                part = re.sub(r"(^|[/\\])\d+ - ", r"\1", tokens[14]).replace("\\", "/")
                if not any(
                    library.read(prefix + part) is not None
                    for prefix in ("parts/", "p/", "")
                ):
                    raise ValueError(f"Missing external part: {part}")
                line = " ".join([*tokens[:14], part])
            lines.append(line)
        models.append("\n".join(lines))
    if not models:
        raise ValueError("No assembly sections in this MPD")
    return "\n".join(models) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--library", type=Path, required=True)
    args = parser.parse_args()
    with PartLibrary(args.library) as library:
        text = prepare(args.source.read_text(encoding="utf-8-sig"), library)
    with TemporaryDirectory(prefix="pyblocks-model-") as temporary:
        path = Path(temporary) / "model.mpd"
        path.write_text(text, encoding="utf-8")
        with LDraw(path, args.library) as reader:
            scene = reader.scene()
        print(f"{len(scene.instances)} instances; {scene.step_count} assembly steps")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(args.output, text)
    print(f"{args.output}: {len(text.encode('utf-8'))} bytes")


if __name__ == "__main__":
    main()
