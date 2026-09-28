"""Pinned public Pybricks flash tools, downloaded to the user cache on prepare.

New Prime firmware needs upstream's MCU detection and second-stage bootloader.
Keep these together at one reviewed revision, outside the repository. Recheck
every file before executing the public flash entry points in an isolated process.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from little_tinker_rig.core.paths import firmware_cache
from little_tinker_rig.i18n import tr


def files(*, download=False):
    from .firmware import fetch

    manifest = json.loads(Path(__file__).with_suffix(".json").read_text())
    revision = manifest["revision"]
    root = firmware_cache() / "installer" / revision
    for relative, digest in manifest["files"].items():
        path = root / relative
        if not path.exists():
            if not download:
                raise ValueError(
                    tr("Firmware installer is missing; prepare the firmware again")
                )
            data = fetch(
                f"https://raw.githubusercontent.com/pybricks/pybricks-micropython/{revision}/{relative}"
            )
        else:
            data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(
                tr("Firmware installer checksum does not match: {path}").format(
                    path=path
                )
            )
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
    return root


def flash(package):
    root = files()
    # -I keeps the current directory, user site and PYTHONPATH out of the
    # installer process. Only the hash-verified tool directory is added.
    program = """
import sys
sys.path.insert(0, sys.argv[1])
from firmware import create_firmware_blob
from lwp3.bytecodes import HubKind
kind, images = create_firmware_blob(sys.argv[2])
if kind == HubKind.EV3:
    import hid
    if len(hid.enumerate(0x0694, 0x0006)) != 1:
        raise ValueError('Connect exactly one EV3 in firmware update mode')
    from ev3 import flash_ev3
    flash_ev3(images)
elif kind == HubKind.TECHNIC_LARGE:
    from dfu import flash_dfu
    flash_dfu(images, kind)
else:
    raise ValueError('Unsupported installer target')
"""
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-u",
            "-c",
            program,
            str(root / "tools/flash"),
            str(package.path),
        ],
        check=True,
    )
