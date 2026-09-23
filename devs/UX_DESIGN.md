# Studio interaction design

Studio supports a first introduction to robotics and everyday Python work.
Every frontend uses the same document model and core editing operations.

## Workspace

- A narrow vertical strip switches between Program, Control, and Help.
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

Global navigation uses rotated labels and a neutral active indicator. Blocks and
Python use two icons in the document header and matching View menu actions.
Native window controls allow minimizing and maximizing; F11 toggles full screen.

English is the source language and the default on first launch. Russian is a
gettext translation. The language menu uses native names from languages.json;
saved choices survive upgrades. Static captions are explicitly marked with N_,
dynamic messages use tr, and snippet descriptions come from English docstrings.
Changing language preserves editors, history, and unfinished text. Source code,
filenames, parameter values, and console output are never translated.

Documentation lives in doc/en and doc/ru with matching page identities. The help
language follows the interface. Missing translated pages fall back to English;
release checks require both supported manuals to be complete. Page and block
anchors are preserved when changing languages.

The structural view has no text cursor outside parameter editing. Clicking a
field opens its editable combo directly over the source value. The name is a
tooltip and the unit is a read-only suffix. Choices use known types and exclude
imported classes from condition suggestions. Invalid input stays available for
correction without changing the program.

Descriptions and action symbols are display-only. Selection pulses across the
block background; blank lines preserve indentation bands. During a drag, the
view shows the target indentation and a source preview. Library blocks insert
with defaults or context-derived values, without a dialog. The view preserves its
anchor and scrolls only as needed to reveal the start of the inserted block.

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
