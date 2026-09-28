import asyncio
import hashlib
import io
import json
from dataclasses import replace
from unittest.mock import AsyncMock
from zipfile import ZipFile

import pytest

from little_tinker_rig.pybricks import firmware


def package_bytes(device=0x81, kind="pybricks"):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("firmware-base.bin", b"\x00" * 1024)
        archive.writestr(
            "firmware.metadata.json",
            json.dumps(
                {
                    "metadata-version": "2.1.0",
                    "firmware-version": "test",
                    "device-id": device,
                    "checksum-type": "none",
                    "checksum-size": 1024,
                    "hub-name-offset": 0,
                    "hub-name-size": 0,
                    "firmware-type": kind,
                }
            ),
        )
        archive.writestr("ReadMe_OSS.txt", "Test firmware license")
    return stream.getvalue()


@pytest.mark.asyncio
async def test_prepare_rejects_wrong_model_and_wrong_firmware_without_transport(
    tmp_path,
):
    pytest.importorskip("pybricksdev")
    path = tmp_path / "firmware.zip"
    path.write_bytes(package_bytes())
    package = await firmware.prepare(path, "inventor", "pybricks")
    assert package.firmware == b"\x00" * 1024
    assert package.license == "Test firmware license"
    with pytest.raises(ValueError, match="model"):
        await firmware.prepare(path, "boost", "pybricks")
    with pytest.raises(ValueError, match="firmware-type"):
        await firmware.prepare(path, "inventor", "lego")
    path.write_bytes(package_bytes(0x80, "lego"))
    package = await firmware.prepare(path, "technic", "lego")
    assert package.metadata["device-id"] == 0x80


def test_firmware_download_is_cached_verified_and_survives_offline_use(
    tmp_path, monkeypatch
):
    data = package_bytes()
    image = firmware.Image(
        "inventor",
        "pybricks",
        "test",
        "https://github.com/pybricks/test.zip",
        hashlib.sha256(data).hexdigest(),
    )
    calls = []

    def fetch(url):
        calls.append(url)
        return data

    monkeypatch.setattr(firmware, "fetch", fetch)
    path = firmware.download(image, tmp_path)
    assert path.read_bytes() == data
    monkeypatch.setattr(
        firmware,
        "fetch",
        lambda url: pytest.fail("Offline cache must not use the network"),
    )
    assert firmware.download(image, tmp_path) == path
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        firmware.download(image, tmp_path)
    assert calls == [image.url]


@pytest.mark.asyncio
async def test_flasher_checks_usb_and_ble_models_before_erase(tmp_path, monkeypatch):
    pytest.importorskip("pybricksdev")
    import bleak
    import pybricksdev.dfu
    import pybricksdev.flash
    import usb.core

    path = tmp_path / "firmware.zip"
    path.write_bytes(package_bytes())
    package = await firmware.prepare(path, "inventor", "pybricks")
    erased = []
    monkeypatch.setattr(pybricksdev.dfu, "flash_dfu", lambda *args: erased.append(args))
    monkeypatch.setattr(usb.core, "find", lambda **args: [])
    with pytest.raises(ValueError, match="exactly one"):
        await firmware.flash(package)
    assert not erased
    from types import SimpleNamespace

    monkeypatch.setattr(
        usb.core,
        "find",
        lambda **args: [
            SimpleNamespace(idProduct=pid, bcdDevice=0x0100)
            for pid, kind in pybricksdev.dfu.ALL_PIDS.items()
            if kind == 0x81
        ][:1],
    )
    await firmware.flash(package)
    assert erased == [(package.firmware, package.metadata)]
    monkeypatch.setattr(
        usb.core,
        "find",
        lambda **args: [SimpleNamespace(idProduct=0x0011, bcdDevice=0x0300)],
    )
    with pytest.raises(ValueError, match="original F4 bootloader"):
        await firmware.flash(package)
    assert len(erased) == 1
    monkeypatch.setattr(bleak.BleakScanner, "discover", AsyncMock(return_value={}))
    with pytest.raises(ValueError, match="No matching"):
        await firmware.flash(
            replace(package, model="boost", metadata={"device-id": 0x40})
        )
    assert len(erased) == 1


def test_firmware_dialog_prepares_before_install_and_blocks_close_during_flash(
    tmp_path, qt_app, monkeypatch
):
    from PySide6.QtCore import QProcess
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.firmware import FirmwareDialog

    dialog = FirmwareDialog()
    path = tmp_path / "firmware.zip"
    path.write_bytes(package_bytes())
    try:
        assert not dialog.install_button.isEnabled()
        dialog.prepare(lambda: path)
        for _ in range(200):
            qt_app.processEvents()
            if dialog.job is None:
                break
            QTest.qWait(5)
        assert dialog.job is None
        assert dialog.package is not None
        assert "SHA-256" in dialog.details.text()
        assert not dialog.install_button.isEnabled()
        dialog.consent.setChecked(True)
        assert dialog.install_button.isEnabled()
        arguments = []
        with monkeypatch.context() as m:
            m.setattr(
                dialog.process, "start", lambda executable, args: arguments.append(args)
            )
            dialog.install()
        assert len(arguments) == 1 and dialog.package.digest in arguments[0]
        dialog.installed(1, QProcess.ExitStatus.NormalExit)
        assert not dialog.consent.isChecked()
        assert "failed" in dialog.log.toPlainText()
        dialog.model.setCurrentIndex(1)
        assert dialog.package is None and not dialog.install_button.isEnabled()
    finally:
        if dialog.job is not None:
            dialog.job.wait(5000)
        dialog.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["inventor", "boost", "technic"])
async def test_upload_does_not_run_and_stored_snapshot_includes_local_imports(
    model, tmp_path
):
    from little_tinker_rig.pybricks.virtual import VirtualConnection

    output = []
    hub = VirtualConnection(output.append, model=model)
    program = tmp_path / "main.py"
    package = tmp_path / "actions"
    package.mkdir()
    (package / "__init__.py").write_text("from .settings import angle\n")
    settings = package / "settings.py"
    settings.write_text("angle = 30\n")
    program.write_text(
        "from actions import angle\nfrom pybricks.pupdevices import Motor\nfrom pybricks.parameters import Port\nMotor(Port.A).run_angle(500, angle)\nprint('ran stored')\n"
    )
    try:
        await hub.connect()
        await hub.upload(program)
        assert not hub.info.running and not output
        assert hub.info.ports["A"]["angle"] == 0
        program.unlink()
        settings.write_text("angle = 180\n")
        await hub.run(wait=True)
        async with asyncio.timeout(5):
            while b"ran stored" not in b"".join(output):
                await asyncio.sleep(0.01)
        assert hub.info.ports["A"]["angle"] == pytest.approx(30, abs=1)
        await hub.stop()
        assert not hub.info.running
    finally:
        await hub.disconnect()


def test_flash_worker_rejects_a_file_changed_after_review(
    tmp_path, monkeypatch, capsys
):
    import sys

    path = tmp_path / "firmware.zip"
    path.write_bytes(package_bytes())
    flash = AsyncMock()
    monkeypatch.setattr(firmware, "flash", flash)
    monkeypatch.setattr(
        sys, "argv", ["firmware", str(path), "inventor", "pybricks", "old-digest"]
    )
    with pytest.raises(SystemExit) as error:
        firmware.main()
    assert error.value.code == 1
    assert "changed after review" in capsys.readouterr().err
    flash.assert_not_awaited()


def test_release_catalog_keeps_channels_separate_and_cached(tmp_path, monkeypatch):
    def release(tag, beta, draft=False):
        return {
            "draft": draft,
            "prerelease": beta,
            "tag_name": tag,
            "html_url": f"https://github.com/pybricks/pybricks-micropython/releases/tag/{tag}",
            "assets": [
                {
                    "name": f"pybricks-{hub}-{tag}.zip",
                    "browser_download_url": "https://github.com/pybricks/test.zip",
                }
                for _, hub, _ in firmware.MODELS.values()
            ],
        }

    monkeypatch.setattr(
        firmware,
        "fetch",
        lambda url: json.dumps(
            [
                release("v4.2.0b1", True, True),
                release("v4.1.0b4", True),
                release("v4.0.1", False),
            ]
        ).encode(),
    )
    images = firmware.catalog(tmp_path, refresh=True)
    assert [
        image.version
        for image in images
        if image.matches("inventor", "pybricks", "stable")
    ] == ["v4.0.1"]
    beta = [image for image in images if image.matches("inventor", "pybricks", "beta")]
    assert [image.version for image in beta] == ["v4.1.0b4"]
    assert beta[0].notes.endswith("/v4.1.0b4")
    assert "Beta" in beta[0].label
    assert not any(image.matches("ev3", "pybricks", "stable") for image in images)
    assert [
        image.version for image in images if image.matches("ev3", "pybricks", "beta")
    ] == ["v4.1.0b4"]
    monkeypatch.setattr(
        firmware, "fetch", lambda url: pytest.fail("Offline catalog used network")
    )
    assert firmware.catalog(tmp_path) == images


def variant_package(path, model, platforms):
    with ZipFile(path, "w") as archive:
        variants = []
        for index, platform in enumerate(platforms):
            name = f"image-{index}.bin"
            archive.writestr(name, bytes([index]) * 1024)
            variants.append(
                {
                    "platform": platform,
                    "firmware": name,
                    "checksum-type": "none",
                    "checksum-size": 4096,
                    "hub-name-offset": 0,
                    "hub-name-size": 0,
                }
            )
        archive.writestr(
            "firmware.metadata.json",
            json.dumps(
                {
                    "device-id": firmware.MODELS[model][0],
                    "metadata-version": "3.0.0",
                    "firmware-version": "4.1.0b4",
                    "variants": variants,
                }
            ),
        )
        archive.writestr("ReadMe_OSS.txt", "Test license")


@pytest.mark.parametrize(
    "model,platforms",
    [
        ("inventor", ["prime_hub_f4", "prime_hub_h5"]),
        ("ev3", ["ev3"]),
        ("boost", ["move_hub"]),
        ("technic", ["technic_hub"]),
    ],
)
async def test_v3_preparation_preserves_variants_and_rejects_wrong_hardware(
    model, platforms, tmp_path, monkeypatch
):
    from little_tinker_rig.pybricks import installer

    (tmp_path / "LICENSE").write_text("Installer license")
    monkeypatch.setattr(installer, "files", lambda **kwargs: tmp_path)
    path = tmp_path / "firmware.zip"
    variant_package(path, model, platforms)
    package = await firmware.prepare(path, model, "pybricks")
    assert package.firmware == {
        platform: bytes([index]) * 1024 for index, platform in enumerate(platforms)
    }
    variant_package(path, model, ["unknown_hardware"])
    with pytest.raises(ValueError, match="hardware variant"):
        await firmware.prepare(path, model, "pybricks")
    variant_package(path, model, [platforms[0], platforms[0]])
    with pytest.raises(ValueError, match="hardware variant"):
        await firmware.prepare(path, model, "pybricks")


def test_cached_installer_requires_pinned_hashes_before_execution(
    tmp_path, monkeypatch
):
    from little_tinker_rig.pybricks import installer

    manifest = json.loads(
        installer.Path(installer.__file__).with_suffix(".json").read_text()
    )
    root = tmp_path / "installer" / manifest["revision"]
    monkeypatch.setattr(installer, "firmware_cache", lambda: tmp_path)
    with pytest.raises(ValueError, match="missing"):
        installer.files()
    relative = next(iter(manifest["files"]))
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_text("Changed installer")
    executed = []
    monkeypatch.setattr(
        installer.subprocess, "run", lambda *a, **kw: executed.append(a)
    )
    with pytest.raises(ValueError, match="checksum"):
        installer.flash(None)
    assert not executed


def test_qt_channel_change_invalidates_review_and_exposes_notes(qt_app):
    from little_tinker_rig.qt.firmware import FirmwareDialog

    dialog = FirmwareDialog()
    stable = firmware.Image("inventor", "pybricks", "4.0.1", "")
    beta = firmware.Image(
        "inventor",
        "pybricks",
        "4.1.0b4",
        "",
        channel="beta",
        notes="https://github.com/pybricks/pybricks-micropython/releases/tag/v4.1.0b4",
    )
    try:
        dialog.catalog_ready([stable, beta])
        assert dialog.version.currentData() == stable
        dialog.package = object()
        dialog.consent.setChecked(True)
        dialog.channel.setCurrentIndex(dialog.channel.findData("beta"))
        assert dialog.version.currentData() == beta
        assert dialog.package is None and not dialog.install_button.isEnabled()
        assert beta.notes in dialog.notes.text()
        assert "second-stage bootloader" in dialog.instructions.text()
        dialog.kind.setCurrentIndex(dialog.kind.findData("lego"))
        assert not dialog.channel.isEnabled()
    finally:
        dialog.close()


def test_rate_limit_uses_feed_and_persists_backoff_without_losing_cached_firmware(
    tmp_path, monkeypatch
):
    from dataclasses import asdict
    from urllib.error import HTTPError, URLError

    data = package_bytes()
    url = firmware.RELEASE_SITE + "/download/v4.0.1/pybricks-primehub-v4.0.1.zip"
    image = firmware.Image(
        "inventor", "pybricks", "v4.0.1", url, hashlib.sha256(data).hexdigest()
    )
    monkeypatch.setattr(firmware, "fetch", lambda url: data)
    cached = firmware.download(image, tmp_path)
    (tmp_path / "releases.json").write_text(json.dumps([asdict(image)]))
    feed = b"""<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><id>tag:github.com,2008:Repository/185628694/v4.1.0b4</id></entry>
      <entry><id>tag:github.com,2008:Repository/185628694/v4.0.1</id></entry>
      <entry><id>tag:github.com,2008:Repository/185628694/@pybricks/firmware/v7.34.0</id></entry>
    </feed>"""
    now = [1000]
    monkeypatch.setattr(firmware.time, "time", lambda: now[0])
    requests, messages = [], []

    def fetch(url):
        requests.append(url)
        if url == firmware.RELEASES:
            raise HTTPError(
                url,
                403,
                "rate limit exceeded",
                {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1500"},
                None,
            )
        assert url == firmware.RELEASE_SITE + ".atom"
        return feed

    monkeypatch.setattr(firmware, "fetch", fetch)
    for _ in range(2):
        images = firmware.catalog(tmp_path, refresh=True, report=messages.append)
        versions = {i.version for i in images if i.kind == "pybricks"}
        assert versions == {"v4.1.0b4", "v4.0.1"}
        stable = next(i for i in images if i.matches("inventor", "pybricks", "stable"))
        assert stable.digest == image.digest
        assert firmware.download(stable, tmp_path, report=messages.append) == cached
        assert any(i.matches("ev3", "pybricks", "beta") for i in images)
        assert not any(i.matches("ev3", "pybricks", "stable") for i in images)
    assert requests.count(firmware.RELEASES) == 1
    assert any("Using cached firmware" in text for text in messages)
    assert any("rate limit" in text for text in messages)
    now[0] = 1600
    firmware.catalog(tmp_path, refresh=True)
    assert requests.count(firmware.RELEASES) == 2

    def offline(url):
        raise URLError("offline")

    monkeypatch.setattr(firmware, "fetch", offline)
    assert firmware.catalog(tmp_path, refresh=True, report=messages.append) == images
    assert "Using the saved catalog" in messages[-1]
    assert firmware.catalog(tmp_path) == images
    assert firmware.download(stable, tmp_path) == cached


def test_catalog_forbidden_without_rate_limit_is_not_hidden(tmp_path, monkeypatch):
    from urllib.error import HTTPError

    def fetch(url):
        raise HTTPError(url, 403, "Forbidden", {}, io.BytesIO(b"Access denied"))

    monkeypatch.setattr(firmware, "fetch", fetch)
    with pytest.raises(HTTPError, match="Forbidden"):
        firmware.catalog(tmp_path, refresh=True)
    assert not (tmp_path / "api-retry.json").exists()


def test_firmware_dialog_reuses_download_after_reopening(tmp_path, qt_app, monkeypatch):
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.firmware import FirmwareDialog

    image = firmware.Image(
        "inventor", "pybricks", "test", "https://github.com/pybricks/test.zip"
    )
    requests = []

    def fetch(url):
        requests.append(url)
        return package_bytes()

    monkeypatch.setattr(firmware, "fetch", fetch)
    for attempt in range(2):
        dialog = FirmwareDialog()
        try:
            dialog.images = [image]
            dialog.selection_changed()
            dialog.prepare_download()
            for _ in range(200):
                qt_app.processEvents()
                if dialog.job is None:
                    break
                QTest.qWait(5)
            assert dialog.job is None and dialog.package is not None
            assert (
                "Using cached firmware" if attempt else "Firmware saved for offline use"
            ) in dialog.log.toPlainText()
            assert "Test firmware license" in dialog.log.toPlainText()
        finally:
            if dialog.job:
                dialog.job.wait(5000)
            dialog.close()
    assert requests == [image.url]
