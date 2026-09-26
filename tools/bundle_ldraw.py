"""Build a small, attributed parts ZIP for offline distribution outside Git.

Usage: python tools/bundle_ldraw.py model.mpd --library complete.zip [--output parts.zip]
Without --output the subset is written to the user's parts cache.
"""

import argparse
import hashlib
from pathlib import Path

from pyblocks.core.ldraw_parts import digest, subset
from pyblocks.core.paths import parts_cache
from pyblocks.core.project import atomic_write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    destination = args.output or parts_cache() / (args.model.stem + "-parts.zip")
    if destination.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error("Write third-party resources outside the repository")
    data = subset(args.model, args.library, {"archive_sha256": digest(args.library)})
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(destination, data)
    print(destination)
    print("SHA-256:", hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
