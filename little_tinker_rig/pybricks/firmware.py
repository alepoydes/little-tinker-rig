"""Validated firmware packages, an offline cache and public Pybricks transports.

Flashing runs in a separate process: the DFU API may terminate its caller.
Nothing is written to a hub during catalog lookup or package preparation.
"""

import asyncio
import hashlib
import io
import json
import re
import struct
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from little_tinker_rig.i18n import N_, tr

MODELS = {
    "inventor": (0x81, "primehub", N_("Robot Inventor / SPIKE Prime")),
    "boost": (0x40, "movehub", N_("BOOST Move Hub")),
    "technic": (0x80, "technichub", N_("LEGO Technic Hub")),
    "ev3": (0xE2, "ev3", N_("EV3 (experimental; hardware untested)")),
}
RELEASES = (
    "https://api.github.com/repos/pybricks/pybricks-micropython/releases?per_page=100"
)
RELEASE_SITE = "https://github.com/pybricks/pybricks-micropython/releases"
LEGO_HASH = "c2ddacb9abef94d72450a1fb468718a08bbe6af09ceed4dd6239e1ef19e0fa9f"
MAX_SIZE = 16 * 1024 * 1024


@dataclass(frozen=True)
class Image:
    model: str
    kind: str
    version: str
    url: str
    digest: str = ""
    channel: str = "stable"
    notes: str = ""

    def matches(self, model, kind, channel):
        return (self.model, self.kind) == (model, kind) and (
            kind == "lego" or self.channel == channel
        )

    @property
    def label(self):
        return (
            f"{self.version} · {tr('Beta')}" if self.channel == "beta" else self.version
        )


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
    firmware: bytes | dict[str, bytes]
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
    request = Request(url, headers={"User-Agent": "LittleTinker-Rig"})
    with urlopen(request, timeout=30) as response:
        data = response.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise ValueError(tr("Firmware download is too large"))
    return data


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data), encoding="utf-8")
    temporary.replace(path)


def _feed_releases():
    """The public feed uses the same versioned asset URLs as the REST catalog."""
    from packaging.version import Version

    root = ET.fromstring(fetch(RELEASE_SITE + ".atom"))
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        identifier = entry.findtext("{http://www.w3.org/2005/Atom}id", "")
        tag = identifier.rsplit("/", 1)[-1]
        # npm packages share this feed but are not hub firmware releases.
        if not re.fullmatch(r"v\d+\.\d+\.\d+(?:[ab]|rc)?\d*", tag) or "@" in identifier:
            continue
        yield {
            "draft": False,
            "tag_name": tag,
            "prerelease": Version(tag).is_prerelease,
            "html_url": f"{RELEASE_SITE}/tag/{tag}",
            "assets": [
                {
                    "name": f"pybricks-{hub}-{tag}.zip",
                    "browser_download_url": f"{RELEASE_SITE}/download/{tag}/pybricks-{hub}-{tag}.zip",
                }
                for _, hub, _ in MODELS.values()
            ],
        }


def _retry_time(error):
    """Honor GitHub's quota reset and both HTTP Retry-After formats."""
    now = time.time()
    retry = error.headers.get("Retry-After", "")
    try:
        delay = now + float(retry)
    except ValueError:
        try:
            delay = parsedate_to_datetime(retry).timestamp()
        except (ValueError, TypeError):
            delay = now + 60
    try:
        reset = float(error.headers.get("X-RateLimit-Reset", "0"))
    except ValueError:
        reset = 0
    return max(now + 60, delay, reset)


def catalog(cache: Path, *, refresh=False, report=lambda text: None):
    path = cache / "releases.json"
    images = (
        [Image(**item) for item in json.loads(path.read_text(encoding="utf-8"))]
        if path.exists()
        else []
    )
    if refresh:
        from packaging.version import InvalidVersion, Version

        cooldown = cache / "api-retry.json"
        retry = json.loads(cooldown.read_text()) if cooldown.exists() else 0
        data = None
        try:
            if retry <= time.time():
                try:
                    data = json.loads(fetch(RELEASES))
                except HTTPError as error:
                    if error.code not in (403, 429):
                        raise
                    limited = (
                        error.code == 429
                        or error.headers.get("X-RateLimit-Remaining") == "0"
                        or "rate limit" in str(error).lower()
                    )
                    if not limited:
                        limited = b"rate limit" in error.read(MAX_SIZE).lower()
                    if not limited:
                        raise
                    retry = _retry_time(error)
                    _write_json(cooldown, retry)
            if data is None:
                report(
                    tr(
                        "GitHub API rate limit reached. API requests resume after {time}; trying the public releases feed.",
                        time=datetime.fromtimestamp(retry)
                        .astimezone()
                        .strftime("%Y-%m-%d %H:%M %Z"),
                    )
                )
                data = list(_feed_releases())
        except (URLError, OSError, ValueError, ET.ParseError) as error:
            if not images:
                raise
            report(
                tr(
                    "Could not refresh firmware versions: {error}. Using the saved catalog.",
                    error=str(error),
                )
            )
            return [*images, LEGO_IMAGE]
        previous = {i.url: i for i in images}
        found = []
        for release in data:
            if release["draft"]:
                continue
            try:
                version = Version(release["tag_name"])
            except InvalidVersion:
                continue
            for model, (_, hub, _) in MODELS.items():
                # EV3 installation starts with the reviewed metadata-v3 release;
                # earlier downloads need an installer we do not provide.
                if model == "ev3" and version < Version("4.1.0b4"):
                    continue
                name = f"pybricks-{hub}-{release['tag_name']}.zip"
                for asset in release["assets"]:
                    if asset["name"] == name:
                        digest = (asset.get("digest") or "").removeprefix("sha256:")
                        old = previous.get(asset["browser_download_url"])
                        found.append(
                            Image(
                                model,
                                "pybricks",
                                release["tag_name"],
                                asset["browser_download_url"],
                                digest or (old.digest if old else ""),
                                "beta" if release["prerelease"] else "stable",
                                release.get("html_url", ""),
                            )
                        )
        # A limited feed must not hide older packages available offline.
        current = {i.url for i in found}
        images = [*found, *(i for i in images if i.url not in current)]
        _write_json(path, [asdict(i) for i in images])
    return [*images, LEGO_IMAGE]


def download(image: Image, cache: Path, *, report=lambda text: None):
    cache.mkdir(parents=True, exist_ok=True)
    suffix = Path(image.url).suffix
    path = cache / (hashlib.sha256(image.url.encode()).hexdigest() + suffix)
    if path.exists():
        data = path.read_bytes()
        report(tr("Using cached firmware: {path}", path=path))
    else:
        report(tr("Downloading firmware {version}…", version=image.version))
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
        report(tr("Firmware saved for offline use: {path}", path=path))
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
        if str(metadata["metadata-version"]).startswith("3."):
            with ZipFile(path) as archive:
                firmware = variants(archive, metadata, model)
                license_text = archive.read("ReadMe_OSS.txt").decode("utf-8")
            if model in ("inventor", "ev3"):
                from . import installer

                root = await asyncio.to_thread(installer.files, download=True)
                license_text += (
                    "\n\n"
                    + tr(
                        "Installer: Pybricks flash tools and bootloader, cached from the official repository."
                    )
                    + "\n"
                    + (root / "LICENSE").read_text(encoding="utf-8")
                )
        else:
            if model == "ev3":
                raise ValueError(
                    tr("EV3 requires a firmware package with metadata version 3")
                )
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
    if not isinstance(firmware, dict) and not 512 <= len(firmware) <= 1024 * 1024:
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


def variants(archive, metadata, model):
    """Validate every v3 image offline; the installer chooses the actual MCU."""
    from pybricksdev.tools.checksum import crc32_checksum, sum_complement

    allowed = {
        "inventor": {"prime_hub", "prime_hub_f4", "prime_hub_h5"},
        "boost": {"move_hub"},
        "technic": {"technic_hub"},
        "ev3": {"ev3"},
    }[model]
    result = {}
    for variant in metadata["variants"]:
        platform = variant["platform"]
        if platform not in allowed or platform in result:
            raise ValueError(tr("Invalid firmware hardware variant"))
        data = archive.read(variant["firmware"])
        limit = variant["checksum-size"]
        if not isinstance(limit, int) or not 0 <= limit <= MAX_SIZE:
            raise ValueError(tr("Invalid firmware image size"))
        checksum = variant["checksum-type"]
        if checksum in ("sum", "crc32"):
            function = sum_complement if checksum == "sum" else crc32_checksum
            data += struct.pack("<I", function(io.BytesIO(data), limit))
        elif checksum != "none":
            raise ValueError(tr("Unsupported firmware checksum type"))
        maximum = min(limit or MAX_SIZE, MAX_SIZE if model == "ev3" else 1024 * 1024)
        if not 512 <= len(data) <= maximum:
            raise ValueError(tr("Invalid firmware image size"))
        result[platform] = data
    if not result:
        raise ValueError(tr("Firmware package contains no hardware variants"))
    return result


async def flash(package: Package):
    """Require bootloader mode and verify the actual device before any erase."""
    if isinstance(package.firmware, dict) and package.model in ("inventor", "ev3"):
        from . import installer

        await asyncio.to_thread(installer.flash, package)
        return
    if package.model == "inventor":
        from pybricksdev.dfu import ALL_PIDS, flash_dfu
        from pybricksdev.usb import LEGO_USB_VID
        from usb.core import NoBackendError, find

        try:
            devices = [
                (d.idProduct, d.bcdDevice)
                for d in find(find_all=True, idVendor=LEGO_USB_VID)
                if d.idProduct in ALL_PIDS
            ]
        except NoBackendError:
            import subprocess

            listing = subprocess.check_output(["dfu-util", "--list"], text=True)
            devices = list(
                {
                    (int(pid, 16), int(bcd, 16))
                    for pid, bcd in re.findall(
                        r"Found DFU: \[0694:([0-9a-fA-F]{4})\].*?ver=([0-9a-fA-F]{4})",
                        listing,
                    )
                }
            )
        if (
            len(devices) != 1
            or ALL_PIDS.get(devices[0][0]) != package.metadata["device-id"]
        ):
            raise ValueError(tr("Connect exactly one matching hub in USB DFU mode"))
        if devices[0][1] != 0x0100:
            raise ValueError(
                tr(
                    "Stable / LEGO firmware requires the original F4 bootloader. Enter USB DFU using the Bluetooth button; H5 hubs require compatible beta firmware."
                )
            )
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
        image = (
            next(iter(package.firmware.values()))
            if isinstance(package.firmware, dict)
            else package.firmware
        )
        if (
            info.type_id != package.metadata["device-id"]
            or len(image) > info.end_addr - info.start_addr + 1
        ):
            raise ValueError(tr("Firmware does not fit the connected hub"))
        await hub.flash(image, package.metadata)
    finally:
        if hub.connected:
            try:
                await hub.disconnect()
            except BleakError:
                pass  # A successful flash reboots and disconnects the device.


def instructions(model, kind, channel="stable"):
    if model == "inventor":
        instructions = tr(
            "USB DFU: turn the hub off and unplug USB. Hold the Bluetooth button while reconnecting USB; release it when the light flashes red, green and blue. Connect only one hub. On Linux, USB access requires libusb/udev permissions; dfu-util is the fallback."
        )
        if kind == "lego":
            instructions += "\n" + tr(
                "The recovery image restores LEGO firmware 1.3. The LEGO app may offer a later update."
            )
    elif model == "ev3":
        instructions = tr(
            "EV3 support is experimental and has not been tested on hardware. Use a current Pybricks beta ZIP. Turn EV3 off, hold Right while turning it on, and release Right when Updating appears. Connect one EV3 by USB. LEGO recovery is not provided for EV3."
        )
    else:
        instructions = tr(
            "Bluetooth bootloader: turn the hub off. Hold its green button until the light flashes purple, then release it. Keep the hub near the computer and close other Bluetooth connections."
        )
        if kind == "lego":
            instructions += "\n" + tr(
                "Select a local LEGO recovery ZIP for this model. Its metadata must declare firmware-type as lego. Automatic LEGO downloads are available only for Inventor / SPIKE Prime."
            )
    if kind == "pybricks" and channel == "beta":
        instructions += "\n" + tr(
            "Beta firmware is experimental. Read the release notes before installing."
        )
        if model == "inventor":
            instructions += "\n" + tr(
                "New beta firmware may install a second-stage bootloader. Its installer is downloaded during preparation and cached for offline use. To restore stable / LEGO firmware on F4 hubs, enter the original DFU mode using the Bluetooth button. Beta installation requires libusb; dfu-util fallback is only available for older firmware."
            )
    return instructions


def result_message(success, kind, model="inventor"):
    if success:
        message = tr("Firmware installation completed.")
        if model == "ev3":
            message += "\n\n" + tr(
                "Close this window and connect EV3 using USB. EV3 support has not been tested on hardware."
            )
        elif kind == "pybricks":
            message += "\n\n" + tr(
                "A blinking blue light means the hub is ready to connect. No manual restart is needed. If the hub is off, press its main button briefly to turn it on. Close this window and choose Connect hub."
            )
            message += "\n\n" + tr(
                "To restart if needed, hold the hub's main button for about 3 seconds until it switches off. Release the button, then press it briefly to turn the hub on again."
            )
        else:
            message += "\n\n" + tr(
                "Turn the hub on if it is off, then connect using the LEGO app."
            )
    else:
        message = tr(
            "Firmware installation failed. Check the log, return the hub to bootloader mode and try again."
        )
    return message


def main():
    import argparse

    from little_tinker_rig.i18n import set_language

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
