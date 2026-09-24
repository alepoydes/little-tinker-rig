import asyncio
import hashlib
import io
import json
from dataclasses import replace
from unittest.mock import AsyncMock
from zipfile import ZipFile

import pytest

from pyblocks.pybricks import firmware


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
            SimpleNamespace(idProduct=pid)
            for pid, kind in pybricksdev.dfu.ALL_PIDS.items()
            if kind == 0x81
        ][:1],
    )
    await firmware.flash(package)
    assert erased == [(package.firmware, package.metadata)]
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

    from pyblocks.qt.firmware import FirmwareDialog

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
    from pyblocks.pybricks.virtual import VirtualConnection

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
