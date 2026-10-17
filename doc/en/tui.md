# Terminal Python workspace

The Textual TUI focuses on Python source and Pybricks tools. It does not include
blocks, Scratch, lessons or 3D assembly. Qt is not installed by the `tui` extra.

Install the TUI once from the project folder:

```sh
uv sync --locked --no-dev --extra tui
```

Then run `.\.venv\Scripts\little-tinker-rig-tui.exe` in Windows PowerShell or
`./.venv/bin/little-tinker-rig-tui` in a Linux/macOS terminal. The same command
opens the TUI on later days. Add `--extra pybricks` to the installation command
for real hubs, keeping `--extra tui` as well. Include `--extra qt` too if you
also want the graphical editor in this environment. Omit the filename to start an
untitled program. Choose **Language** from the command menu for Russian.
Firmware and connection requirements are described in
[installation](INSTALL.md) and [robotics](robotics.md).

## Edit and save

The main area is an ordinary Python editor with syntax highlighting and line
numbers. Tab indents; Ctrl+Z / Ctrl+Y undo and redo. Ctrl+Space offers completions,
and F1 shows signatures and documentation using static Jedi analysis.

| Key | Action |
| --- | --- |
| Ctrl+N / Ctrl+O | New / Open |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As; also available through F10 |
| Ctrl+F / F3 | Find and replace / next match |
| Escape | Leave search and return to the editor |
| F10 | Command menu, including syntax checking and language |
| Ctrl+Q | Quit, with a choice to save or discard changes |

Save preserves source text, including unfinished code, comments and spacing. It
does not regenerate imports or block helpers and leaves `.ltr.json` metadata
alone. Legacy encodings are detected on opening; saving writes UTF-8 without a
BOM and updates the encoding declaration in the editor. Line endings are retained.
The declaration change can be undone. A file changed externally cannot
be silently overwritten; reopen it or save your version under another name.

## Connect and run

F7 opens the connection dialog when disconnected. During connection it cancels
the attempt; once connected it disconnects the hub. Bluetooth is selected initially; USB and virtual
Inventor / SPIKE Prime, BOOST and Technic hubs are also available. The model
choice applies only to virtual hubs. The status line shows the connection and
program state.

| Key | Action |
| --- | --- |
| F4 | Save and upload, without starting |
| F5 | Save, upload and run |
| F6 | Stop the program or monitor |
| F8 | Show or hide the console |
| F9 | Open or close the port monitor |

**Run uploaded program** and **Disconnect hub** are available through F10.
Upload requires valid Python and a successful save. Output and transport progress
appear in the console; the progress bar tracks percentages reported by the
transport. Errors offer **Go to error**. Navigation refuses to point into changed
source because the traceback belongs to the version that actually ran.

For a physical hub, the console input sends a line on Enter while a user program
is running. This is program input, not a Python REPL. The local virtual hub does
not accept this text input.

The port monitor is started explicitly. On a physical hub it runs a service
program, stopping the user's program and potentially replacing the stored one.
Upload your program again afterwards. The virtual hub keeps its telemetry service
available in the background; opening the panel makes its ports visible.

## Install firmware

Choose **Hub firmware** from F10. Select the hub and firmware kind, then refresh
versions and prepare a download, or enter the path to a local ZIP/BIN package.
The cache is shared with Qt and supports reuse without downloading again.

Preparation checks the package and shows its model, version, checksum and license.
Follow the displayed bootloader instructions, review the license, then confirm
replacement of the existing firmware and program before installing. The app
releases its hub connection and runs the installer in a separate process. The
installation dialog stays open until the operation finishes and shows the result.

Original LEGO firmware downloads are available only for the supported Inventor /
SPIKE Prime recovery image; other supported hubs require a suitable local recovery
package. There is no program readback from the hub.
