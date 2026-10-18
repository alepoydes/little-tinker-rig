# LittleTinker Rig interaction design

The [visual redesign implementation plan](VISUAL_REDESIGN_PLAN.md) defines the
planned light/dark appearance, unified header, and component migration. It is
future work; the interaction contracts below continue to describe the application.

The [lesson task panel plan](LESSON_TASK_PANEL_PLAN.md) records the delivered
project-scoped lesson design. Earlier catalog delivery notes below describe their
October 2026 baseline; the task panel and open recommendations supersede their
references to lesson restrictions.

LittleTinker Rig supports a first introduction to robotics and everyday Python work.
Every frontend uses the same document model and core editing operations.

## Workspace

- A left sidebar switches between Program, Control, Help, Block Editor, and
  Assembly. A lesson adds a right task panel; only the selected task expands
  into Markdown and inline links. Narrow windows open it as a transient overlay.
  Its collapsed progress chip sits beside hub connection.
  Scratch shares that dock area. Each sidebar row has
  a centered 24-pixel SVG icon in a 48-pixel row. The sidebar is 48 pixels wide;
  names appear only in localized tooltips and remain available to assistive
  technology. Active rows use a neutral background and a left accent.
- Programs have structural and full Python views. Text drafts may be invalid;
  save, run, and returning to Blocks validate and format them atomically. Text
  edits and formatting remain undoable.
- Toolbar actions are grouped by files, history, editing, and execution. Hub
  connection and state appear at the top right.
- The console starts hidden. An unread counter announces output; errors reveal
  it. Users can open, clear, and hide it.
- Library cards show semantic color, Python, a short description, and an action
  symbol. These remain consistent after insertion into the program.
- Offline help combines localized Markdown with generated snippet reference
  pages. Its contents list groups; each group page contains all its templates.
  F1 targets a stable section anchor, and search includes all blocks in the page.
  Source snippets are the only maintained block reference definitions.

## Library redesign target

The catalog implements the following layout:

- Use one exclusive button group for Beginner, Intermediate, Advanced, Expert,
  and All. Preserve cumulative level filtering and the separate All choice.
- Use a separate exclusive button group for Catalog, Favorites, Recent, Frequent,
  and For this task. View buttons use icons with localized names and tooltips,
  accessible labels, and a visible active state. Level buttons also use icons:
  numbered badges 1–4, and infinity for All. Neither group has a persistent
  caption. Collapse/expand-all icons share the view row; personal usage resets
  appear there only when relevant.
- Display subject categories as expandable branches of the catalog tree, with
  cards under them. These replace module-based headings. Do not add another
  category button bar or an extra Python/devices/model hierarchy above them.
- Personal views preserve their own manual, recent, or frequency order. They
  reference the same cards and do not add duplicates inside a view.
- For this task shows the selected task's recommendations without an unrelated
  level selection hiding them. Other catalog views and Scratch remain available.

Each card has an outlined or filled favorite star; clicking it toggles membership
without insertion or dragging, including unavailable favorite references. The
keyboard-accessible context menu provides the same action. There is no detached
favorite button, variant selector, or Add selected block button under the tree.

Right-clicking a family exposes its allowed insertion variants in a submenu. Search
previews the best matching variant; a manual choice remains stable for that query.
An inserted block's Variant submenu switches immediately with one Undo, retaining
compatible fields and applying the same validity checks. F3 or Variants and
parameters opens the detailed editor with a Python diff. Additional settings collapse by default,
while active non-default values stay visible in a summary. An existing form above
the selected level remains editable. The Block Editor's Catalog properties button
edits the same family metadata directly in the definition source.

Current work covers block operations, consolidation of variants, parameters,
categories, and catalog navigation. New lesson sequences and changes to the
teaching of functions are future curriculum work. Function blocks remain ordinary
language tools; they do not prescribe the architecture of every program.

The [catalog research](BLOCK_CATALOG_RESEARCH.md#14-catalog-reduction-and-personal-navigation-proposal)
records consolidation candidates and personal-view semantics. The
[inventory](BLOCK_LIBRARY_INVENTORY.md) records implemented family membership;
[family metadata](DESIGN_SPEC.md#191-catalog-family-metadata) defines its contracts.
The [block library work plan](BLOCK_LIBRARY_PLAN.md) defines the implementation
sequence, dependencies, and completion criteria.

### Nested groups

The catalog uses optional source-authored subgroup paths. Keep purpose as the first level, then use a mechanism or
input kind where it reduces a large list. A robot can contain several mechanisms;
its model name is not a suitable root for shared motor, sensor, or Python blocks.

Start with the two crowded branches, Movement (54 families) and Input (42):

| Category | Subgroups | Placement examples |
|---|---|---|
| Motors and movement | Individual motors; two-wheel drive bases; steering chassis; grippers; two-axis mechanisms; conveyors | Motor setup, motion, measurements and control tuning stay with motors. DriveBase setup, movement, gyro use, line following and remote driving stay with two-wheel bases. Car setup and steering calibration stay with steering chassis. |
| Sensors and input | Color and reflection; distance; force and contact; orientation and motion; buttons and controllers; time; terminal input | Reads are grouped by what they measure. Stopwatch creation and readings stay together. LEGO remote and Xbox branches may separate their controls when the combined branch becomes crowded. |

Creation families spanning several sensor kinds remain directly under Sensors
and input. In particular, `create_color_sensor` already includes ultrasonic,
force, and BOOST sensor variants; `colorsensor_port` also includes an ultrasonic
value constructor. Placing either whole family only under Color would mislabel
its other variants. Search and dependency help must select the matching exact
variant without duplicating the card across branches.

Use a third group only for a useful distinction, such as a model-specific
mechanism implementation or an oversized motor-tuning section. Do not reproduce
the whole category tree below each robot or add empty General/Models wrappers.
Small categories can keep their cards directly under the category. New branches
are justified by existing blocks, not by hypothetical future mechanisms.

`conveyor_transfer` belongs under Conveyors / BOOST Auto Builder: its homing,
geometry and sequence depend on that build. `draw_rectangle` needs a two-axis
mechanism, and `force_gripper` needs a gripper with a force sensor and mechanical
stops. `dance_turns` is a general DriveBase behavior; its Tricky example origin
does not make it exclusive to Tricky. Keep these requirements separate from
hub, port, accessory, and firmware compatibility.

Future applicability filtering should use explicit model selection in project
or lesson context. Currently model-specific routines have a named nested branch;
there is no automatic hardware or model filter. A project can select several mechanisms and models. Complete
discovery remains available through a catalog context action; no persistent extra
selector row is needed. Do not infer a chassis from its connected hub or treat an
unknown project configuration as a confirmed hardware mismatch. Existing source
and favorite references remain accessible when a branch is hidden.

Each family retains one canonical path and its existing stable identity. Paths
use stable keys and localized labels, independent of difficulty and personal
views. Search examines descendants, their path labels, and all eligible variants;
it expands matching ancestors and restores prior expansion when cleared. Group
visibility and collapse/expand-all operate recursively. Favorites, Recent and
Frequent keep their existing flat ordering. Exact lesson and level restrictions
still apply to variants before a card becomes visible.

### Parameter dependency help

Hover shows
the expected type/unit, current name, and a concise availability diagnostic.
Hover does not change the catalog. Clicking or using the parameter context menu
offers these distinct actions:

- Use an existing value: offer compatible variables accessible at this use site,
  and compatible value-producing expressions.
- Show a definition: navigate to a lexically resolved declaration. A clearly later
  module binding is identified by its source line.
- Find a creation block: pin a catalog filter to declarations or constructors
  that provide the required type, selecting the matching family variant.

An unset Motor parameter should lead to motor creation or an existing motor, not
to every operation that takes a motor. A ForceSensor parameter should select the
force-sensor variant of the shared creation card. Derive these relationships
from existing parameter/result annotations and public inline declarations;
function-helper locals are private. Do not maintain another manual list of
device types or a parallel dependency catalog. Unknown types remain uncertain,
not falsely compatible or erroneous. Units use the existing compatibility rules.

Statement creators and value expressions have different insertion destinations.
A creator such as `motor = Motor(Port.A)` is placed before the use in a scope where
the binding is accessible. An expression constructor can fill the input, but its
evaluation frequency matters: placing it inside a loop creates an object on every
iteration. Do not automatically insert or move initialization, choose a hardware
port, rename user variables, or satisfy an entire dependency chain. Show candidate
placement and the resulting Python before an explicit edit. Use the established
drag interaction and Undo; do not restore the removed Add block button.

For a DriveBase input, help may expose the chain from drive base to left/right
motors and ports one step at a time. A combined setup block is another candidate,
not a mandatory program architecture. Existing compatible objects come first.
After insertion, reassess the original input; bind a new name only when that
change is explicitly included in the reviewed edit. Document revision changes
invalidate stale suggestions.
Switching the originating program or Scratch cell to Python also ends a pinned
search, even before its text changes. Hidden block projections cannot receive
replacements while the user edits the corresponding text draft.

Availability diagnostics cover missing names and straight-line reads before
assignment in the same execution scope, including function locals and assignment
right-hand sides. Deferred closures can refer to outer bindings initialized later.
They are lexical diagnostics, not a definite-assignment proof: conditional
creation, runtime calls, and closure execution can remain uncertain. Input types
come from recognized template fields, including calls nested in an assignment or
another public input, and ordinary inference. Unknown expressions may still need
an annotation or Python editing. Source order alone
does not prove availability across branches, loops, closures or function calls.
A module variable used by a function need not precede the function definition;
it must exist when the function executes. Start with clear straight-line cases,
and describe uncertainty rather than claiming full definite-assignment analysis.
Warnings should explain the needed ordering: creation executes before use.
The same input contract governs quick suggestions, catalog filtering, drops and
variant validation. An inner receiver keeps its device contract under an assignment.

The pinned filter survives moving the pointer to the catalog. A compact existing
status/back control identifies the input and restores the previous catalog view,
search, selection and expansion on exit. It must not silently widen lesson or
level restrictions: explain when a provider is hidden and offer an explicit way
to change the relevant filter. Creation search filters declarations by what they
produce; value search filters expressions by the input contract. Selection alone
does not activate either search.

## Hubs and controls

Connections offer Bluetooth, USB, and virtual hubs. The device panel shows hub
name, type, firmware, program state, battery, and ports. Readings are current only
while the monitor is running.

Manual control starts a small monitor on the hub. Its activation explicitly says
that it replaces the user program. Motors can use four stick axes and two triggers;
each binding chooses a source, speed or servo mode, scale, direction, and servo
center. Unassigned motors do not start.

The on-screen controller follows the Xbox layout. An SDL gamepad updates the same
screen and produces the same normalized state. Commands never accumulate in a
queue. Stop, disconnection, disabling manual control, and closing the application
stop control. The hub also stops motors when fresh commands expire.

Virtual hubs use the same connection, execution, port, and control workflows.
User Python runs in a separate process over explicit device models. This is a
teaching model, not physical simulation or a sandbox for untrusted code. Sensor
inputs can be changed on screen; unsupported APIs fail explicitly.

Target Pybricks models are Robot Inventor / SPIKE Prime (A–F), BOOST Move Hub
(built-in A/B motors and external C/D), and LEGO Technic Hub (A–D). The monitor
must work on BOOST without ujson or PUPDevice. The common helper is tested with
typed discovery and a compact text protocol on this profile. Sending Controller
input to a user program remains separate from direct motor assignments.

## Documents, language, and parameter editing

Each file tab owns a Session, text draft, history, selection, and scroll position.
Changing tabs never commits unfinished Python. Hub tools, the console, and global
modes belong to the window. Closing checks every changed document; reopening a
path selects its existing tab.

Launching without a filename opens an unnamed document. Explicit Save and
Save-on-close ask for a destination. Run and Upload capture current source and
open local modules without a naming dialog or an implicit ordinary-file save.
The recovery checkpoint must succeed before submission. Example attempts autosave
through their existing Project file checks, independently of execution. The initial window size
fits the available screen, including the desktop's reserved panels.
When Console reduces workspace height, only the mode list scrolls vertically.
Scrolling never selects a mode. Keyboard navigation skips
unavailable lesson modes.

The library introduces Python basics before robotics. Cards of different heights
scroll by pixels, so hidden level-filtered rows do not prevent revealing a card.
Choosing a `pass` row fills that body when adding a statement, even when the
surrounding construct is recognized as a library template. Action-only user
functions insert sequential calls; value-returning functions remain expressions.

File → Open recent stores up to ten successfully opened or saved paths. Opening
an existing tab preserves its draft. Missing files are disabled; the list can be
cleared.

Global navigation uses icons and a neutral active indicator. Blocks and
Python use two icons in the document header and matching View menu actions.
A visible title bar provides minimize, maximize/restore, and close on every
desktop, including GNOME layouts that hide native buttons. Dragging and edge
resizing use the compositor; double-clicking the title toggles maximization.
F11 toggles full screen.

English is the source language and the default on first launch. Russian is a
gettext translation. The language menu uses native names from languages.json;
saved choices survive upgrades. Static captions are explicitly marked with N_,
dynamic messages use tr, and snippet descriptions come from English docstrings.
Changing language preserves editors, history, and unfinished text. Source code,
filenames, parameter values, and console output are never translated.

End-user documentation lives in doc/en and doc/ru with matching page identities.
Help follows the interface language; missing translated pages fall back to English.
Developer API, architecture, and development pages are English-only and use that
fallback in every interface language. Standalone developer documents belong in
devs and are not translated. Release checks require complete user guides and reject
translated developer pages. Page and block anchors survive language changes.
The [project rules](../AGENTS.md) define this language boundary, including English
source-code comments and localized GUI, block descriptions, and lab/lesson text.

The structural view has no text cursor outside parameter editing. Clicking a
field opens a text input directly over the source value. A field with alternatives
also has an arrow and a completion list below it. Declared names and fields without
alternatives remain plain inputs. The name is a
tooltip and the unit is a read-only suffix. Choices use known types and exclude
imported classes from condition suggestions. Invalid input stays available for
correction without changing the program.

Descriptions and action symbols are display-only. Every description has its own
row and the color of its block, including nested expression blocks. The hash comes
first, followed by an enlarged symbol and description within the existing row height.
Code and descriptions share hover, selection, ancestor bands and owner hit testing. Drop boundaries
precede both descriptions and owned source comments. Selection pulses across the
block background; blank lines preserve indentation bands. During a drag, the
view shows a colored preview attached to the pointer (at most four displayed
lines), an amber origin marker and a green insertion row. Escape restores the
original projection and prevents a held pointer from restarting the gesture. Library blocks insert
with defaults or context-derived values, without a dialog. The view preserves its
anchor and scrolls only as needed to reveal the start of the inserted block.

Logical blocks have thin semantic outlines, with one shared edge between adjacent
blocks. Comments and code are inside the same contour; nested blocks retain parent
color bands. Outlines strengthen with focus and do not add line spacing.

Personal collections live in the user data directory and are shared by documents.
Block Editor offers editable icon/color catalogs, Open blocks folder and Start next
version. A new version archives the saved definitions before further editing.
Program upgrades have a read-only diff preview, explicit acceptance and Undo.

## Detached block ribbon

Scratch and the device dock start hidden in Program mode. Scratch can be opened
with its bottom button and is hidden in hub Control. Its dock
can be resized or closed. Independent cells share the main structural renderer;
each cell also offers a text view for unfinished fragments.

Dragging adds, combines, detaches, reorders, and restores blocks. Cells need no
imports or complete execution context. Returning to the main program adds library
dependencies and validates the complete result. One undo restores both sides.

## Verification

Tests cover invalid-draft preservation, undo, consistent library and source
presentation, mode changes, the console, help navigation, and connection/execution
lifecycle. Virtual motor angles, speeds, sensor feedback, released controls, and
expired commands provide observable results. The real monitor is compiled for
MicroPython and tested at the public device API boundary. Localization checks cover
captions, snippet help, corresponding documentation, links, package resources, and
preservation of user data during language changes.

## Drag boundaries, levels and firmware

Pointer halves choose before/after a row; the lower half of a compound header
chooses the body. The empty visual tail chooses the end of the program, independent
of horizontal position; the last body row still offers insertion inside a final
compound. The next outside block or an interior blank line offers insertion after
other compounds. A shared source offset does not make two suite destinations
equivalent: moving the last child after its parent changes nesting. An insertion
row cannot move the hovered source row relative
to the pointer. Invalid contexts have no target. Ordinary drops accept expressions
only in empty parameters; an explicit value search authorizes replacement of that
exact pinned input. The search belongs to a view and source revision, so catalog
focus does not cancel a search originating in Scratch. One accepted gesture creates
one Undo operation.

Cards and help show Beginner, Intermediate, Advanced, or Expert from collection
metadata. The persisted level filter combines with search and groups; All is an
unrestricted level filter. First launch selects Beginner, and subsequent levels
accumulate earlier ones. The [learning guide](../doc/en/learning.md) describes the
current palette. The [catalog reduction and personal navigation proposal](BLOCK_CATALOG_RESEARCH.md#14-catalog-reduction-and-personal-navigation-proposal)
records the rationale for family cards and the implemented personal views. The Python view remains
available at every level. Selection and hover increase saturation at fixed hue and lightness in both
library cards and source; nested blocks retain their own semantic colors.

The toolbar keeps file, history and hub actions. Structural commands remain in
menus and shortcuts. Upload sends without execution; Run uploads and executes;
Run stored program and Stop act on the hub. Firmware preparation and installation
are separate steps with model checking, cached/local files, license review and
progress. The dialog remains open during writing. There is no source read-back.

## Block presentation

Short source-authored `title` labels use the UI font; Python keeps its monospace
font. The full docstring remains in help and hover text. Compound outlines have
a left guide and closing foot. Insertion markers name the destination suite,
including Inside loop, After loop and At program level. Equal source offsets
do not erase that distinction.

Ordinary scalar clicks edit values without changing the library. Sequence controls
reserve a strip below the viewport instead of covering the next block. Missing
references receive an amber input border and a localized tooltip. Reporter
suggestions require confirmed result compatibility, including units; plain
Python names with unknown units remain editable. Provider discovery uses public
inline declarations and expression return types, never helper-private locals.

The per-block display control appears on hover or selection, or while a manual
override is active. The same modes are available from the context menu. Variant
choices use exclusive actions; the parameter dialog fits its visible fields and
only offers a collapsible Python diff when changes exist.
