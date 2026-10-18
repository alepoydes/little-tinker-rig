# Installation and first launch

LittleTinker Rig runs on your computer. The editor and virtual hubs need no robot.
Programs for physical hubs require compatible Pybricks firmware. Start with the
virtual hub; [robot connections](robotics.md) and [USB help](usb.md) are separate
steps. The Windows desktop shortcut and physical hardware still need hands-on
verification.

## Install the editor once

Install [Git](https://git-scm.com/downloads) and
[uv](https://docs.astral.sh/uv/getting-started/installation/). On Windows, open
PowerShell and, if WinGet is available, run:

```powershell
winget install --id Git.Git -e --source winget
winget install --id astral-sh.uv -e --source winget
```

If WinGet is unavailable, use the linked installers. Close and reopen PowerShell
after installation so it can find `git` and `uv`. On Linux or macOS, install these
tools using the linked instructions or your package manager. Then, in a terminal,
choose where you want to keep the project and run:

```sh
git clone https://github.com/alepoydes/little-tinker-rig.git
cd little-tinker-rig
uv sync --locked --no-dev --extra qt
```

Keep the project folder in place: the installed editor uses it. `uv` creates an
isolated `.venv` and obtains the Python version in `.python-version` if needed;
you do not need to activate the environment. The project supports Python 3.11+
and uses 3.13 for this checkout. `--locked` keeps the recorded
dependencies, `--no-dev` skips developer tools, and `--extra qt` installs the
graphical editor. These options belong to installation, not daily launch.

## Open the editor any time

On Windows, double-click `little-tinker-rig-qt.exe` in the project's
`.venv\Scripts` folder, or run this from the project folder in PowerShell:

```powershell
.\.venv\Scripts\little-tinker-rig-qt.exe
```

To make daily launch easier, right-click the `.exe` in File Explorer, create a
shortcut (use **Show more options** if needed), and move the shortcut to the
desktop. Keep the project folder at its original location. On Linux or macOS,
launch from the project folder with:

```sh
./.venv/bin/little-tinker-rig-qt
```

On first launch, **Home** shows **First Python program**, an illustrated
three-task lesson. Open that card, change its message and loop count, then choose
**Connect hub → Virtual hub → Robot Inventor / SPIKE Prime → Connect** and press
**F5 / Run**. Open **Console** to inspect the output. A physical robot is not
needed. **New program** starts an empty file; **Open a file…** opens existing
work. The Home icon returns to this page without closing your work. Opening a
lesson card again continues your last attempt. No file path is needed to start
the editor.

English is the initial interface language. Choose **View → Language → Русский**
for Russian; the setting and offline help are saved with your preferences.
The [first steps guide](tutorial/first.md) continues from this example.

## Add a physical hub or controller later

From the project folder, run this installation command once to add Bluetooth
and supported USB connections:

```sh
uv sync --locked --no-dev --extra qt --extra pybricks
```

The same editor shortcut now has hub tools; no extra options are needed to launch
it. This installs a pinned Git revision of the
[pybricksdev fork](https://github.com/alepoydes/pybricksdev). A physical gamepad
also needs `--extra gamepad` in the installation command. When you add a feature
or update the checkout, repeat `uv sync` with *all* the extras you want to keep:
syncing without a previously selected extra can remove it from `.venv`.

A real hub must run suitable Pybricks firmware. Stable Inventor/Prime 4.0.1 uses
Bluetooth; USB Serial needs compatible beta firmware. Follow the
[robot guide](robotics.md) for your hub and [USB help](usb.md) for port and
firmware details. EV3 USB support is experimental and untested on hardware.

For the terminal editor, see the [TUI guide](tui.md); install its `tui` extra once
and launch its executable directly in a terminal.

## If something does not start

- If `git` or `uv` is not found after installation, reopen the terminal and check
  `git --version` or `uv --version`.
- If the editor does not open on Windows, run
  `.\.venv\Scripts\little-tinker-rig-qt-console.exe` from PowerShell to see the
  startup error. On Linux/macOS, start the editor from a terminal to see it.
- If an optional module is missing, rerun `uv sync` with the required extras.
  `PySide6` needs `qt`; `pybricksdev` needs `pybricks`.
- If Qt cannot create a display, check the desktop session and graphics driver;
  for headless use, choose the [TUI](tui.md). If only 3D fails, text steps and
  parts lists remain available.
- For a missing or busy real hub, close other hub apps and check Bluetooth or
  the USB cable and port in [USB help](usb.md).

Fresh installations store preferences, student projects and downloads in the
operating system's user directories. Existing PyBlocks settings, `.pyblocks`
projects and `.pyblocks.json` workspaces remain readable; new lesson projects
use `.ltr`.
