"""Serial access advice follows the device and session, never error wording."""

import errno
import shlex
import stat
from types import SimpleNamespace

import pytest

from little_tinker_rig.pybricks import serial_access


@pytest.fixture
def port_access(monkeypatch):
    grp = pytest.importorskip("grp")
    pwd = pytest.importorskip("pwd")
    port = SimpleNamespace(st_gid=20, st_mode=stat.S_IFCHR | 0o660)
    group = SimpleNamespace(gr_name="uucp")
    user = SimpleNamespace(pw_name="student", pw_gid=1000)
    registered, active = [1000], [1000]
    monkeypatch.setattr(grp, "getgrgid", lambda gid: group)
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: user)
    monkeypatch.setattr(
        serial_access,
        "os",
        SimpleNamespace(
            stat=lambda path: port,
            geteuid=lambda: 1000,
            getegid=lambda: 1000,
            getgrouplist=lambda name, gid: registered,
            getgroups=lambda: active,
        ),
    )
    monkeypatch.setattr(serial_access, "sys", SimpleNamespace(platform="linux"))
    return port, group, user, registered, active


def test_access_command_uses_actual_device_group_and_quotes_user(port_access):
    _, _, user, _, _ = port_access
    user.pw_name = "student name"
    error = PermissionError(errno.EACCES, "Accès refusé", "/dev/ttyACM7")
    message = serial_access.opening_error("/dev/ttyACM7", error)
    command = next(line for line in message.splitlines() if line.startswith("sudo "))
    assert shlex.split(command) == [
        "sudo",
        "usermod",
        "-aG",
        "uucp",
        "--",
        "student name",
    ]
    assert str(error) in message
    assert "crw-rw----" in message
    assert "Fully log out" in message


@pytest.mark.parametrize("session_active", [False, True])
def test_existing_membership_does_not_repeat_usermod(port_access, session_active):
    port, _, _, registered, active = port_access
    registered.append(port.st_gid)
    if session_active:
        active.append(port.st_gid)
    message = "\n".join(serial_access.linux_access("/dev/ttyACM0"))
    assert "usermod" not in message
    if session_active:
        assert "ACL" in message
    else:
        assert "running session does not" in message
        assert "Fully log out" in message


@pytest.mark.parametrize(
    "name, mode",
    [
        ("root", stat.S_IFCHR | 0o660),
        ("dialout", stat.S_IFCHR | 0o600),
        ("dialout", stat.S_IFREG | 0o660),
    ],
)
def test_unusual_ownership_never_recommends_privileged_membership(
    port_access, name, mode
):
    port, group, _, _, _ = port_access
    group.gr_name, port.st_mode = name, mode
    message = "\n".join(serial_access.linux_access("/dev/ttyACM0"))
    assert "usermod" not in message
    assert "administrator" in message


def test_unplug_during_permission_diagnosis_keeps_original_error(
    port_access, monkeypatch
):
    def disappeared(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(serial_access.os, "stat", disappeared)
    error = PermissionError(errno.EACCES, "Accès refusé", "/dev/ttyACM0")
    message = serial_access.opening_error("/dev/ttyACM0", error)
    assert str(error) in message
    assert "usermod" not in message
    assert "administrator" in message


@pytest.mark.parametrize(
    "code, platform, advice",
    [
        (errno.EBUSY, "linux", "busy"),
        (errno.ENODEV, "linux", "no longer available"),
        (errno.EACCES, "win32", "device access settings"),
        (errno.EIO, "linux", "USB cable"),
    ],
)
def test_non_permission_errors_and_other_platforms_need_no_linux_metadata(
    monkeypatch, code, platform, advice
):
    monkeypatch.setattr(serial_access, "sys", SimpleNamespace(platform=platform))
    # Looking up Linux users or port metadata here would be an error.
    monkeypatch.setattr(serial_access, "os", None)
    error = OSError(code, "original error")
    message = serial_access.opening_error("COM3", error)
    assert "COM3" in message
    assert advice in message and str(error) in message
    assert "usermod" not in message


@pytest.mark.asyncio
async def test_open_failure_reaches_usb_process_with_complete_diagnosis(monkeypatch):
    serial = pytest.importorskip("serial")
    pytest.importorskip("pybricksdev")
    from pybricksdev.connections.serial import PybricksHubSerial

    from little_tinker_rig.pybricks import usb, usb_process

    monkeypatch.setattr(serial_access, "sys", SimpleNamespace(platform="win32"))
    error = serial.SerialException(errno.EACCES, "Accès refusé")

    def denied(*args, **kwargs):
        raise error

    monkeypatch.setattr(serial, "Serial", denied)
    hub = PybricksHubSerial("COM3")
    monkeypatch.setattr(usb, "find_hub", lambda selector: hub)
    events = []
    await usb_process.serve("COM3", lambda **event: events.append(event))
    assert events == [{"reply": 0, "error": serial_access.opening_error("COM3", error)}]
    assert hub.connection_state_observable.value.name == "DISCONNECTED"
