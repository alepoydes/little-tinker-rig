"""Explain native serial-port failures without changing system permissions."""

import errno
import os
import shlex
import stat
import sys

from little_tinker_rig.i18n import tr


def opening_error(device, error):
    lines = [tr("Could not open USB serial port {port}.", port=device)]
    if error.errno in (errno.EACCES, errno.EPERM):
        lines.append(tr("The operating system denied access to this port."))
        if sys.platform.startswith("linux"):
            lines.extend(linux_access(device))
        else:
            lines.append(
                tr(
                    "Close other applications using the hub and check your operating system's device access settings."
                )
            )
    elif error.errno in (errno.EBUSY, errno.EAGAIN):
        lines.append(
            tr(
                "The port is busy. Disconnect the hub in other applications, then try again."
            )
        )
    elif error.errno in (errno.ENOENT, errno.ENODEV, errno.ENXIO):
        lines.append(
            tr(
                "The port is no longer available. Reconnect the USB cable and select the port again, or leave the port field empty for automatic discovery."
            )
        )
    else:
        lines.append(
            tr("Check the USB cable and close other applications using the hub.")
        )
    lines.append(tr("Open USB connection help for setup instructions."))
    lines.append(tr("System error: {error}", error=error))
    return "\n\n".join(lines)


def linux_access(device):
    import grp
    import pwd

    fallback = tr(
        "Ask your system administrator to grant your account read/write access to this serial port."
    )
    try:
        port = os.stat(device)
        group = grp.getgrgid(port.st_gid).gr_name
        user = pwd.getpwuid(os.geteuid())
        registered = os.getgrouplist(user.pw_name, user.pw_gid)
    except (OSError, KeyError):
        return [fallback]
    lines = [
        tr(
            "Port group: {group}. Permissions: {permissions}.",
            group=group,
            permissions=stat.filemode(port.st_mode),
        )
    ]
    # Only recommend membership in known serial groups, never an administrative
    # group merely because it owns a misconfigured device node.
    if (
        not stat.S_ISCHR(port.st_mode)
        or group not in ("dialout", "uucp")
        or port.st_mode & 0o060 != 0o060
    ):
        return [*lines, fallback]
    if port.st_gid in {*os.getgroups(), os.getegid()}:
        return [
            *lines,
            tr(
                "This process already belongs to the port group. Ask your system administrator to check the port's ACL and system access restrictions."
            ),
        ]
    if port.st_gid not in registered:
        command = shlex.join(["sudo", "usermod", "-aG", group, "--", user.pw_name])
        lines.append(
            tr(
                "To grant {user} access to serial ports in group {group}, run:",
                user=user.pw_name,
                group=group,
            )
            + "\n"
            + command
        )
    else:
        lines.append(
            tr(
                "Your account already belongs to {group}, but this running session does not.",
                group=group,
            )
        )
    lines.append(
        tr(
            "Fully log out of the desktop and log in again, then restart LittleTinker Rig and any IDE or terminal used to launch it. Reconnecting the cable or restarting only the app does not refresh session groups."
        )
    )
    return lines
