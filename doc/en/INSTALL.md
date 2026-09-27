# Installation

LittleTinker Rig runs on your computer. Programs for real robots run on Pybricks firmware;
the included virtual hubs need no hardware or connection packages. Python 3.11+
is supported. The development interpreter and exact dependencies are recorded in
`.python-version` and `uv.lock`.

Get the source from [GitHub](https://github.com/alepoydes/little-tinker-rig):

```sh
git clone https://github.com/alepoydes/little-tinker-rig.git
cd little-tinker-rig
```

From the repository, using [uv](https://docs.astral.sh/uv/):

```sh
uv sync --all-extras --locked
uv run --all-extras little-tinker-rig-qt examples/courier.py
```

For just the desktop editor and virtual hubs, use `--extra qt`. Other extras are
`tui` for the Textual terminal interface, `pybricks` for Bluetooth/USB, and
`gamepad` for SDL controllers. `uv run` synchronizes the selected extras, so keep
the extras you need in the command. `--no-dev` omits development tools.

With a regular virtual environment:

```sh
python -m venv .venv
# Activate .venv, then:
python -m pip install '.[qt,pybricks,gamepad]'
little-tinker-rig-qt examples/courier.py
```

English is the default on first launch. Choose **View → Language → Русский**
for Russian. The choice is remembered, including existing Russian preferences. Switching language
preserves open documents, incomplete text and undo histories. Help is bundled
with the package and works offline.

Existing PyBlocks settings, user libraries and cached downloads are retained.
Fresh installations use `little-tinker-rig` in the operating system's user data
and cache directories. New student projects use `.ltr`; existing `.pyblocks`
projects and `.pyblocks.json` workspaces remain readable.

If a dependency is missing, install its extra. If Qt cannot find a platform
plugin, check your desktop session and system Qt dependencies. For headless use,
choose TUI; `QT_QPA_PLATFORM=offscreen` is intended for tests. Bluetooth requires
a powered Pybricks hub and no other app connected to it. USB requires a data
cable and operating-system device permissions.

Next: [first steps](tutorial/first.md), [editing](usage.md), [robots](robotics.md).
