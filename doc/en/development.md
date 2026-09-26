# Development

```sh
uv sync --all-extras --locked
uv run --all-extras pytest
uv run ruff check .
uv run black --check .
uv run python tools/translations.py check
uv run python tools/check_docs.py
uv build
```

Core uses the standard library, platformdirs for user-data paths and Ruff's supported CLI with packaged settings.
Qt tests run offscreen. Tests covering asyncio worker threads require local
socketpair communication; a sandbox that denies socketpair writes cannot run
those tests correctly. No test requires a physical robot.

## Invariants

Inline block display has a per-instance Auto/Source/Definition choice. Auto considers
owned comments, never blank lines. Definition text is a source-mapped projection;
changing its mode must not commit, save, format or execute any code. All pointer,
parameter, selection, fold and drag coordinates must map back to the authoritative
source. A compound block's hover span is the entire recognized match, including
its header and projected comments; expanded children use their own spans. Verify
actual pointer events and rendered colors for multi-statement blocks, not only AST
selection or single-statement examples. Titles precede all owned source comments.

Keep source text alongside definition ASTs. AST substitution determines semantics;
text patches preserve comments and layout. Function helpers evaluate each argument
once and isolate local variables. Generated helper definitions retain comments;
inline insertion does not copy explanatory comments. Test source preservation,
comment ownership (including docstrings and trailing suite comments), mode changes,
parameter edits, Undo, and runtime traces after converting activities to functions.

Function blocks show their actual calls, never a substituted label or a body
appended at each call site. Their names must agree in the library, saved calls,
managed definitions and all previews. Keep one reachable definition per name after
imports, with shared dependencies and Scratch retention. Reject conflicting code
or global bindings explicitly; unrelated user functions must not acquire a block's
description merely by sharing its name. Test multiple calls, call-site comments,
editable arguments, definition navigation, final-use cleanup and atomic failure.

Source is authoritative; AST and presentation are derived. Committed documents
parse and compile without executing (Scratch projections only require parsing). Failed operations preserve source, Scratch
and both histories. Unicode spans, comments, literal contents and lexical scopes
must survive transformations. Compare optimized move targets with an independent
compile-based reference. Test interrupted source/workspace saves in both directions.

Each document retains its own draft, selection, scrolling and undo. Window actions
operate on the active tab. Changing language must not translate user text or clear
histories. Drops preview the committed destination and insert without dialogs.
Parameter edits preserve expression grouping and reject stale revisions.
Deleting or detaching a standalone expression removes its owning statement;
only nested expressions leave a `None` placeholder. Empty suites retain `pass`.
Deletion and transfer share this rule; replacement adds parentheses only when
needed to preserve the AST.

Python text assistance uses the public Jedi Script API and the official `pybricks`
API package in the Qt extra. One background queue serializes Jedi's shared parser
cache and coalesces pending requests per editor. Only plain suggestion data crosses
threads. Text/cursor changes, Escape, focus loss and path changes invalidate results;
no suggestion may modify a different source revision. Test static local imports
without execution, incomplete calls, Unicode insertion and native text undo.

Text persistence and structural validity are separate contracts. Saving unfinished
Python preserves the visible text; Run/Upload/Blocks still require syntax validation.
Recovery checkpoints retain the original source/workspace hashes and saved state,
never silently accepting external edits as a new save baseline. Restoring an AST
revision must rebind the editor selection before any view refresh. Check live-window
locks, interrupted recovery transfer, Scratch and conflicting recovered versions.
Runtime locations belong to immutable uploaded sources, including local imports.
Never mark a changed document using an old line number. Traceback parsing must
handle fragmented output without modifying it, and stop interrupts are not failures.
Examples menus derive from the packaged directory listing, without a second catalog.
Repeated refreshes must release obsolete Qt submenus.

Definition drafts are independent of both committed programs and their text
drafts. Static validation must accept template placeholders without evaluating
them. Collection reload invalidates recognition caches, including Scratch, while
preserving source and undo histories. Test invalid-draft recovery, read-only
built-ins, external-change detection, and a failed manifest write during legacy
migration. Preview values must not leak into saved defaults or library cards.
Decorator controls must modify source with ordinary text undo. Block contracts
cover lexical renaming, fixed implementation fields, type/unit diagnostics,
helper deduplication, dependency cleanup, library reloads and Scratch retention.
Migration checks preserve expanded algorithms and historical source and verify
that validation failures or write errors leave collections recoverable.

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

English is the source and default interface language; Russian is a translation. gettext PO files live in
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
and add the corresponding help pages. English needs no translation catalog.

Mark static Qt captions with `N_("Caption")`; `qt.localization.localize` retains
the English originals and updates widgets in place. Dynamic messages
must call `tr("message with {name}", name=value)`. Do not interpolate before lookup.
Parameter values, source, filenames and console output are never translated.
English snippet docstrings share the catalog. Extraction reads explicit `N_` /
`tr` calls and template docstrings, without alphabet detection. Add corresponding documentation under
`doc/<language>/`, retaining page paths so navigation survives language changes.


## Scratch and rendering invariants

Transfers hold their owner's revision and commit both areas atomically. Invalid
context and cancelled drags preserve the source fragment. Scratch-only edits keep
the main syntax index. Undo must not republish a stale cell projection.

Fragment projections require parsing but not executable context; raw cells retain
incomplete Python. Main-document commits still compile. Descriptions and units
never change source text. Rendering checks cover first-line descriptions, blank
indentation bands, and viewport anchors after imports and insertion. A document
with one block can still detach it even when it has no internal move destination.

`test_scratch.py` exercises Qt drag/drop, undo and incomplete cells. It builds
programs through the library and runs them on virtual Inventor, BOOST and Technic,
checking device effects and dependencies as well as syntax.


## Localized documentation and block groups

Keep matching Markdown paths in `doc/en/` and `doc/ru/`. English is the reference
version; update both supported guides when behavior changes. Language-specific
screenshots belong to `doc/<language>/images/`; text-free shared assets may live
in `doc/images/`. Help follows the selected interface language and retains the
current page or block anchor. Missing translated pages fall back to English at
runtime; `tools/check_docs.py` rejects missing release pages and broken local
links or anchors. The root README, code comments, docstrings, design notes, and
commit descriptions use English. Saved language choices remain authoritative;
fresh or invalid preferences default to English.

`snippet_groups()` derives groups from collection/module identities and excludes
historical templates. The library and help use the same grouping. Each group has
one generated reference page, with descriptions, parameters, code, and stable
function-name anchors. F1 resolves a snippet identity to its group and anchor.
No separate maintained Markdown copy of the block reference is needed. Search
matches the full group page, and Back includes visits to sections of the same page.

## Performance and packaging checks

AST indexing is linear. Committed transformations format and parse again; hover
and navigation reuse the index. History stores source/Scratch snapshots. Move
validation normally compiles one candidate per statement suite; declarations such
as global, nonlocal, and __future__ require per-position validation. The resulting
move is always compiled before publication. Pointer dragging chooses a geometric destination first, validates it lazily,
and reuses that result until the source revision changes. An invalid destination
must not snap to a different legal target.

Compile the monitor and controller as well as the courier example:

```sh
uv run --extra pybricks python -m mpy_cross_v6 pyblocks/pybricks/hub_monitor.py -o /tmp/pyblocks-monitor.mpy
uv run --extra pybricks python -m mpy_cross_v6 pyblocks/pybricks/hub_controller.py -o /tmp/pyblocks-controller.mpy
```

Imports in static templates declare dependencies, including names used only by
default expressions. F401 is disabled for template modules because removing those
imports can break expanded programs. Run behavioral tests after linting and
formatting. Pointer indentation, rather than the text cursor's column zero, selects
the nesting of a drop onto an empty line.

## Imported set programs

Imported programs in `examples/pybricks` must remain composable from the standard
palette. A generic assignment or function-call placeholder must not count as
coverage for an unknown device API. Test each actual call against the bundled
operations, rebuild recognized fragments and compare ordered device commands and
final virtual state. At import time, compare against the pinned upstream revision
as well. Preserve argument evaluation order, wait flags, stop modes, repeated
sensor reads and termination; migration to a current API name must keep the data.
Script mechanical end stops and remote inputs explicitly in tests. Do not turn
unsupported physical behavior into a silent success in the interactive simulator.
The simulator's public keyword names must match Pybricks, including `run_time(time=...)`.

## Interactive latency

Measure complete insertions, including analysis, Qt layout, and repaint:

```sh
uv run --extra qt python tools/benchmark_editor.py --lines 1000 5000
```

Runtime formatting uses Ruff's public CLI with `core/formatting.toml`; repository
code style is checked with the development Black dependency. Scratch views parse
existing text without reformatting it; committed edits still format and validate.
Source indexes and derived presentation are reused while the revision is unchanged.
Hit testing and snippet overlap selection use indexes, and rendering visits visible
rows. Formatting operations batch Qt layout updates. Benchmark library-to-Scratch
and program-to-Scratch separately, and verify undo after each transfer.

Regression checks must exercise actual pointer activation for every enum value,
plain identifier fields, source preservation while opening menus, comment colors,
and the insertion marker above all owned descriptions. Window control tests click
the visible buttons; window flags alone do not verify desktop decorations.

## Pointer and firmware regression rules

A drag is a display projection over an unchanged document. Do not maintain a
second mutable source or add Undo entries during movement. Restore transient Qt
formats before committing. Test Escape followed by movement with the button still
held, return to origin, invalid contexts, expressions, and transfers in both areas.

Insertion space changes layout. Test the global position of the same source row
and the pointer's relative location after every marker update, including short
documents, scroll limits, compound headers and Scratch cells. Reserve temporary
scroll space and complete cell layout before compensating the anchor. A screenshot
of the marker alone cannot verify this invariant. Notes must retain ancestor bands;
painting their background without those bands erases structural information.

Test upload without execution and stored execution after editing/deleting local
source and imported modules. Firmware preparation must never access hardware.
Reject mismatched metadata before transport, check the connected model before
erase, verify the reviewed digest again in the flash process, and propagate
failures. Use mocked transport boundaries in automation; report physical flashing
separately. A subprocess isolates public DFU routines that may call SystemExit.

## Structural fields and shared painting

Names, expression leaves, operators and editable lists refer to one Syntax
revision. Token indexes locate fields absent from AST coordinates, such as a
function name, and delimit argument lists without splitting strings or nested
expressions. Edits validate before a single commit. Operator changes preserve
operand ASTs; list edits retain comments and reject invalid parameter ordering.
Signature checks use known lexical definitions without executing user code.
Unknown unpacking, decorated functions and rebound callables do not produce
speculative arity errors. Rename checks must cover shadowing, stores, declarations
and keyword arguments, not just matching text.

Code and generated notes share region geometry for background and interaction
states. Drawing note backgrounds after selection used to erase hover; a separate
comment palette also drifted from source colors. Use the shared region pass, with
note-specific drawing limited to the hash, symbol and text. The hash follows the
containing statement's indentation; the symbol may align with an inner expression.
Drag markers explicitly set their brush and pen: inheriting a previous brush when
drawing the frame can repaint the marker with an unrelated dark fill. Test pixel
contrast, owner hit testing and hover on both notes and code, including nesting.

Selection previously darkened already-painted regions with a second Multiply
overlay. Saturation alone also left very pale colors too similar. Activity now
increases saturation and reduces lightness before the one-owner region paint,
retaining the hue. Verify both the color transform and rendered nested
notes/code; descendants retain their own hues under an active ancestor.

Library levels describe introduction order and accumulate. Keep the initial
twenty-block motor/sensor/robot path usable without advanced cards. Verify generated
expansions, contextual insertion and complete learning examples on all three
virtual profiles. Host-installed MicroPython shims must not enable unsupported
firmware modules (in particular `urandom` on BOOST). Virtual drive-base moves
model wheel geometry and final positions with constant motor speed; they do not
model acceleration, tire slip, gyro corrections or different braking dynamics.
Arc wheels use a common completion time, not equal angular speeds. Hub feedback
is recorded and printed; hub inputs can be scripted in tests. Remote algorithms
use scripted remote inputs with virtual motors; pairing and Car calibration
require hardware. Nested API reporters such as `hub.imu.heading()` derive their
type and completion suggestions from the same receiver/member-path analysis.
Movement completion compares unrounded positions: rounding a displayed motor
angle before the tolerance check can stop outside the promised tolerance.

## Definition and example invariants

A block default is evaluated at the insertion site. Helper dependency discovery
must inspect a decorated block's body, not capture its insertion defaults as
module helper references. Python annotations are type syntax, not runtime value
blocks. Dictionary keys are arbitrary expressions, not necessarily numeric indices.

Context actions use the pointer's current block. In an expanded recipe, editing
acts on the pointed child; navigation can still open the recipe definition.
Historical navigation retains the matched source path and version, independent
of the installed current definition. Linked-field highlighting uses logical field
identity and match identity, not equal source text.

Keep an inventory of every upstream file in supported hub families at the pinned
revision. Test executable AST rebuilding and MicroPython compilation separately
from virtual command traces. Exclude generic assignment/call placeholders when
checking device-operation coverage. Record scripted boundaries and hardware-only
behavior explicitly. A successful compiler check is not a physical robot test.

## Personal libraries, releases and block contours

The personal collection is an implicit runtime connection shared by frontends.
Resolving it never creates directories; tests isolate it through the path resolver.
Only explicit project collection connections belong in workspace metadata.
Built-in collections remain packaged with the application.

Before changing published definitions, run `pyblocks next-block-version DIRECTORY
MAJOR.MINOR.PATCH` or use the equivalent authoring action. A saved snapshot includes
current modules and its manifest, without recursively archiving existing history.
Validate the staged collection and compare live sources before registration. A
failed manifest replacement removes the new snapshot; an unregistered history
folder is never treated as current source. Match saved helper implementations and
their imports against history; reloading a library must not rewrite them. An
explicit function upgrade replaces the shared definition for all calls, with one
diff and Undo. Changed call signatures require manual editing. Exact-version pins
retain their strict existing semantics.

Contours use logical block ownership and shared fill/comment geometry. Opaque
cosmetic strokes share edge pixels; they do not change layout. Test same-color
siblings, nested comments, scrolling, error overlays and unchanged drop geometry.
Keep viewport work bounded and verify the rendered result at multiple DPI scales.

## End-to-end learning workflows

Exercise visible controls from an empty document through saved source and virtual
execution. Direct Session operations alone do not verify library selection,
focus, dialogs or drag hit testing. Keep the complete window inside the configured
test screen and wait for layout before clicking scrolled cards. With hidden rows
and nonuniform card heights, per-item scrolling could leave a requested card
outside the viewport; use pixel scrolling and assert the clicked item is visible.

An empty `pass` body is an insertion hole before it is part of a recognized
template. Default insertion must test that hole before promoting selection to
the whole match. Cover loops, branches and function bodies through Add selected
block as well as drag-and-drop.

User function cards distinguish action calls from value expressions. Inspect only
returns/yields in the function's own body; nested definitions do not supply its
return value. Respect result annotations and leave decorated callables unknown.
Verify consecutive calls after editing an argument, alongside expression insertion.

Unnamed-document state belongs to the document page and its recovery checkpoint.
Save, Run, Upload and Save-on-close share the same cancellable naming operation.
Do not create a file merely by launching the editor. Keep explicit-path saves and
external-change checks intact. Test cancellation before starting any hub worker
and preserve both text and Undo when the destination changes.

Review translated layouts with Console open on a laptop-sized screen. Workspace
tabs may shorten their captions, but all tabs must remain clickable and retain
the full localized name in a tooltip. Initial window bounds respect screen space.
