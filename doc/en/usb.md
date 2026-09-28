# USB connection help

For a hub running compatible Pybricks firmware, choose **USB** in **Connect hub**.
Leave the port field empty for automatic discovery, or enter the serial port shown
by your operating system. Installing firmware and transferring programs use different
connections; successful flashing does not establish permission to open a serial port.

LittleTinker Rig uses public Pybricks tools for BLE, legacy USB and firmware installation.
Its temporary USB Serial adapter covers the protocol missing from `pybricksdev 2.3.2`.
Both Inventor/Prime and EV3 on compatible new firmware use this serial protocol.
EV3 remains experimental and has not been verified on physical hardware; the older
EV3 Linux/SD-card environment is outside this adapter's scope.

## Linux: permission denied on a serial port

The app reports the actual port, its group and permissions, followed by an explanation
and, when appropriate, a command for your account. **Copy error** copies the complete
message and command. **USB connection help** opens this page without internet access.
The same explanation appears in the terminal interface and CLI.

For example, examine a connected port and the groups of the running session:

```sh
ls -l /dev/ttyACM0
id
id "$USER"
```

Replace `/dev/ttyACM0` with the reported port. If its owner/group is `root:dialout`
and its permissions are `crw-rw----`, members of `dialout` can read and write it.
On some systems the serial group is `uucp`; use the group of the actual device.
To add your account to `dialout`:

```sh
sudo usermod -aG dialout -- "$USER"
```

This grants access to serial ports assigned to that group. The app only suggests
membership in the serial groups `dialout` and `uucp`; unusual ownership or missing
group read/write permissions require administrator review.

**Fully log out of the desktop and log back in.** Restart LittleTinker Rig and
any IDE or terminal used to launch it from the new session. Simply unplugging the
hub or restarting an app from an old IDE does not update the inherited group list.
If `id "$USER"` already lists the group but `id` does not, membership is already
configured; a fresh session is the remaining step.

If the running process already has the group and opening still fails, have your
administrator inspect the device ACL (`getfacl /dev/ttyACM0`) and system access
restrictions. The app never changes permissions or account membership itself.

## Linux: access for Pybricks USB and firmware tools

Use the rules supplied by the installed `pybricksdev`, as described in the
[official instructions](https://github.com/pybricks/pybricksdev#linux-usb).
From the LittleTinker Rig source checkout:

```sh
uv run --extra pybricks pybricksdev udev | sudo tee /etc/udev/rules.d/99-pybricksdev.rules
sudo udevadm control --reload-rules
```

Unplug and reconnect the hub after installing the rules. If they were already
installed, a serial-port error alone is not a reason to reinstall them: the rules
in `pybricksdev 2.3.2` cover USB and HID devices, but not `tty` ports. Use the serial
access instructions above for `/dev/ttyACM*`. LittleTinker Rig does not ship a
separate copy of these device rules.

## Other connection failures

- **Port busy:** disconnect from Pybricks Code, other editor instances and serial
  terminals, then retry.
- **Port missing:** reconnect the hub with a data-capable USB cable. Its port name
  may have changed; use automatic discovery or select its new name.
- **No response / unsupported protocol:** verify that the hub runs compatible
  Pybricks firmware and is in normal operation, rather than firmware update mode.
  Firmware and device permissions are separate checks.
- **Windows:** a serial hub appears as a COM port, such as `COM3`. Linux group and
  udev commands do not apply. Check Device Manager and close other applications
  holding the port.
- **macOS:** use the detected `/dev/cu.usbmodem…` port; Linux group and udev commands
  do not apply. Close other applications and check the device's access permissions.

During connection, the hub button or F7 cancels the attempt. Once connected, it
disconnects. Read the complete error in **Console**; it retains the original system
error together with the suggested next step.

## Check the connection on Inventor

After access is configured, connect an Inventor with compatible Pybricks firmware.
Open **File → Examples → inventor_51515_hub_check.py**
([source](../../examples/inventor_51515_hub_check.py)). This program uses only the
built-in display and speaker: numbers 1–3 with rising tones, then a heart and a final
beep. It finishes in about five seconds, with progress messages and
`Hub check complete.` in Console. No motors or sensors are needed. The same program
also works on SPIKE Prime; see the [hub API](https://docs.pybricks.com/en/latest/hubs/primehub.html).

**Upload** should finish without running the program. **Run stored program** should
show the sequence and print the messages in Console without another upload. Also check **Run**, console
input with a program that reads it, **Stop**, disconnect/reconnect and cancellation
when the hub is unavailable. Upload replaces the program stored on the hub.

Results on Inventor do not constitute an EV3 hardware test. EV3 compatibility is
currently checked against its protocol and simulated serial responses.
