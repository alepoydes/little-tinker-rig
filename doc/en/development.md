# Development

The [project rules](../../AGENTS.md) define the language boundary: developer
documentation, comments, and docstrings are English-only; localization serves
end users through the GUI, block descriptions, help, and lab/lesson content.

The [Pybricks, SPIKE, and MINDSTORMS block research](../../devs/BLOCK_CATALOG_RESEARCH.md)
catalogs operations, execution semantics, and a proposed Python learning
progression. It informs future library and lesson design without changing the
editor's current contracts.

```sh
uv sync --all-extras --locked
uv run --all-extras --locked pytest
uv run --all-extras --locked ruff check little_tinker_rig tests tools build_support.py
uv run --all-extras --locked black --check little_tinker_rig tests tools build_support.py
uv run --all-extras --locked python tools/translations.py check
uv run --all-extras --locked python tools/check_docs.py
uv run --all-extras --locked python tools/catalog_report.py --check --verify-transitions
uv build
```

Lint and format the application, tests and tools. Example programs retain upstream
conventions and are validated by the example tests. Pytest includes the repository
root on its import path so command-line and module invocations resolve the same
development tools.

The uv development environment pins Python 3.13 to use binary wheels for the
locked renderer dependencies. The application's minimum remains Python 3.11.

Core uses the standard library, platformdirs for user-data paths and Ruff's supported CLI with packaged settings.
Qt tests run offscreen. Tests covering asyncio worker threads require local
socketpair communication; a sandbox that denies socketpair writes cannot run
those tests correctly. No test requires a physical robot.

The GitHub Actions workflow uses a GitHub-hosted Ubuntu runner with offscreen Qt.
It checks code, documentation, translations, tests and distribution builds.
Hardware and native OpenGL checks remain local; CI does not need a self-hosted runner.

## Invariants

Before importing an external program or asset, verify the license for that specific
source and retain attribution. A repository license does not automatically cover
its author's website downloads. Keep unlicensed materials as external links;
exclude their contents from source trees, distribution archives and published Git
history. Download/adaptation tools must not bypass this boundary.

Window geometry uses Qt's save/restore API, including maximized/full-screen state
and screen-bound adjustment. Save only after close confirmation and recovery
cleanup succeed. Reopening must remain visible even after closing while minimized.

Read legacy Python files using their declared encoding; Save and Save As always
write UTF-8 without a BOM. Normalize an active encoding declaration through the
shared source-file utility. Frontends apply that text change through their undo
history before updating the saved baseline. Verify actual bytes, reopened text,
editor state, Undo and subsequent saves, including invalid drafts and legacy BOMs.
Editor selections rebind to the current syntax revision after persistence or
recovery changes the document, as well as after interactive edits.

Open reads the destination after Save/Discard/Cancel is resolved. Reopening the
current file must use the just-saved bytes and their new conflict-detection hash;
a failed destination read keeps the current document.

Close confirmations have the same scope as saves. A lesson archive owns all its
programs: when closing a window, ask once per project and consider drafts in every
tab. Discard must not be undone by saving another tab of the same archive; Cancel
preserves the working copy and open documents.

Hub firmware modules are registered by full name and need not be attributes of
their parent module. Load modules directly when inspecting available classes;
do not assume `import pybricks.hubs as hubs` has CPython package semantics.
Monitor tests must exercise this import boundary as well as port telemetry and
motor cleanup. Compilation alone cannot detect missing module attributes.
Async UI tests wait for the complete observable transition, including both
connection state and operation availability; separate queued signals can arrive
in different event-loop iterations.
Unknown devices have no telemetry reads that could detect removal. Rescan them
periodically, remove unplugged entries and preserve active supported devices.
Test both immediate replacement and replacement after an empty-port interval.

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
Use token boundaries when removing parameter defaults: AST expression spans omit
redundant parentheses. Reuse string-aware indentation for definition bodies and
helpers; generic dedenting changes multiline literal values. Verify generated
functions by execution, including parenthesized defaults, docstrings and f-strings.

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
Lexical analysis and renaming cover every binding form, including match captures,
star patterns and mapping remainders. Comprehension bodies skip class namespaces;
only the outermost iterable uses the enclosing class scope. Verify both name
resolution and runtime results after unrelated edits, cleanup and renames.

Each document retains its own draft, selection, scrolling and undo. Window actions
operate on the active tab. Changing language must not translate user text or clear
histories. Drops preview the committed destination and insert without dialogs.
Parameter edits preserve expression grouping and reject stale revisions.
Deleting or detaching a standalone expression removes its owning statement;
only nested expressions leave an `...` placeholder. Empty suites retain `pass`.
Deletion and transfer share this rule; replacement adds parentheses only when
needed to preserve the AST.
Expression edits replace subtrees before projecting text. Validate the projection
against that independent tree, not against another textual substitution. Apply
the same operation inside linked parameters before propagating their values.
Check precedence, associativity, comments and one-step Undo for both copy and move.

Python text assistance uses the public Jedi Script API and the official `pybricks`
API package in the Qt and TUI extras. A shared analysis lock protects Jedi's
parser cache; the Qt queue additionally coalesces pending requests per editor. Only plain suggestion data crosses
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
`little_tinker_rig/locale/<language>/LC_MESSAGES/little_tinker_rig.po`; compiled MO files ship in the
wheel. `locale/languages.json` maps language codes to their native menu names.
Use the development translation tool to extract/update catalogs, validate coverage
and compile. Babel is a development dependency, not a runtime dependency.

```sh
uv run --all-extras --locked python tools/translations.py update
# Translate new msgstr entries in the PO files.
uv run --all-extras --locked python tools/translations.py compile
uv run --all-extras --locked python tools/translations.py check
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

Keep matching end-user Markdown paths in `doc/en/` and `doc/ru/`. English is the
reference version; update both user guides when behavior changes. Developer API,
architecture, and development pages exist only in `doc/en/`; the help viewer uses
its existing English fallback for them. Put standalone developer documents in
`devs/`, without translations. Language-specific
screenshots belong to `doc/<language>/images/`; text-free shared assets may live
in `doc/images/`. Help follows the selected interface language and retains the
current page or block anchor. Missing translated pages fall back to English at
runtime; `tools/check_docs.py` rejects missing user-guide pages, translated developer
pages, and broken local links or anchors. The root README, code comments, docstrings, design notes, and
commit descriptions use English. Saved language choices remain authoritative;
fresh or invalid preferences default to English.

`snippet_groups()` derives help groups from collection/module identities and
excludes historical templates. Catalog categories and families independently
control discovery; they do not change help identities. Each help group has
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
uv run --extra pybricks python -m mpy_cross_v6 little_tinker_rig/pybricks/hub_monitor.py -o /tmp/little-tinker-rig-monitor.mpy
uv run --extra pybricks python -m mpy_cross_v6 little_tinker_rig/pybricks/hub_controller.py -o /tmp/little-tinker-rig-controller.mpy
```

Imports in static templates declare dependencies, including names used only by
default expressions. F401 is disabled for template modules because removing those
imports can break expanded programs. Run behavioral tests after linting and
formatting. Pointer indentation, rather than the text cursor's column zero, selects
the nesting of a drop onto an empty line.

## Imported set programs

Assess construction from an empty document as a one-time manual design review:
can the available tools express the program, and are those tools discoverable?
Record gaps and findings in `AI`. Do not add complete GUI reconstruction scenarios
to the recurring suite. Keep focused regression tests for the semantic and UI
invariants that can break accidentally.

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
rows. Match note ownership through an indexed statement range, not a full-document
scan per block. Definition comment projection reuses the template's comment owners;
it must not instantiate each call merely to display the same comments. Reporter
compatibility is cached per catalog/input type, while receiver names retain the
current lexical context. Formatting operations batch Qt layout updates. Benchmark library-to-Scratch
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

Connection lifecycle is separate from hub telemetry. Disconnect cancels an in-flight
connect; busy ends only after cleanup, and callbacks from a cancelled attempt cannot
restore a connection. Native USB drivers live in a child process so synchronous
native stalls cannot block cancellation. Kill and reap that process when cooperative
shutdown fails. Exercise connect timeout, cancellation, reconnection and hung
shutdown with a blocking synthetic child, without discovering physical devices.

Release lookup must preserve cached versions and digests during rate limiting or
network failure. Persist GitHub's retry deadline and reuse identical asset URLs
across REST and public-feed lookup. Catalog refresh never downloads binaries;
reopening preparation reuses verified archives. Test with synthetic HTTP failures
and local packages, never repeated real API calls.

Keep Pybricks-owned functionality behind public upstream APIs; USB identifiers
come from pybricksdev. The serial adapter is a compatibility layer until upstream
provides it. Do not duplicate upstream udev rules. Diagnose serial open errors
before crossing the worker boundary, retaining errno-specific advice and the original
error. Linux group advice comes from device metadata, account membership and process
groups; never suggest joining an administrative group. Tests distinguish missing
membership, stale sessions, ACL failures, busy ports and unplugged devices. UI help
must remain accessible offline. Inventor checks do not establish EV3 hardware support.

USB Serial uses SPIKE COBS framing, not ordinary zero-delimited COBS. Fragmentation,
coalescing and malformed frames must not change transaction boundaries. Serialize
requests and correlate responses by tag / read selector; on timeout or cancellation
close the stream rather than reusing it with an ambiguous late reply. An upload
invalidates stored-program metadata before writing and commits its size only after
every chunk succeeds. Run waits for idle status after its start acknowledgement,
not a stale status from before it. Keep BLE and legacy USB on their public adapters.

Metadata v3 separates hub type from hardware variant. Validate all images during
preparation; let the pinned public upstream installer identify the actual DFU MCU
before erase. Never send a v3 F4/H5 image to the old fixed-address DFU writer.
`pybricks/installer.json` pins the upstream tools, license and bootloader hashes;
they live in the user cache and are rechecked before execution. Update them as one
reviewed unit. Keep hardware targets separate from implemented virtual profiles:
EV3 USB support does not imply an EV3 simulator, BLE or port monitor.

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
nineteen-family motor/sensor/robot path usable without advanced cards. Verify generated
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
Timed motor commands advance on the same World clock as target motions. A new
command replaces the previous deadline; waiters may complete only the command
they started. Test cancellation and deadline integration with explicit time steps.
Runtime integration tests allow the modeled one-degree completion tolerance and
check stopped speed, rather than requiring an exact printed angle.

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

Before changing published definitions, run `little-tinker-rig next-block-version DIRECTORY
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
the whole match. Cover loops, branches and function bodies through catalog
double-click insertion as well as drag-and-drop.

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
navigation uses a narrow, fixed-width icon strip with localized tooltips. Keep
names in the item model for accessibility while suppressing painted labels; icons
stay centered, and language/font changes do not widen the strip. Short panels
scroll without selecting a mode. Hidden lesson modes are disabled and
Home/End target visible rows: hiding a QListWidget row alone does not exclude it
from keyboard navigation. Verify scrolling, selection, hidden modes, localized
tooltips and icon rendering. Initial window bounds respect screen space.

## Lesson and renderer invariants

Preserve a requested assembly step until the model supplies its actual step count.
Sparse step annotations and failed loads must not clamp saved progress. Navigation
becomes available after loading; only then clamp an out-of-range saved step.

Use the editor's `commit` operation when applying lesson starters: a direct
Document commit leaves selection pointing into the old syntax tree. Stage changes
must never commit source. Save a project's raw drafts and Scratch before replacing
its archive, and keep it dirty if archive writing fails after the working files
were saved. Recovery keeps the original archive hash to detect external changes.
Remove a closed project's working directory only after the recovery checkpoint
stops referencing it; a failed checkpoint must leave that directory recoverable.

Keep palette policy separate from the session's recognition catalog. Verify that
an existing block remains editable when hidden by the current stage, and that
search, expression suggestions and direct drops respect the stage palette.

For OpenGL integration, verify a real QOpenGLWidget under both Wayland and X11,
as well as headless shader results. An X11-only check misses EGL attachment errors.
Resolve OpenGL functions through `QOpenGLContext.getProcAddress`: Qt owns the
native context and selects its backend. Do not infer GLX from Linux, create a
second native context, or reuse another widget's cached ModernGL context. Detect
the current Qt framebuffer on every paint; zero is not its render target. The
small native-context regression can be run with `QT_QPA_PLATFORM=wayland` or
`xcb`; it is skipped on Qt's non-GL offscreen test platform. Mesh loading belongs
off the GUI thread. Camera and step changes reuse uploaded meshes and buffers.
Model traversal must retain inline primitives alongside part references, including
their assembly step; test mixed geometry rather than only standalone part files.

Third-party part libraries are external resources, not lesson source assets.
Keep pinned references in Git and verified archives in the shared user cache.
Downloads and ZIP/mesh loading run off the GUI thread; index a ZIP once and read
only needed members. Do not copy downloaded geometry into lesson directories for
packaging. Offline export owns a snapshot and writes a separate archive, retaining
drafts, Scratch, dependency closure and licenses without marking the original
project saved. Test cancellation and checksum failure against synthetic archives,
then reopen an exported project with its cache removed and networking disabled.
The pilot mating check is optional: set `LITTLE_TINKER_RIG_TEST_LDRAW` to a verified local
`complete.zip`. Routine tests never download the full library.

Package only authored lesson Python, JSON, Markdown, text notices, LDraw models
(`.ldr`/`.mpd`) and PNG/SVG illustrations. Keep the lesson file filters in
`MANIFEST.in` and `build_support.py` aligned; both exclude the `ldraw` directory,
archives and working state. Git ignore rules do not control Python packaging.
Verify both sdist and wheel with stray resources present in a temporary source
tree, including a direct wheel build. The local `AI/` working notes are excluded
from version control and distributions; maintained decisions belong in the design
specification or developer documentation. Original lesson materials use the
project's MIT license; external parts retain their own license notices.

## Catalog navigation invariants

Filter exact variants by level, lesson identity, and insertion type before choosing
a representative card. A primary identity must not grant access to siblings in a
restricted lesson. Enforce the same palette at all catalog insertion entry points,
including a new Scratch cell and insertion into an existing cell. Record usage
only after a successful edit; transfer, recognition, Undo/Redo, and automatic helper
management are not catalog use.

Family grouping does not alter source, role colors, or help anchors. Sort tree
children without detaching them: Qt item removal/reinsertion can lose hidden state.
Search snapshots preserve selection and expansion across collection reloads and
language changes. Personal views keep their own ordering; frequency is refreshed
on entering the view, never while a card is being selected or dragged.

Unnamed documents need unique, recovery-persisted catalog scopes: a placeholder
filename cannot isolate equal function names in different drafts. First save
migrates references and counts together, including selected personal-view rows;
subsequent Save As keeps path-based isolation.

Variant previews use the same preparation as acceptance without mutating the
document. Revalidate the syntax and selected match before committing. Preserve
compatible shared expressions, declaration names and comments; fixed options such
as `wait=False` must not reset when a variant exposes them as editable fields.
Validate the known result type against the parent input. Test side-effectful
argument expressions by observing evaluation order and their received values,
not by comparing formatting alone. Reordering templates may require retained
keyword spelling; reject a switch if order cannot be preserved.

AST operators, `withitem`, and absent optional children have no independent source
span. Text rewriting must fall back to the nearest locatable changed ancestor and
discard its partial descendant patches. Verify the resulting AST, parentheses,
comments, and literal values. The catalog report's transition check exercises all
built-in family transitions with defaults, including recognition after the edit;
focused tests cover non-default values, evaluation order, stale dialogs, and Undo.

Quick variant menus share dialog filtering and the core edit transaction; they
must not insert a new block or record another use. Card favorite hit testing uses
the painted star bounds and stable references, including unavailable cards.
Consume its pointer gesture before item dragging or double-click insertion.

Parameter suggestions carry expansions, including imports and helpers, until the
edit commits. Inline fields and variant changes must use those same dependencies.
Automatic measurement candidates opt in with `readout=True`; returning a numeric
value does not make a blocking motor action a measurement. Recognized inner calls
retain input contracts even when a larger block owns their display and linked edits.
Catalog filtering, drops and variant validation use those same nested contracts.
Declaration changes in variant dialogs reuse lexical rename patches, including
references outside the replaced block and unchanged input expressions inside it.
Conflicts reject the whole edit; preview and application include one Undo transaction.

Pinned searches are owned by a source view and revision, not keyboard focus.
Test browsing from Scratch through applying a result and one Undo. Ordinary drops
protect filled values; replacement is authorized only for the exact searched input.
Keep scalar edits and hovering independent of catalog discovery.
Switching the originating document or Scratch cell to Python invalidates the search
immediately. A hidden structural projection must never overwrite a visible draft;
verify the displayed text through save, reopen and a switch back to blocks.

Name diagnostics distinguish lexical ownership from initialization during ordered
evaluation. Visit assignment values before writes and loop iterables before targets.
Reads in the same execution scope must have a preceding value; deferred functions
may reference outer values created later. This is not control-flow analysis across
branches or a proof of runtime initialization.
Deferred global/nonlocal writes are possible initializers only after a call to their
known function in the same execution scope. Merely defining the function does not
suppress an earlier missing-name warning. Calls inside deferred bodies do not
initialize module values at definition time.

Class-local reads before their first value fall back to globals, not a shadowed
enclosing function variable. Use the same lookup for diagnostics, renaming and
dependency retention. Managed imports also retain names in quoted parameter and
return annotations, including quoted types nested inside generic annotations.
