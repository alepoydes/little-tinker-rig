"""Validated firmware packages, an offline cache and public Pybricks transports.

Flashing runs in a separate process: the DFU API may terminate its caller.
Nothing is written to a hub during catalog lookup or package preparation.
"""

import asyncio
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

from pyblocks.i18n import tr

MODELS = {
    "inventor": (0x81, "primehub"),
    "boost": (0x40, "movehub"),
    "technic": (0x80, "technichub"),
}
RELEASES = (
    "https://api.github.com/repos/pybricks/pybricks-micropython/releases?per_page=20"
)
LEGO_HASH = "c2ddacb9abef94d72450a1fb468718a08bbe6af09ceed4dd6239e1ef19e0fa9f"
MAX_SIZE = 16 * 1024 * 1024


@dataclass(frozen=True)
class Image:
    model: str
    kind: str
    version: str
    url: str
    digest: str = ""


LEGO_IMAGE = Image(
    "inventor",
    "lego",
    "1.3.00.0000",
    "https://raw.githubusercontent.com/pybricks/pybricks-code/master/src/firmware/assets/prime-v1.3.00.0000-e8c274a.bin",
    LEGO_HASH,
)


@dataclass(frozen=True)
class Package:
    path: Path
    model: str
    kind: str
    version: str
    digest: str
    firmware: bytes
    metadata: dict
    license: str


def fetch(url):
    if not url.startswith(
        (
            "https://api.github.com/",
            "https://github.com/pybricks/",
            "https://raw.githubusercontent.com/pybricks/",
        )
    ):
        raise ValueError(tr("Unsupported firmware download address"))
    request = Request(url, headers={"User-Agent": "PyBlocks-Studio"})
    with urlopen(request, timeout=30) as response:
        data = response.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise ValueError(tr("Firmware download is too large"))
    return data


def catalog(cache: Path, *, refresh=False):
    path = cache / "releases.json"
    if refresh:
        data = json.loads(fetch(RELEASES))
        images = []
        for release in data:
            if release["draft"] or release["prerelease"]:
                continue
            for model, (_, hub) in MODELS.items():
                name = f"pybricks-{hub}-{release['tag_name']}.zip"
                for asset in release["assets"]:
                    if asset["name"] == name:
                        digest = (asset.get("digest") or "").removeprefix("sha256:")
                        images.append(
                            Image(
                                model,
                                "pybricks",
                                release["tag_name"],
                                asset["browser_download_url"],
                                digest,
                            )
                        )
        cache.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps([asdict(i) for i in images]), encoding="utf-8")
        temporary.replace(path)
    else:
        images = (
            [Image(**item) for item in json.loads(path.read_text(encoding="utf-8"))]
            if path.exists()
            else []
        )
    return [*images, LEGO_IMAGE]


def download(image: Image, cache: Path):
    cache.mkdir(parents=True, exist_ok=True)
    suffix = Path(image.url).suffix
    path = cache / (hashlib.sha256(image.url.encode()).hexdigest() + suffix)
    if path.exists():
        data = path.read_bytes()
    else:
        data = fetch(image.url)
    if image.digest and hashlib.sha256(data).hexdigest() != image.digest:
        raise ValueError(
            tr(
                "Firmware checksum does not match; remove the cached file and download it again"
            )
        )
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
    return path


async def prepare(path: Path, model: str, kind: str):
    if model not in MODELS or kind not in ("pybricks", "lego"):
        raise ValueError(tr("Unsupported firmware target"))
    size = path.stat().st_size
    if not 512 <= size <= MAX_SIZE:
        raise ValueError(tr("Invalid firmware file size"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.suffix.lower() == ".zip":
        from pybricksdev.firmware import create_firmware_blob

        with ZipFile(path) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_SIZE:
                raise ValueError(tr("Firmware package is too large"))
            metadata = json.loads(archive.read("firmware.metadata.json"))
        if kind == "lego" and metadata.get("firmware-type") != "lego":
            raise ValueError(
                tr("LEGO recovery packages must declare firmware-type as lego")
            )
        if (
            kind == "pybricks"
            and metadata.get("firmware-type", "pybricks") != "pybricks"
        ):
            raise ValueError(tr("This is not a Pybricks firmware package"))
        if metadata["device-id"] != MODELS[model][0]:
            raise ValueError(tr("Firmware does not match the selected hub model"))
        firmware, metadata, license_text = await create_firmware_blob(path)
    elif kind == "lego" and model == "inventor":
        firmware = path.read_bytes()
        if digest == LEGO_HASH:
            metadata = {"device-id": 0x81, "firmware-version": LEGO_IMAGE.version}
        else:
            metadata = json.loads(
                path.with_suffix(".metadata.json").read_text(encoding="utf-8")
            )
            if metadata.get("firmware-type") != "lego":
                raise ValueError(
                    tr("LEGO recovery packages must declare firmware-type as lego")
                )
        license_text = tr(
            "LEGO firmware is proprietary. Use it only with your LEGO hub."
        )
    else:
        raise ValueError(tr("Choose a firmware ZIP package for this hub"))
    if metadata["device-id"] != MODELS[model][0]:
        raise ValueError(tr("Firmware does not match the selected hub model"))
    if not 512 <= len(firmware) <= 1024 * 1024:
        raise ValueError(tr("Invalid firmware image size"))
    return Package(
        path.resolve(),
        model,
        kind,
        str(metadata["firmware-version"]),
        digest,
        firmware,
        metadata,
        license_text,
    )


async def flash(package: Package):
    """Require bootloader mode and verify the actual device before any erase."""
    if package.model == "inventor":
        from pybricksdev.dfu import ALL_PIDS, flash_dfu
        from pybricksdev.usb import LEGO_USB_VID
        from usb.core import NoBackendError, find

        try:
            devices = [
                d.idProduct
                for d in find(find_all=True, idVendor=LEGO_USB_VID)
                if d.idProduct in ALL_PIDS
            ]
        except NoBackendError:
            import subprocess

            listing = subprocess.check_output(["dfu-util", "--list"], text=True)
            devices = list(
                {
                    int(pid, 16)
                    for pid in re.findall(
                        r"Found DFU: \[0694:([0-9a-fA-F]{4})\]", listing
                    )
                }
            )
        if (
            len(devices) != 1
            or ALL_PIDS.get(devices[0]) != package.metadata["device-id"]
        ):
            raise ValueError(tr("Connect exactly one matching hub in USB DFU mode"))
        flash_dfu(package.firmware, package.metadata)
        return
    from bleak import BleakScanner
    from bleak.exc import BleakError
    from pybricksdev.ble.lwp3 import LEGO_CID, LWP3_BOOTLOADER_SERVICE_UUID
    from pybricksdev.ble.lwp3.bootloader import BootloaderAdvertisementData
    from pybricksdev.flash import BootloaderConnection

    def matches(device, advertisement):
        data = advertisement.manufacturer_data.get(LEGO_CID, b"")
        return (
            LWP3_BOOTLOADER_SERVICE_UUID in advertisement.service_uuids
            and len(data) == 6
            and BootloaderAdvertisementData(data).hub_kind
            == package.metadata["device-id"]
        )

    print(tr("Searching for a matching hub in Bluetooth bootloader mode…"), flush=True)
    found = await BleakScanner.discover(return_adv=True, timeout=8)
    devices = [
        device
        for device, advertisement in found.values()
        if matches(device, advertisement)
    ]
    if not devices:
        raise ValueError(tr("No matching hub found in Bluetooth bootloader mode"))
    if len(devices) != 1:
        raise ValueError(tr("Leave only one matching hub in Bluetooth bootloader mode"))
    device = devices[0]
    hub = BootloaderConnection()
    try:
        await hub.connect(device)
        info = await hub.bootloader_request(hub.GET_INFO)
        if (
            info.type_id != package.metadata["device-id"]
            or len(package.firmware) > info.end_addr - info.start_addr + 1
        ):
            raise ValueError(tr("Firmware does not fit the connected hub"))
        await hub.flash(package.firmware, package.metadata)
    finally:
        if hub.connected:
            try:
                await hub.disconnect()
            except BleakError:
                pass  # A successful flash reboots and disconnects the device.


def main():
    import argparse

    from pyblocks.i18n import set_language

    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("model", choices=MODELS)
    parser.add_argument("kind", choices=("pybricks", "lego"))
    parser.add_argument("digest")
    parser.add_argument("--language", default="en")
    args = parser.parse_args()
    set_language(args.language)

    async def run():
        package = await prepare(args.path, args.model, args.kind)
        if package.digest != args.digest:
            raise ValueError(tr("Firmware file changed after review; prepare it again"))
        await flash(package)

    try:
        asyncio.run(run())
    except Exception as error:
        print(str(error) or type(error).__name__, file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
