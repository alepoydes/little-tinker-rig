# Development

```sh
uv sync --all-extras --locked
uv run --all-extras pytest
uv run ruff check .
uv run black --check .
uv run python tools/translations.py check
uv build
```

Core uses the standard library and Black's supported CLI with packaged settings.
Qt tests run offscreen. Tests covering asyncio worker threads require local
socketpair communication; a sandbox that denies socketpair writes cannot run
those tests correctly. No test requires a physical robot.

## Invariants

Source is authoritative; AST and presentation are derived. Committed documents
parse and compile without executing. Failed operations preserve source, Scratch
and both histories. Unicode spans, comments, literal contents and lexical scopes
must survive transformations. Compare optimized move targets with an independent
compile-based reference. Test interrupted source/workspace saves in both directions.

Each document retains its own draft, selection, scrolling and undo. Window actions
operate on the active tab. Changing language must not translate user text or clear
histories. Drops preview the committed destination and insert without dialogs.
Parameter edits preserve expression grouping and reject stale revisions.

Motor tests check motion and stopping, not just encoding. Simulate a device failing
after another motor has started: cleanup must brake the newly started motor too.
Check cancellation before the next connection operation. Test the real monitor
against all target virtual profiles, including BOOST without PUPDevice.

`examples/courier.py` exercises a complete scenario: calibration, line following,
obstacle stop/resume, delivery gripper and emergency cleanup. Virtual tests verify
successful completion, an emergency after the first delivery, a disconnected
sensor and expiration of the route deadline. Available motors must stop on every exit.

Compile hub code with the optional pybricks tools:

```sh
uv run --extra pybricks python -m mpy_cross_v6 examples/courier.py -o /tmp/courier.mpy
```

Verify a built wheel outside the repository, including offline help, translations,
formatting resources and core-only virtual execution on the minimum Python version.

## Translations

Source interface messages are Russian. gettext PO files live in
`pyblocks/locale/<language>/LC_MESSAGES/pyblocks.po`; compiled MO files ship in the
wheel. `locale/languages.json` maps language codes to their native menu names.
Use the development translation tool to extract/update catalogs, validate coverage
and compile. Babel is a development dependency, not a runtime dependency.

```sh
uv run python tools/translations.py update
# Translate new msgstr entries in the PO files.
uv run python tools/translations.py compile
uv run python tools/translations.py check
```

The check rejects missing or unreviewed translations, changed format fields and
outdated MO files. Commit PO and MO files together. To add a language, register
its code/native name in `languages.json`, update the catalogs, translate, compile,
and add the corresponding help pages.

Static Qt captions are captured by `qt.localization.localize`. Dynamic messages
must call `tr("message with {name}", name=value)`. Do not interpolate before lookup.
Parameter values, source, filenames and console output are never translated.
Snippet docstrings share the catalog. Add corresponding documentation under
`doc/<language>/`, retaining page paths so navigation survives language changes.
