# LittleTinker Rig interaction design

LittleTinker Rig supports a first introduction to robotics and everyday Python work.
Every frontend uses the same document model and core editing operations.

## Workspace

- A left sidebar switches between Program, Control, Help, and Block Editor.
  Lesson and Assembly appear for the corresponding student project. Each row has
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
  and For this lesson. View buttons use icons with localized names and tooltips,
  accessible labels, and a visible active state. Level buttons also use icons:
  one to four filled bars, and infinity for All. Neither group has a persistent
  caption. Collapse/expand-all icons share the view row; personal usage resets
  appear there only when relevant.
- Display subject categories as expandable branches of the catalog tree, with
  cards under them. These replace module-based headings. Do not add another
  category button bar or an extra Python/devices/model hierarchy above them.
- Personal views preserve their own manual, recent, or frequency order. They
  reference the same cards and do not add duplicates inside a view.
- For this lesson consumes the existing current-stage block selection. The stage
  determines its palette without an unrelated level selection hiding required cards.

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

Launching without a filename opens an unnamed document. Its first Save, Run or
Upload asks for a destination; cancellation propagates through execution and
closing. Explicit filenames retain direct-save behavior. The initial window size
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

Scratch is visible when opening a program and hidden in hub Control. Its dock
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
chooses the body. The next outside block or a following blank line offers insertion
after a compound. An insertion row cannot move the hovered source row relative
to the pointer. Invalid contexts have no target; only empty parameters accept
compatible expressions. One accepted gesture creates one Undo operation.

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
