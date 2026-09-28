# Changelog

## 0.1.1 — 2026-09-28

### User-visible changes

- Support USB Serial connections on compatible Pybricks firmware: upload, run,
  stop, console input/output and starting a stored program. USB upload and the
  display/sound example have been verified on Robot Inventor. EV3 support is
  experimental and untested on hardware; EV3 port monitoring is not available.
- Select stable or beta firmware and open release notes in both the desktop and
  terminal interfaces. Support new firmware packages and upstream installers for
  Inventor / SPIKE Prime and experimental EV3 installation.
- Reuse downloaded firmware and installer files from the local cache. Firmware
  lookup handles GitHub API rate limits and can fall back to the saved catalog;
  download and cache messages appear in the application.
- Cancel pending connections with the hub button or F7. Once connected, the same
  control disconnects the hub. Connection attempts time out instead of hanging
  indefinitely when a USB hub is unavailable.
- Explain serial-port access errors with instructions for the actual device and
  user account. Add **Copy error**, **USB connection help**, and offline setup
  guides in [English](doc/en/usb.md) and [Russian](doc/ru/usb.md).
- Add [a hub-only Inventor / SPIKE Prime example](examples/inventor_51515_hub_check.py)
  using the display, speaker and console, with no external devices required.
- Preserve operator precedence when replacing or composing expressions in the
  block editor.
- Retain the saved assembly step while a robot model loads or loading fails.
- Fix reopening a file in the terminal editor after saving pending edits.
- Prevent superseded virtual motor commands from stopping newer movements and
  correct timed-motion completion.

### Developer changes

- Validate expression edits against independently transformed AST subtrees.
  Parentheses preserve the intended tree while unaffected comments and whitespace
  remain intact; ambiguous or invalid replacements are rejected.
- Add a temporary SPIKE COBS / Pybricks profile 1.6+ serial adapter using
  `pyserial`. Device identifiers and compilation use public `pybricksdev` APIs;
  compiler ABI and transfer sizes follow the hub's advertised capabilities.
- Isolate native USB operations in a child process so blocked driver calls can
  be terminated. Explicit connection states and generation checks prevent late
  callbacks from restoring a cancelled connection.
- Support firmware metadata v3 and validate target variants before installation.
  Cache upstream flash tools at a pinned revision, verify their SHA-256 hashes,
  and execute them in an isolated Python process.
- Persist firmware catalogs and API retry deadlines; use the public release feed
  during rate limiting without discarding known asset hashes or older cached
  versions. Keep upstream udev rules owned by `pybricksdev`.
- Track virtual motor command ownership and durations independently of waiting
  tasks. Add regression coverage for expression semantics, assembly restoration,
  TUI file reopening, motor replacement, serial framing, USB cancellation,
  access diagnostics and firmware caching/validation.
