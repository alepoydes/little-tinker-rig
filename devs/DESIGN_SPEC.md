# LittleTinker Rig: Design and Implementation Specification

**Status:** consolidated design specification for implementation

**Project name:** LittleTinker Rig

This document describes the current design of a Python structural editor and robotics development environment intended to be implemented with Codex. It consolidates the agreed ideas, requirements, architecture, interaction model, snippet model, UI principles, and Pybricks integration. It intentionally omits the history of how the design was reached.

Where a detail has not yet been decided, the document marks it explicitly rather than inventing a choice.

The [block catalog and learning research](BLOCK_CATALOG_RESEARCH.md)
compares Pybricks, SPIKE, and MINDSTORMS and proposes a Python learning progression.
Its catalog and curriculum proposals are research inputs, not changes to the
implemented contracts described here.
The [block library work plan](BLOCK_LIBRARY_PLAN.md) covers the next catalog and
block-variant revision, including compatibility and verification requirements.

---

## 1. Core idea

LittleTinker Rig is not a Scratch clone and not a separate visual programming language.

It is a **structural editor for ordinary Python source code**.

The normal `.py` file is the single source of truth. The editor parses the source into a Python AST and uses that structure to provide block-like interaction, constrained editing, drag-and-drop, semantic highlighting, completion, snippet recognition, validation, and educational guidance.

The most important invariant is:

> A project must remain normal, readable, executable Python even if LittleTinker Rig disappears.

A user must be able to open the file in Vim, VS Code, Helix, or any other text editor, modify it, and later reopen it in LittleTinker Rig. LittleTinker Rig-specific metadata must not be required for the Python file to make sense or execute.

LittleTinker Rig may lose some enhanced presentation or snippet recognition after arbitrary external edits, but it must degrade to generic structural Python editing rather than making the source unusable.

The editor therefore treats block structure as a **derived view of Python**, not as a second program representation.

---

## 2. Motivation and philosophy

The difficulty of Python for a beginner is often not that `if`, `while`, function calls, or expressions are conceptually too hard. A major difficulty is that a text editor permits an enormous space of malformed or irrelevant states:

```python
if x <:
motor.run[
motro.run(500)
Motor.Port.A
```

A Scratch-style editor avoids many such errors by constraining the user's actions, but it introduces a second language and a later transition from blocks to text.

LittleTinker Rig should keep the constraint and guidance of a block editor while using Python from the beginning.

The desired learning path is therefore continuous:

1. The beginner mostly manipulates structural blocks and predefined snippets.
2. The user sees real Python syntax at all times.
3. More expression editing and source-level freedom can gradually be exposed.
4. Any block can eventually be edited as ordinary Python.
5. The final result is still the same `.py` file rather than code translated from another language.

The editor should allow different presentation intensities, from nearly ordinary Python to a strongly block-like view, without changing the program representation.

---

## 3. Scope

The initial application domain is Pybricks robotics, but the structural editor must not be coupled to Pybricks.

The project should be useful as a generic Python structural-editing engine with optional domain packages.

The Pybricks application adds primarily:

- a Pybricks snippet collection;
- Pybricks-aware completion and diagnostics where practical;
- a host-side connection/run backend;
- console interaction;
- application data suitable for virtual or physical controllers;
- virtual screen controls such as joysticks and buttons.

The structural editor itself should work without any robotics dependency.

---

## 4. Non-goals

The following are not initial goals:

- implementing another programming language;
- maintaining a separate block-project format as the authoritative program;
- binary compatibility with Scratch projects;
- reproducing Scratch sprite/stage semantics;
- requiring Chromium or a browser runtime;
- requiring Qt for users who only want a terminal interface;
- building a full Python type checker comparable to Pyright;
- implementing a full IDE before the structural editing model works;
- hiding Python behind opaque generated code;
- storing per-block UUIDs or editor metadata in the Python source;
- making browser or tablet support a requirement for the first implementation.

---

## 5. Source code is the authoritative representation

The authoritative program representation is always Python text.

A typical processing cycle is:

```text
Python source
    -> canonical formatting
    -> ast.parse()
    -> AST and source-range index
    -> structural presentation and interaction
```

After a committed structural edit, the main source must again be syntactically valid Python.

The AST is reconstructed from the source. It is not a persistent parallel document model.

This removes the need for difficult synchronization between a text representation and a block representation.

### 5.1 Canonical formatting

The project must use a standard deterministic Python formatter so that structurally equivalent edits converge to a predictable textual form.

The editor uses Ruff through its public CLI, with packaged deterministic settings.

Requirements for the formatter choice:

- mature and reliable;
- deterministic;
- practical to invoke from Python tooling;
- acceptable for normal Python projects;
- should not introduce a large architectural dependency.

Formatting should normally happen after a committed structural transformation rather than continuously while the user is in the middle of an incomplete local edit.

### 5.2 AST positions and source ownership

For presentation purposes, every source character should logically belong to the **deepest AST node that determines that character's contents**.

This does not require an actual array entry for every character. An interval/range representation is preferable if it is simpler and faster.

For a source position, the editor must be able to determine:

- the deepest AST node owning the position;
- its ancestors;
- its children;
- its source range;
- its semantic/presentation category;
- whether it is a legal movable or editable unit.

The Python AST already provides source positions for most syntactic nodes. The core should build a convenient parent/child/range index from a single AST traversal.

Comments are indexed with standard tokenization alongside the AST. Standalone
comments belong to the next statement in the same suite, across blank lines;
inline comments belong to the statement on that line. Docstrings belong to their
function, class or module. Final comments without a following statement belong to
their scope. File metadata and managed section markers remain file-owned.

---

## 6. Structural blocks without a separate block model

A block is not a stored UI object. It is a view over a source range corresponding to an AST node or a recognized snippet.

This is a central simplification.

The editor should not maintain a second tree such as:

```text
VisualBlock -> PythonCodeGenerator -> source
```

Instead:

```text
source -> AST -> structural regions
```

All block behavior should be derived from the Python structure wherever possible.

Useful rule:

> If information can be derived reliably from source and AST, do not store it separately.

Examples:

- nesting derives from the AST;
- block boundaries derive from source ranges;
- available lexical names derive from scope analysis;
- snippet parameters derive from snippet function signatures;
- snippet documentation derives from docstrings;
- snippet dependencies derive from imports in snippet definitions;
- snippet units can derive from annotations;
- snippet categories can derive from their module/package location;
- presentation role derives from node/snippet semantics.

---

## 7. Main editor and Scratch workspace

The primary desktop layout should conceptually have three columns:

```text
+------------------+------------------------------+------------------+
| Library          | main.py                      | Scratch          |
|                  |                              |                  |
| snippet groups   | normal Python source         | temporary pieces |
| and search       | with structural interaction  | and experiments  |
+------------------+------------------------------+------------------+
```

This layout belongs to the Qt structural editor. The TUI edits plain Python source
and exposes a smaller set of Pybricks tools, as specified in section 33.

The desktop window saves its geometry only after closing is accepted. Restore
position, normal size and maximized/full-screen state before the next first show,
using Qt's geometry serialization and screen-bound adjustment. Do not restore a
minimized state or replace saved geometry when closing is cancelled.

### 7.1 Main source

The block view represents a valid structural projection. Inline fields and local
fragment dialogs apply only syntactically valid edits; invalid input remains
editable until corrected or explicitly cancelled. Valid inline input applies on
Enter, suggestion acceptance or leaving the field, including before Save and Run.

Full-document Python view may contain and save unfinished text. Its draft shares
document history with blocks and Scratch. Run, Upload and switching to Blocks
require valid syntax; saving a text draft does not. See section 43.

### 7.2 Scratch workspace

The Scratch workspace is intentionally less strict.

It is a place for:

- temporarily removed blocks;
- incomplete expressions;
- partially written statements;
- experiments;
- alternative implementations;
- code fragments that currently do not parse.

A Scratch item may therefore be either valid Python or arbitrary dirty text.

Scratch is persisted as text fragments in the sibling `name.py.ltr.json` workspace,
alongside collection paths and pins. Lesson projects package these files in `.ltr`.
Editor metadata never enters the Python source. See the
[file API](../doc/en/api.md#documents-and-sessions) and
[lesson project guide](../doc/en/lessons.md).

### 7.3 Moving between main and Scratch

Moving a valid structural block from the main source to Scratch removes the corresponding source fragment from the main program and stores the fragment in Scratch.

If removal would leave an empty required suite, the main source must be repaired using a valid Python placeholder such as `pass`.

Moving a Scratch fragment back into the main program is allowed only when it can produce valid Python in the selected structural location.

---

## 8. Valid placeholders

The editor should use ordinary Python placeholders rather than editor-only empty nodes.

Examples:

```python
if condition:
    pass
```

and where an expression is structurally required:

```python
some_call(...)
```

`pass` and `...` are examples of context-dependent valid placeholders. The exact rules for when to introduce them should remain simple and Python-native.

`None` is an ordinary Python value, not an unfilled input. Empty required suites
use `pass`; unfinished expressions use `...`. Save preserves unfinished inputs;
Run and Upload require filling them.

The UI may present an automatically introduced placeholder as an editable slot rather than emphasizing the literal `...` or `pass` to a beginner.

---

## 9. Structural highlighting and the visual block model

LittleTinker Rig should be capable of looking visually close to a block editor without drawing puzzle-piece geometry.

Python indentation already defines much of the visual nesting.

The editor should use subtle background regions behind source ranges and extend the background beyond the final source character of a line toward the visual end of the line. This continued background is important: it gives each line/block a visible rectangular body rather than merely coloring tokens.

Nested code naturally creates nested colored regions due to indentation.

### 9.1 Semantic colors

Colors should correspond to semantic groups rather than assigning an unrelated strong color to every AST class.

Possible semantic roles include:

- control flow;
- loops;
- actions/calls;
- values;
- variables/state;
- functions/definitions;
- hardware/domain-specific nodes;
- placeholders;
- snippets/compound recognized regions;
- warnings/errors.

The exact palette is a design parameter, but default semantic color guidance should be shared between frontends.

Logical blocks have subtle one-pixel semantic contours. Recognized compact blocks
have one outline; expanded structural children have their own. Adjacent contours
share an opaque boundary, and descriptions/source comments belong inside the
same outline as code. Reuse the fill geometry instead of outlining all AST nodes.
Borders preserve line heights, hit testing and drop coordinates; scrolling does
not add artificial caps at the viewport edge. Hover and selection strengthen the
outline, while error borders and drag markers retain visual priority.

### 9.2 Hover and selection

Permanent semantic colors should be vivid enough to distinguish block types
while preserving readable Python text and editable field contrast in both themes.

When the pointer or cursor is over a region:

- the exact node under consideration should become more prominent;
- it should be possible to navigate to the parent or child structural node;
- selection should be visually stronger than mere hover.

### 9.3 Presentation intensity

A saved **Block color** slider in the appearance menu controls the presentation
continuum between:

```text
plain text  <-------------------------->  strongly block-like
```

This is a presentation choice over the same source and AST, not a conversion between languages.

The slider changes only the structural editor's fill intensity. Catalog cards
keep their semantic colors so discovery remains consistent.

---

## 10. Structural selection and editing

The editor should make AST nodes directly manipulable.

At minimum, the core needs operations for:

- locating a node from a source position;
- selecting a node;
- selecting its parent;
- selecting an appropriate child;
- replacing a selected expression;
- deleting/moving a statement;
- inserting code into a valid structural location;
- moving code to/from Scratch;
- inserting a snippet;
- expanding/unlocking a recognized snippet for generic editing.

The core should describe what moves are valid. Frontends should only translate user gestures into these operations.

---

## 11. Drag-and-drop as navigation through structural insertion targets

The core should not depend on mouse coordinates or Qt drag events.

A move operation can be modeled more generally as:

1. choose a structural source node;
2. enumerate legal insertion targets;
3. navigate among targets;
4. preview the current target;
5. commit or cancel.

This supports multiple interaction mechanisms with the same implementation.

### 11.1 GUI interaction

The library, document and Scratch share one cancellable pointer gesture. A colored
preview attached to the pointer shows at most four displayed lines. The source
is temporarily replaced by one highlighted Previous position row; expressions
leave an inline origin marker. Source and history stay unchanged until a valid
drop. Escape, invalid release, or return to origin restores the view without a
history entry. One successful commit and Undo cover both affected areas.

The upper/lower half of a source row selects insertion above/below. Below a
compound header means its first body position. Insertion after the whole compound
uses the next outside block or a following blank line. Horizontal position on a
blank line selects nesting. Compatible expressions fit empty parameter slots;
an explicit value search additionally authorizes replacement of its exact pinned
input. Other filled inputs remain protected, and one Undo restores the old value.

A new Insert here row opens space before descriptions and owned comments. Adding
or removing it must preserve the same source row and relative pointer position.
Decorations are not new structural targets. Invalid contexts offer no insertion;
they must not snap to a distant valid context. Edge autoscroll is explicit; dragging
does not automatically fold code.

### 11.2 TUI interaction

The terminal frontend uses ordinary text selection and editing. Structural move
navigation is available in Qt and the headless structural core, not in TUI.

### 11.3 Other interactions

Because moving is represented as generic navigation over valid structural targets, later frontends or keyboard styles can reuse the same core behavior without another drag-and-drop algorithm.

---

## 12. Low-level and high-level core APIs

The core should expose two useful levels of behavior without becoming a large framework.

### 12.1 Low-level structural operations

These are Python/source operations such as:

```text
parse source
find source range for node
replace a range
move a structural range
reindent moved source
format source
match an AST template
analyze lexical scope
```

They know nothing about GUI widgets, mouse events, or terminal rendering.

### 12.2 High-level interaction primitives

These expose the reusable interaction state needed by real frontends, for example conceptually:

```text
select at position
select parent
select child
begin move
move to previous/next candidate
move outward/inward
preview destination
commit move
cancel move
insert snippet
move to Scratch
restore from Scratch
```

This level knows the structural editing model but still not Qt, TUI, or WUI details.

The purpose of this split is maximum code reuse, not architectural ceremony.

---

## 13. Text editing and expert mode

Structural editing is the default constrained mode, but any block should be editable as ordinary Python.

The user should be able to activate something equivalent to **Edit as Python** on a selected block or expression.

For the main source:

- editing may temporarily produce invalid text inside the active local editor;
- the edit cannot be committed until the affected source parses correctly;
- cancel restores the previous valid state.

For Scratch:

- invalid text may remain indefinitely.

When a text-edited region becomes valid Python again, it is reparsed and automatically decomposed into normal structural nodes and recognized snippets.

There is therefore no irreversible boundary between structural and textual editing.

---

## 14. Snippet system: overview

The educational/domain-specific layer should be implemented primarily through **snippet libraries**.

A snippet is not merely a text completion. It is an AST template with editable placeholders.

A snippet may correspond to a single expression, one statement, or a substantial multi-statement algorithm.

A recognized snippet may be presented as one compound logical block, with only explicitly defined placeholders editable by default, even though the underlying `.py` file contains ordinary expanded Python code.

The user can always switch to generic Python editing, at which point the snippet may cease to be recognized and simply becomes normal AST structure.

---

## 15. Source-complete block definitions

A Python definition is the sole source of block behavior and metadata. Modules
are parsed statically; loading never executes decorators, imports, defaults or
bodies. Each module defines a help group, with its docstring providing the group
title and description. Catalog categories and families can group cards across modules. A function docstring provides block help and search text.

```python
@inline_block(level="beginner", icon="⚙", color="state", names=("motor",))
def create_motor(port: "Port" = Port.A):
    """Connect a motor to a hub port."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import Motor

    motor: "Motor" = Motor(port)
```

`@inline_block` substitutes the body into the destination scope. A single return
expression defines an expression block. Repeated fields repeat evaluation.
`@block` generates an ordinary helper call: arguments are evaluated once and
locals are confined to the function. Modes are explicit and never converted
silently. Generated programs need no LittleTinker Rig runtime or decorators.

Both decorators accept literal `level`, `icon`, `color`, and optional `kind`.
Inline blocks additionally accept `names` and `context="loop"` or `context="async"`. Difficulty is one
of beginner, intermediate, advanced, expert; all is only a filter. A color is a
palette role or #RRGGBB. Defaults are intermediate, ▶, and the snippet palette.

Signature parameters define expression fields. `names` publishes declarations
for lexical renaming, including created variables and nested names such as
`action.value`. Other methods, constants, operators and internal identifiers are
fixed until explicit expansion/Python editing. Every structural entry point,
including list controls and drops, uses the same permission rules. Public
expression lists remain extensible; changed implementations lose recognition
and their previous descriptions.

Input contracts live in parameter annotations. Created variables have annotated
assignments in the body; result annotations describe actual returned values.
`kind="statement"` keeps return as an instruction. `context="loop"` unwraps one
while body for break/continue. `context="async"` unwraps an async function for
await statements; compiler validation enforces the insertion context.
Control context is not a result type.

Undecorated functions in a format-2 module are shared helpers. Reachable helpers
are emitted once after imports, retaining their authored Python names. Definitions
and dependencies are retained while referenced by ordinary code or Scratch and
pruned after their final use. Existing implementations survive library reloads;
undo restores code and dependencies atomically. Imports are similarly managed,
while local imports inside generated functions retain normal Python scope.
Function blocks show only their actual calls, with editable arguments and program
comments. Their bodies are accessible through Open definition and the complete
Python source, never appended to each call. Conflicting function names require an
explicit rename; presentation must never conceal a different runtime name.

Block signatures have fixed parameters. Inline templates reject recursion,
classes and global/nonlocal declarations; ordinary helpers use normal Python
signatures. Calls to decorated blocks inside helper code supply every field;
block defaults are insertion expressions, not runtime function defaults.
The module itself contains a docstring, imports and functions.

---

## 16. Snippet matching

Snippet recognition must be structural, using AST patterns rather than textual equality.

Formal parameters act as pattern variables.

For example the template:

```python
motor.run(speed)
```

should match:

```python
left_motor.run(700)
```

and bind conceptually:

```text
motor = left_motor
speed = 700
```

A placeholder may represent a larger expression when its context allows that.

If the same formal parameter occurs multiple times in a template, matching should require consistent binding.

A recognized multi-statement snippet should match a contiguous structural region rather than individual isolated lines.

If several templates match the same region, the matching policy should favor the more specific/larger meaningful template rather than fragmenting a known algorithm into many tiny snippets. Exact precedence rules should stay simple and can be refined when real ambiguities appear.

Failure to recognize a snippet is never a program error. The same source simply falls back to generic AST-based presentation.

---

## 17. Snippet editing and loss of recognition

A recognized snippet exposes only its declared placeholders by default.

If the user changes only placeholder values, the snippet remains recognized.

If the user enters generic source-edit mode and changes internal template structure, the source is reparsed normally. If it no longer matches the snippet template, the compound snippet presentation disappears and the code is shown as ordinary Python blocks.

This is expected behavior, not an error.

---

## 18. Snippet hygiene and local names

Complex snippets may introduce local variables such as:

```python
error = ...
tmp = ...
i = ...
```

Insertion must avoid accidental capture or collision with surrounding names.

The snippet engine therefore needs simple hygienic renaming of locally introduced identifiers when necessary.

Formal parameters are public placeholders and must not be renamed arbitrarily.

Local names created only inside the template may be alpha-renamed when a conflict exists.

The hygiene mechanism should remain narrow and AST-based rather than attempting to implement a new macro language.

---

## 19. Snippet libraries, collections, and extensibility

Snippet libraries may come from several independent sources:

- built-in generic Python snippets;
- built-in Pybricks snippets;
- user-defined libraries;
- course-specific libraries;
- competition-specific libraries;
- third-party or commercial libraries.

A library may consist of multiple Python modules.

The directory/module structure can naturally define the Library panel grouping where convenient, for example conceptually:

```text
snippets/
    python/
    pybricks/
        motors.py
        sensors.py
        drivebase.py
    robocup/
        line.py
```

Collections use `collection.toml` for identity, version, format version and history.
Format 2 uses decorators for blocks and ordinary functions for helpers. Block
levels and appearance belong exclusively to the definition source. Legacy
collections remain readable and have an explicit, validated migration command.

A major design goal is that writing a new snippet should require mostly writing normal Python rather than authoring a large schema or UI definition.

### 19.1 Catalog family metadata

Catalog grouping is independent of Python module paths and block role colors.
A module may declare one literal `__category__` string; a block's optional
`category` decorator argument overrides it. The built-in categories are `program`,
`values`, `data`, `functions`, `movement`, `input`, `output`, and `devices`. Older
collections without categories retain their module headings.

An optional single-line `title` separates the compact label from the full help
docstring. Without it, older definitions retain their first help line as a title.
The optional `group=("Mechanism", "Model")` contains up to two nonempty path
segments beneath the category. Segments are English translation keys; localized
labels never become persistent navigation keys. The family primary owns the path;
members may omit it or repeat it exactly. Block Editor edits these literal fields.

The optional boolean `readout=True` declares an expression suitable for automatic
measurement suggestions. It must not start motion, wait, consume input, or change
device state. The default is false, including for older collections. Receiver-method
suggestions require this declaration as well as compatible type and unit contracts.
Suggested expansions retain imports and helpers through inline and variant edits;
dependencies and the value change are committed together.

A family uses the complete identity of a current primary block. Other forms name
it with `family="collection/module/block"`. Primaries omit `family`; chains,
missing primaries, and incompatible statement/expression or context requirements
are rejected when a collection loads. Category changes never change identity.
Definitions remain the sole source of code, parameters, descriptions, and grouping.
The [generated inventory](BLOCK_LIBRARY_INVENTORY.md) can be regenerated with
`python tools/catalog_report.py` and checked with its `--check` option.

`variant` is a short, translatable operation label. A family member without this
label is a compatibility alias: normal discovery omits it, while recognition and
an existing lesson's exact identity can still use it. Choosing one family does
not grant access to all its forms. Level, lesson, and insertion-context filters
apply to each exact variant before producing a card.

`advanced=("then", "wait")` identifies optional fields for compact editing;
these names must have defaults in the signature. `bindings={"rotation_angle":
"angle"}` maps differently named parameters to shared family fields, with unique
keys within a variant. Unmapped names keep their own names. The metadata does
not create runtime enums, evaluate defaults, or rewrite existing Python.

For example, motor movement forms can omit `wait`, expose a Boolean `wait`, or
expose the existing `Stop` enum as `then`. Stop, brake, and hold use different
ordinary Python methods in one statement family. Reading motor settings remains
an expression family separate from setting them. Historical spellings preserve
their argument order, even when argument expressions have side effects. Reloading
the catalog never silently converts a recognized form into its primary form.

Copying a variant into a personal collection detaches its family reference and
preserves its effective category, so the copy is a usable standalone definition.
Handwritten collections may opt into grouping without migrating their existing
source bodies or adding a parallel catalog file.

For an inserted, currently recognized family block, the **Variant** context submenu
applies a chosen form immediately with one Undo. The current form is checked;
level restrictions filter the other forms. Stale source/selection
and incompatible edits fail atomically. No extra insertion or usage is recorded.
F3 or **Variants and
parameters…** opens an explicit edit dialog. Compatible shared fields retain
their expressions; newly exposed fixed API options retain the old source value.
Other new fields use the definition default or `...`, without evaluating it.
Additional settings are collapsed unless their current values differ from defaults;
a collapsed section still summarizes active differences. Enum and Boolean choices
use the existing parameter suggestions and allow ordinary Python expressions.

The dialog previews the complete Python diff, including imports and helpers.
Applying revalidates the selected source revision and commits one undoable edit;
Cancel and invalid input leave source, Scratch, and history intact. Existing forms
remain selectable even when above the current level or retained only as aliases.
Other choices obey level restrictions. Returned values must fit
the parent input's known type. Declaration names, literal contents, comments, and
the evaluation order of retained call arguments survive the edit. When compatible
keyword spelling can preserve that order, it is retained; otherwise the edit is
rejected with an explicit message. Changes to the operation itself, removed fields,
units, waiting, and stop behavior remain visible in the description and diff.

This operation requires a recognized template. A filled generic loop or condition
may cease to match its empty construction template; its existing structural and
Python editing tools remain available. Family grouping does not add wildcard
recognition of arbitrary program bodies.

### 19.2 Block Editor workspace

The desktop has a separate text-based definition editor. Collections, modules and
blocks appear on the left. A wide preview is above the Python source, using the
program's renderer; a switch shows the library card. Initially the preview shows
at most four source lines, with explicit expansion and a resizable divider.
Typing does not resize or move the editor. Preview values are independent of
template defaults and are never executed.

Built-in definitions are read-only examples with a copy-to-user-collection action.
The Catalog properties button edits category, family primary, variant label,
shared field keys, and optional additional fields in the same decorator source.
The dialog validates the module before one text edit; Save and apply validates
family references across the complete collection. Preview and ordinary text Undo
use the same source as all other property controls.
User modules have ordinary text editing, undo, template-aware highlighting,
context hints, source-located validation errors and recoverable invalid drafts.
Preview parameter/description clicks navigate to their declarations/docstrings.
The cursor selects the enclosing function; intervening text and invalid edits
retain the last valid preview. New blocks use action, expression or multi-command
starters. A program selection can become a draft, with explicit parameter choices.

The default personal collection uses the operating system's user data directory:
`$XDG_DATA_HOME/little-tinker-rig/blocks` on Linux, with the usual `~/.local/share`
default. All frontends automatically connect it without persisting its location
in every project. The directory is created on demand. Built-ins remain packaged
with source; external project collections may be connected explicitly. A group
field chooses the Python module. Icon and color controls are editable selectors
with localized meanings, semantic swatches and custom values. They edit decorator
literals with text Undo; no separate metadata store exists. Invalid drafts live
in `.drafts/*.py.json`. Saving validates the collection and checks external changes.
The library and help expose Open definition links.

Applying definitions refreshes recognition in connected documents and Scratch.
It never rewrites program source, commits program drafts, or alters their undo
histories. Unmatched old code remains ordinary Python; upgrades stay explicit.
Hub upload/run is disabled in the definition workspace.

---

## 20. Snippet versioning and upgrades

Snippet code can change between LittleTinker Rig/library versions. The system must avoid depending on fragile inline metadata in the Python source.

### 20.1 No per-snippet provenance markers in source

Do **not** insert comments such as:

```python
# @snippet package/name@1.2
...
# @end
```

The source must remain normal Python, robust under editing in external editors.

### 20.2 Collection versioning

Snippet collections must have an identity and version.

Multiple collections from different sources must be able to coexist.

Project-level knowledge of which collections are relevant may be stored outside the Python source if useful, but the exact project manifest format is still open.

Before editing a published collection, Start next version or the
`next-block-version` CLI command archives its saved modules and manifest under
`history/<previous-version>/`, validates a staged candidate and advances the
manifest version. Drafts must be resolved first. Snapshots are read-only in the
editor and included in distributions. Unregistered history directories are inert.
Version history starts with these explicit transitions; no reconstruction of older
development revisions or migration of personal directories is required.

### 20.3 Historical template matching

Recognition should first attempt installed/current snippet templates.

When a current template does not match, the system should be able to try historical patterns from older versions of the same snippet collection.

If a historical template matches, the editor can identify the code as an old form of a known snippet and offer an upgrade.

The source is still ordinary Python; historical matching is an optional enhancement.

### 20.4 Automatic upgrade by preserving bindings

If old and new snippet versions have compatible signatures and contracts, an upgrade can be generated mechanically:

```text
match old template
    -> extract placeholder bindings
    -> instantiate current template with the same bindings
    -> replace old source region
```

The desktop shows a diff before committing. Cancel preserves the source; Undo
restores the whole change, including managed helpers. Type/unit and
result/declaration contract changes require manual editing. Function blocks retain
one named implementation shared by all calls. Historical recognition compares
saved implementations and their imports. An explicit function upgrade replaces the
shared definition for every call; changed call signatures require manual editing.

### 20.5 Compatibility rule

For automatic upgrade, existing snippet parameters should preserve their meaning and signature compatibility.

New parameters may be added with defaults.

Breaking signature/semantic changes should be treated as a major incompatible change for which automatic upgrade is not guaranteed.

The exact versioning policy can follow this principle without overengineering a package manager initially.

---

## 21. Snippet help and documentation

Snippet documentation must not permanently consume editor space.

The Library panel should stay compact.

A snippet entry may show only:

- a compact name;
- optional small icon;
- optional concise signature/parameter hint.

Additional information should appear on demand:

- short tooltip/quick help on hover or selection;
- full documentation in a separate help window, tab, or dock opened explicitly (for example by an F1/help action).

A docstring in the snippet definition is the primary source of help text.

The same documentation source should serve Qt, TUI, and any future frontend.

---

## 22. Managed imports

Snippets may declare dependencies by placing imports inside their template-definition function.

For example:

```python
def create_motor(port):
    from pybricks.parameters import Port
    from pybricks.pupdevices import Motor

    motor = Motor(port)
```

These imports are metadata/dependencies for expansion and should be hoisted to the source import header rather than duplicated at the insertion point.

The main source should clearly distinguish imports managed automatically by LittleTinker Rig from imports written by the user.

A normal-comment convention should be used, conceptually:

```python
# --- automatically managed imports ---
from pybricks.parameters import Port
from pybricks.pupdevices import Motor

# --- user imports ---
import math
```

The exact marker text is not important yet; the principle is.

Rules:

- LittleTinker Rig may freely recompute, sort, add, or remove imports in the managed section.
- User imports outside the managed section must be preserved.
- Removing the last use of a managed dependency may remove its managed import.
- The markers themselves are ordinary explanatory comments, not hidden block metadata.

---

## 23. Types and units

String annotations use a type and optional numeric unit: "Motor", "int",
"number[deg/s]", "int[ms]"; alternatives use |. Numeric types are int, float and
number. Units are deg, deg/s, deg/s², mm, mm/s, ms, s, %, N and Hz. Generated
values remain ordinary Python values; units are never converted automatically.

The shared static model supplies field hints, suggestions, drag compatibility,
declaration/result inference and diagnostics. Compatibility has three outcomes:
compatible, incompatible, unknown. Known contradictory types/units are errors;
unknown dynamic values are allowed. A numeric literal adopts its field's unit.
This is conservative analysis, not a complete Python type checker or general
physical-units algebra. Existing unannotated assignments can match typed
creation templates without rewriting the program.

---

## 24. Names, completion, and lightweight static analysis

The editor should provide suggestions for names available at a source location.

Examples:

- local variables;
- function parameters;
- global variables defined before the location;
- imports;
- classes;
- known objects such as motors, sensors, and drive bases.

The editor should also diagnose obvious uses of unavailable/undefined names.

The initial implementation should exploit Python's existing AST/scope structure and keep the analysis lightweight.

A full external language server is not required initially.

Snippet placeholder metadata may narrow completion choices. For example, a placeholder expected to contain a motor should preferentially suggest names known to represent motors.

Deep type inference is not required. Graceful fallback to ordinary names is preferable to building a large custom type checker.

---

## 25. Core style guide and frontend-independent presentation semantics

The core should not contain Qt classes, terminal escape sequences, or HTML/CSS.

However, most of the **style semantics** should be shared so that different frontends express the same structural language.

The core should define or provide:

- semantic presentation roles;
- default palette guidance in backend-neutral colors such as RGB/hex values;
- which AST/snippet regions are structurally visible;
- which regions extend to visual line end;
- nesting/depth information;
- hover/selection semantics;
- foldable regions;
- placeholder semantics;
- snippet compound-region semantics;
- warnings/errors.

Frontends adapt these semantics to their capabilities.

For example:

- Qt can use translucent rounded backgrounds, padding, smooth folding animation, drag previews, and tooltips.
- The source-only TUI uses syntax highlighting and ordinary text selection;
  structural region styling does not apply to it.

The core owns the meaning; the frontend owns the rendering technique.

---

## 26. Core presentation output

A frontend should not have to reverse-engineer AST presentation rules independently.

The core may expose simple backend-neutral structural regions, conceptually like:

```text
region:
    source range
    line/column span
    depth
    semantic role
    whether background extends to end of visual line
    selected/hoverable/movable properties
```

This is not intended to become a heavy UI ViewModel layer. It should be a direct result of source/AST analysis.

The exact Python class names and representation should remain minimal and implementation-driven.

---

## 27. Undo and redo

Undo/redo is required.

Because typical educational and robotics source files are small, the preferred initial implementation is intentionally simple: store snapshots of logical editor state rather than building an elaborate reversible command/event system.

A logical state includes at least:

- the valid source projection and optional full-document Python draft;
- Scratch text and fragment identities.

After an atomic operation changes visible text or fragment identities:

- push the previous state to undo history;
- clear redo history.

Undo restores the earlier snapshot and its structural projection. Parsing an
unchanged draft does not add a history entry or clear Redo. Fragment identities
keep Scratch text widgets, cursors and modes attached to their own history.

This is expected to be simpler and more reliable than writing inverse transformations for every operation.

---

## 28. Architectural principle: elegant algorithms over reduced file count

The goal is **not** to minimize the number of source files.

The goal is to minimize total implementation complexity by choosing representations and algorithms that make problems disappear.

Examples of desired simplification:

- no separate block model: derive blocks from AST;
- no block/text synchronization: Python text is authoritative;
- no reverse-command framework: undo by snapshots;
- no verbose snippet schema: derive snippet metadata from Python functions;
- no custom migration scripts for ordinary updates: match old template, preserve bindings, instantiate new template;
- no separate drag algorithm per frontend: navigate common insertion targets;
- no duplicated style semantics: core defines roles/regions, frontend renders them;
- no full type checker when lexical/symbol analysis is sufficient.

Readability and clean module boundaries matter. Putting unrelated code in one large file is explicitly not considered simplification.

---

## 29. Proposed package structure

The project should use real subpackages for the core and each frontend/integration.

A reasonable starting structure is:

```text
little_tinker_rig/
    core/
        document.py
        syntax.py
        edit.py
        interaction.py
        snippets.py
        analysis.py
        presentation.py
        formatting.py

    qt/
        editor.py
        library.py
        scratch.py
        controller.py
        app.py

    tui/
        editor.py
        library.py
        app.py

    cli/
        main.py

    pybricks/
        connection.py
        run.py
        appdata.py

    snippets/
        python/
        pybricks/
```

This is a structural direction, not a requirement that every listed file exist from day one.

Modules should be split according to real responsibilities and readability, not to satisfy a predetermined layer count.

If two modules constantly need each other's internals, their boundary should be reconsidered. If one responsibility grows independently, it should be separated.

---

## 30. Core code requirements

The core should be:

- independent of Qt;
- independent of any TUI library;
- independent of Pybricks;
- directly testable without a UI;
- mostly based on Python standard-library facilities where practical;
- explicit and readable;
- small because the algorithms are simple, not because code is compressed or hidden.

Prefer:

- plain functions;
- small dataclasses where they clarify data;
- direct composition of operations;
- derived data instead of cached duplicated state;
- narrow interfaces with obvious semantics.

Avoid introducing abstractions such as repositories, services, model/view adapters, event buses, or generalized plugin frameworks unless a concrete need appears.

A useful rule for new abstractions:

> Introduce an abstraction only if it removes real duplication between frontends/integrations or represents a real domain concept.

---

## 31. Multiple frontends as an architectural test

Qt is the primary teaching interface; TUI focuses on source editing and Pybricks
operations. Share source-file safety, static Python assistance and hardware
services. Structural editing remains independent of Qt and is exercised by the
CLI and core tests; TUI does not need matching structural features.

The desired split is roughly:

```text
core decides:
    what is selected
    what can move
    where it can move
    what a snippet means
    what names are available
    what regions and roles exist
    what state results from an edit

frontend decides:
    how the user expresses the action
    how regions are drawn
    how animation works
    how mouse/keyboard events are captured
    how dialogs/tooltips are presented
```

---

## 32. Qt frontend

The Qt frontend is the rich desktop UI.

Preferred toolkit: **PySide6 / Qt**.

It should provide, as the design matures:

- three-column Library / source / Scratch layout;
- rich structural background rendering;
- smooth drag-and-drop;
- explicit folding/collapse animation without drag-induced folding;
- tooltip quick help;
- separate full documentation view;
- virtual joystick/buttons/sliders;
- run/stop/connect controls;
- console output;
- settings and project controls as needed.

The Qt frontend should be thin: it consumes core structural/presentation data and translates GUI gestures into core interaction operations.

Qt must be optional. Installing the core/TUI must not require downloading Qt.

---

## 33. TUI frontend

Textual provides a lightweight terminal workspace for Python and Pybricks. Qt,
OpenGL and gamepad libraries are not required. The optional `tui` dependencies
include Jedi, Pybricks API descriptions and Python-only Tree-sitter highlighting.

- Edit ordinary Python with highlighting, indentation, undo/redo, find/replace,
  completion and signature/documentation help.
- New, Open, Save and Save As preserve text, including invalid drafts and line
  endings. Read legacy Python encodings; write UTF-8 without a BOM and normalize
  active encoding declarations through the shared persistence utility and editor
  undo history. Detect external changes and confirm overwrites; never rebuild
  imports, helper functions or block workspace metadata while saving source.
- Connect using Bluetooth by default, supported USB, or a virtual hub.
- Upload, upload-and-run, run uploaded code, stop and disconnect are distinct
  actions. Save and check syntax before transferring the current source.
- Show connection state, operation progress, program output and physical hub
  input. Runtime error navigation checks against the uploaded source snapshot.
- Prepare and review cached/downloaded/local firmware, then install it in an
  isolated process with the same validation and instructions as Qt.
- Start the port monitor explicitly: on physical hubs it stops the user program
  and can replace the stored program. Show telemetry in a compact table.
- Provide keyboard commands and English/Russian captions.

TUI does not provide Library, structural block editing, Scratch, lessons or 3D
assembly. Hub operation serialization and cancellation live in a shared worker;
frontends adapt its callbacks rather than maintaining separate implementations.


---

## 34. Headless CLI

A headless CLI is required from the beginning.

It is useful both to users and as the easiest way to test almost all substantive logic without starting a UI.

Potential commands include operations conceptually equivalent to:

```text
inspect a file
show AST/structural regions
list recognized snippets
show diagnostics
apply snippet upgrades
perform structural edits for tests
run a file on a configured backend
```

The exact command syntax is not fixed.

The important requirement is that parsing, snippet matching, source transformations, imports, analysis, and most interaction logic can be exercised headlessly.

---

## 35. Packaging and optional dependency weight

Users should be able to choose how heavy an installation they want.

A suitable packaging model is one Python distribution with optional extras, conceptually:

```text
little-tinker-rig                 -> core + CLI
little-tinker-rig[tui]            -> TUI dependencies
little-tinker-rig[qt]             -> PySide6 GUI
little-tinker-rig[pybricks]       -> Pybricks host integration
little-tinker-rig[gamepad]        -> optional physical-controller support
```

Exact extra names are not fixed.

Key requirement:

> A user who only wants the terminal frontend must not have to install Qt.

Likewise, generic Python structural editing should not require Pybricks packages.

---

## 36. Pybricks integration philosophy

Pybricks runs on the hub.

On the computer, the preferred implementation is to reuse the existing Pybricks host-side Python library/protocol implementation rather than reproducing the wire protocol ourselves.

Current preference:

> Use the Pybricks host Python library (`pybricksdev` or its current equivalent) if its API is practical. Reimplement the protocol only if that proves materially simpler or necessary.

The host integration belongs in a separate optional `pybricks` subpackage.

The structural editor should not know how BLE/USB works.

---

## 37. Pybricks host-side responsibilities

The Pybricks integration should expose a small, stable project-local API for the rest of LittleTinker Rig.

It needs to support at least the concepts of:

- discover/connect to a hub;
- upload/run the current Python program;
- stop a program;
- receive console/output data;
- send low-latency application/control state where supported;
- handle reconnection/errors cleanly.

The exact wrapper API should remain thin and follow what the underlying Pybricks library already provides rather than abstracting hypothetical future transports.

BLE/USB transport details stay inside this integration.

The GUI captures process stdout/stderr for its lifetime through a queued Qt
signal, including pybricksdev transfer progress from the hub worker. Carriage
returns update a console line instead of accumulating terminal control characters.
Upload/Run open the console; hub operations show an indeterminate activity bar
until completion, cancellation or failure. Program stdout continues through the
transport's public observable. Scratch and Hub and devices are tabified docks;
switching an inactive tab must not record it as explicitly closed.

---

## 38. Virtual controls and physical controllers

A major requirement is support for screen-based interfaces similar in spirit to the controls used by LEGO BOOST-style applications.

Examples:

- virtual joystick;
- buttons;
- sliders;
- simple custom control panels.

A physical controller should be usable as an alternative input source.

The architectural principle is that the robot-side program consumes a normalized control state, not a Qt widget or a particular gamepad API.

Conceptually:

```text
Qt virtual joystick ----+
                        |
physical gamepad -------+--> normalized control state --> Pybricks connection --> hub
                        |
keyboard ---------------+
```

`ControlState` defines four axes in `[-1, 1]`, two triggers and a legacy slider
in `[0, 1]`, and a 16-bit button mask. The
[hub/input API](../doc/en/api.md#hubs-and-input) specifies its stdin frames.

The controller input implementation should be optional so that users who do not need physical gamepads do not inherit unnecessary dependencies.

The optional `gamepad` extra uses pygame-ce's SDL controller API. Its input is
normalized to the same state as the screen controls.

---

## 39. Source-side controller API

The bundled `little_tinker_rig_controller.py` helper is ordinary Python. Generate
it beside a hub program with the CLI `controller` command. Call `update()` on
each control-loop iteration:

```python
controller = Controller()

while True:
    controller.update()
    drive.drive(
        controller.left_y * 500,
        controller.left_x * 120,
    )
    wait(20)
```

The helper uses Pybricks `read_input_byte` and owns stdin. Stale input becomes
neutral after 500 ms; the program must apply that state to its motors. Import
`Controller` from the generated module and `wait` from `pybricks.tools`. See the
[control guide](../doc/en/robotics.md#manual-control) for a runnable example.

The important point is that virtual and physical controllers should feed the same conceptual state.

---

## 40. Library panel behavior

The Library is the source of available snippets.

It should support:

- grouping by collection/module/category;
- compact browsing;
- search/fuzzy search where practical;
- drag/drop insertion in Qt;
- keyboard insertion in Qt;
- concise display rather than large permanent previews.

A snippet should be usable without opening its full documentation.

Hover/selection may show quick help. Full documentation is explicitly separate.

---

## 41. Snippet recognition in existing source

Snippets are not only inserted from the Library.

When opening any Python file, the editor should scan its AST and identify regions matching known snippet templates.

This allows ordinary source written externally to gain enhanced LittleTinker Rig presentation automatically.

Recognition is optional and non-destructive:

```text
recognized -> enhanced compound block
not recognized -> generic Python structural blocks
```

No source rewriting is required merely to recognize a snippet.

---

## 42. Editing externally

External editing is a supported workflow.

A user may:

1. save a normal `.py` file from LittleTinker Rig;
2. edit it in another editor;
3. reopen it in LittleTinker Rig.

LittleTinker Rig reparses the source from scratch.

Possible consequences:

- generic AST structure is always recoverable from valid Python;
- snippet recognition may change depending on how closely code matches templates;
- old snippet forms may be detected using historical patterns;
- no editor-specific source markers need repair.

This graceful degradation is more important than perfect preservation of every enhanced visual annotation.

---

## 43. Error handling and validity

The structural projection maintains a strong invariant:

> Between committed structural operations, the block document is syntactically valid Python.

Structural edits must be atomic.

A failed edit should leave the previous source unchanged.

Removing or detaching a standalone expression removes its owning statement.
Only an expression used inside another construct leaves `...`; an emptied suite
retains `pass`. Deletion and transfer must use the same removal semantics.
Expression replacement introduces parentheses only to preserve the intended AST.

Python text editors share static Jedi completion and signature/documentation hints,
including installed Pybricks API descriptions. Analysis uses one background queue,
coalesces pending requests and never executes user source. Suggestions belong to
one source/cursor/path revision; editing, navigation and cancellation invalidate
old results. Both source editors use the shared analysis module; importing the
structural core alone does not require Jedi.

Full-document Python editing may contain unfinished text. Save writes that text to
the ordinary `.py` file, which reopens in Python view. Run, Upload and switching to
Blocks require valid syntax. Local structural edit dialogs still reject invalid
commits. Text persistence must not depend on structural validity.

All program saves use UTF-8 without a BOM. Opening detects the original Python
encoding; saving normalizes an active first- or second-line encoding declaration.
The editor, persisted bytes and reopened text agree, including for invalid drafts.
The declaration change participates in the active editor's undo history.

Desktop recovery checkpoints preserve open tabs, unsaved text, Scratch, collection
settings and the original save baselines. They are separate from source files,
written atomically and protected by per-window process locks. Recovery is offered
after an abnormal exit, never overwrites disk sources, and retains external-change
checks. Conflicting unsaved versions open separately. Checkpoint ownership moves
only after the replacement is durable; normal close removes the window checkpoint.
After restoring a structural revision, rebind selection before refreshing views.

Runtime errors carry immutable uploaded source snapshots, including local modules.
Known failures have localized explanations and source navigation. Managed helper
frames prefer the calling user block. If source has changed, show the executed
snapshot read-only instead of attaching an old line number to the new source.
Keep complete tracebacks and unknown messages; user stop interrupts are not errors.

The desktop File → Examples submenu discovers bundled programs recursively.
First opening creates a persistent local attempt with imported Python modules;
subsequent openings resume the last explicitly opened attempt. Start again creates
a new attempt; My attempts exposes older ones. Attempts autosave Python and Scratch
through Project, including invalid text, and survive normal close. Save As retains
the attempt identity and relocates its modules without overwriting conflicting
files. The local work manifest records origin and paths, not a second catalog of
available examples. Bundled source remains unchanged.

Static diagnostics such as undefined names may remain warnings and do not necessarily block commits, because they are semantic rather than syntax errors.

---

## 44. Testing strategy

Core behavior must be testable without Qt or TUI.

Important test targets include:

- AST/source range construction;
- deepest-node lookup;
- parent/child navigation;
- structural move operations;
- correct reindentation;
- preservation of syntactic validity;
- formatter round trips;
- snippet parsing;
- snippet matching and placeholder binding;
- snippet instantiation;
- hygienic local-name renaming;
- historical-template recognition;
- snippet upgrade by rebinding;
- managed imports;
- scope/name analysis;
- Scratch-to-main validation;
- undo/redo snapshots;
- presentation region generation.

Qt tests concentrate on translating gestures into structural operations. TUI
tests protect source preservation, keyboard actions and hub workflows. Shared
hardware and file operations are checked independently of either frontend.

---

## 45. Implementation style requirements

Code quality is a first-class requirement.

The implementation should favor:

- readable Python;
- clear module structure;
- small cohesive functions;
- algorithms that exploit Python's real syntax/AST properties;
- minimal duplicated state;
- minimal duplicated logic between frontends;
- ordinary language/library mechanisms over custom frameworks;
- mature dependencies where a dependency is justified;
- optional heavy dependencies;
- explicit failure modes.

Avoid clever compression that reduces line count at the expense of readability.

Avoid architectural boilerplate that exists only to satisfy patterns.

The desired style is the solution a lazy but highly productive engineer would choose: find the representation that makes the problem simple, then write the minimum clear code needed to express it.

---

## 46. Dependency policy

Dependencies should be few, mature, reliable, and optional where possible.

Current intended dependency categories:

### Base/core

Prefer Python standard library plus one canonical formatter.

### Qt frontend

PySide6 / Qt.

### TUI frontend

Textual, Jedi, Pybricks API descriptions and Python-only Tree-sitter highlighting.

### Pybricks integration

Use the existing Pybricks host-side Python library where practical.

### Physical gamepads

Optional pygame-ce dependency through the `gamepad` extra, using its SDL controller API.

Do not introduce browser runtimes, JavaScript build systems, Rust sidecars, local RPC daemons, or similar layers unless a concrete later requirement justifies them.

---

## 47. Important invariants

The implementation should preserve these invariants:

1. **Python source is the truth.**
2. **A normal `.py` file must remain useful outside LittleTinker Rig.**
3. **No per-block/source provenance tags are required for correctness.**
4. **AST/block presentation is derived from source.**
5. **The structural projection is syntactically valid Python.**
6. **Full-document Python drafts and Scratch may be syntactically invalid and saved.**
7. **Structural edits are atomic.**
8. **Snippet recognition is an enhancement, never a requirement for execution.**
9. **Unknown/modified code degrades to generic Python blocks.**
10. **Heavy UI/hardware dependencies are optional.**
11. **Qt and TUI share file safety, Python assistance and Pybricks operations.**
12. **Style semantics are shared; rendering mechanics are frontend-specific.**
13. **Undo/redo is required.**
14. **Managed imports are clearly separated from user imports.**
15. **Snippet definitions should be concise Python, not verbose metadata schemas.**
16. **When data can be reliably derived, do not persist duplicate state.**

---

## 48. First implementation milestones

This section records the initial implementation sequence. It is historical
delivery guidance, not an outstanding task list. The current behavior is described
in the corresponding contracts and the [developer guide](../doc/en/development.md).

### Milestone 1: structural core

Implement:

- load source;
- canonical format hook;
- parse AST;
- build parent/child/source-range index;
- deepest-node lookup;
- semantic presentation roles;
- structural selection/navigation;
- snapshot undo/redo.

Expose through CLI inspection commands.

### Milestone 2: minimal Qt structural view

Implement the desktop structural view with:

- source display;
- structural highlighting;
- selection and parent/child navigation;
- simple fold visualization;
- no robotics requirement yet.

This validates that core behavior is truly frontend-independent.

### Milestone 3: structural movement

Implement:

- legal insertion-target generation;
- move preview state;
- move commit/cancel;
- reindentation;
- formatting and reparse;
- Qt mouse drag mapping;
- Qt keyboard mapping.

### Milestone 4: Scratch workspace

Implement:

- move selected region to Scratch;
- dirty Scratch fragments;
- restore valid fragments to main source;
- placeholders such as `pass` where needed.

Persistence details can remain simple initially.

### Milestone 5: snippet engine

Implement:

- parse snippet-definition functions without executing them;
- extract parameters/defaults/docstrings/imports/template body;
- statement and expression snippets;
- AST template matching;
- placeholder binding;
- instantiation;
- compound presentation;
- loss of recognition after structural modification;
- simple local-name hygiene.

### Milestone 6: Library and help

Implement:

- snippet grouping;
- compact Library UI in Qt;
- insertion;
- tooltip/quick help in Qt;
- explicit full help view;
- keyboard access to help in Qt.

### Milestone 7: imports and lightweight analysis

Implement:

- managed-import section;
- preservation of user imports;
- lexical name availability;
- undefined-name diagnostics;
- completion suggestions;
- simple annotation/unit metadata.

### Milestone 8: versioned snippet collections

Implement:

- collection identity/version;
- historical AST patterns;
- old-template recognition;
- compatible-signature upgrade by preserving bindings.

Project collection paths and version pins now use the `.py.ltr.json` workspace
format described in section 7.2.

### Milestone 9: Pybricks integration

Implement optional Pybricks host integration:

- connect;
- run/upload;
- stop;
- console;
- application/control data transport as supported by the host library.

Add built-in Pybricks snippets.

### Milestone 10: controls

Implement:

- Qt virtual joystick/buttons;
- normalized control state;
- transfer to a running hub program;
- optional physical controller source.

---

## 49. Open decisions

Possible extensions remain open until a concrete task needs them:

- Additional terminal workflows beyond the source-and-hub scope.
- Distribution of external collections beyond the directory-based format.
- Extensions beyond the current string type/unit grammar.
- Whether a presentation-intensity control would improve the existing Blocks / Python views.

The following earlier questions are resolved and must not be treated as missing
implementations:

| Decision | Current contract |
|---|---|
| Formatting | Ruff public CLI; see [formatting and latency](../doc/en/development.md#interactive-latency) |
| Scratch, collection paths and pins | `.py.ltr.json` workspace; see [file API](../doc/en/api.md#documents-and-sessions) |
| Historical templates | Manifest `[[history]]` entries and archived definitions; see [collection versions](../doc/en/snippets.md#starting-a-collection-version) |
| Recognition conflicts | Larger regions first, then fewer contract mismatches, greater specificity, current before historical forms, and stable identity; see `recognize` in [snippets.py](../little_tinker_rig/core/snippets.py) |
| Comment ownership | Source-attached comments and separate definition display; see [editor views](../doc/en/usage.md#documents-and-views) |
| Hub adapters and controller state | Public pinned pybricksdev adapters, bundled Controller helper and optional pygame-ce; see [hub/input API](../doc/en/api.md#hubs-and-input) |
| Palette and interaction feedback | Shared semantic roles and current [UX contracts](UX_DESIGN.md) |

---

## 50. Final design summary

LittleTinker Rig should be built around a very small set of strong ideas:

- Python source is the program.
- The AST turns Python into manipulable structure.
- Structural blocks are source ranges, not a second model.
- Indentation plus semantic backgrounds can provide a Scratch-like visual hierarchy while showing real Python.
- Structural commits remain syntactically valid; full-document Python and Scratch may contain saved unfinished text.
- Drag-and-drop is generalized as navigation through legal structural insertion targets.
- Block definitions are statically parsed Python functions. Decorators specify inline substitution or a generated helper call, level, appearance and editable declarations. Signatures and annotations specify fields and type/unit contracts; docstrings and imports provide help and dependencies.
- Snippets are recognized structurally in ordinary Python source.
- Snippet versions are handled by collection versioning and historical AST matching, without adding per-snippet markers to source.
- Compatible snippet upgrades are generated by extracting old bindings and instantiating the new template.
- Auto-managed imports and shared helpers have separate sections marked by ordinary comments; their lifecycle follows references in the program and Scratch.
- Scope analysis provides lightweight completion and undefined-name checking.
- Style semantics and interaction primitives live in the core; Qt, TUI, and CLI are thin independent frontends.
- Qt and TUI share source-file safety and hardware services while keeping different editing scopes.
- Heavy dependencies are optional.
- Pybricks is an optional execution/domain integration rather than part of the editor core.
- Virtual and physical controllers feed a shared normalized control state.
- Code volume should be reduced by representation and algorithmic simplicity, not by collapsing modules or hiding complexity.

The project should feel like ordinary Python that has acquired structure, constraints, discoverability, drag-and-drop, and domain-specific intelligence, rather than like a visual language that happens to generate Python.

## Desktop library and hub actions

Every block has one decorator level: beginner, intermediate, advanced, or expert. All exists only
as a filter choice. Levels are cumulative and a fresh installation starts at
Beginner: nineteen family cards for motor/sensor and robot setup, bounded moves, waits,
repetition, console feedback and complete line/remote activities. Intermediate
adds decisions, readings, hub feedback, variables, arithmetic and reusable
functions. Advanced adds collections, numeric helpers, curves, steering cars and
individual remote operations. Expert adds exception handling and raw motor duty.
Legacy standard settings and manifests migrate to intermediate. Above Beginner,
groups start collapsed; search expands matching groups and restores their prior
expansion when cleared. Python view is the
path to broader language/API features; levels never restrict editable source.
Search, category branches, and persisted icon-only level buttons combine; help retains
module groups and the same source definitions. Independent view buttons open
Catalog, Favorites, Recent, Frequent, and For this task. Exact variants are
selected through context menus; category expansion controls share the view row.
Names remain in localized tooltips and accessible labels. Each family card shows
its own clickable favorite star, filled when selected. Exact variants are
filtered before a family produces one card. Personal records are local family
references; saved document functions use their resolved source path as scope.
An unnamed document uses a unique recovery-persisted identifier. Its first save
moves personal references and counts to the saved path; later Save As starts a
separate scope. Recent
and Frequent show at most twelve families. Daily counts cover the current and
previous 29 UTC days; ties use latest insertion time and identity. Frequent stays
a snapshot until the view is entered again. All successful catalog insertion
paths, including both Scratch paths, record a use after the edit succeeds.
Undo retains that use, and redo does not create another. Favorites retain their
manual ordering and unavailable references independently of usage resets. Display-only titles place the action symbol before text,
use the owning block's color, and preserve enclosing indentation bands. Titles
precede all owned comments and use the editor's normal font size.

Hover and selection increase HSL saturation and moderately reduce lightness at
fixed hue and opacity. Saturation alone cannot distinguish already-pale saturated
colors sufficiently; verify the final composited contrast, not only HSL values.
Each pixel retains its most specific block's color, including under an active
ancestor; comments and code use the same region pass. Never stack dark selection
overlays on the base colors. The shared transform resolves both changes before
painting a region, preserving each descendant's hue and comment ownership.

Prepared actions use ordinary helper functions and native Pybricks operations.
Declarations and language constructs remain inline. Function calls evaluate
arguments once and isolate implementation locals. Their source can be viewed
without inlining the call or changing its behavior.
Expansion is a temporary editing view and is recalculated after source changes;
separate use/unpack level metadata is not implemented. Shared helper lifecycle is implemented. General events, gait frameworks and
host media blocks remain deferred.
Sensor/motion activities specify termination and brake in Python cleanup. Direct
remote pairing and steering-stop calibration are hardware capabilities, not
features of the virtual physics model.

Set-specific examples in `examples/pybricks` preserve upstream command semantics
while using bundled blocks for every device operation. Shared sequences become
ordinary activity templates, not hidden per-example dependencies. All 37 Python files from the supported upstream families are cataloged at a pinned
revision, with set-number filenames, dependencies and validation status. EV3 is
excluded. Gelo remains a visible shared module; REPL/reference files retain their roles.
Website project downloads and inline menu programs have a separate source
inventory including exclusions, hashes, hardware requirements and attribution.
Shared libraries stay beside importing programs; multi-hub crane programs are
independent entry points, not import dependencies. Radio uses Pybricks 4; vision
programs require an external host. The simulator does not claim either feature.
Community control schemes may be reimplemented with explicit behavioral changes,
separate attribution and pinned reference sources. The 42100 excavator has two
independent programs using existing blocks: Xbox/base and upper mechanisms.
Their radio protocol carries a model tag, changing sequence and signed commands;
the receiver brakes on invalid input or a 500 ms sequence timeout. Slow mode,
stop controls and motor limits are documented beside the examples in EN/RU.
Scripted virtual tests cover commands and failures; they do not establish physical
travel limits or radio reliability. Xbox button choices share the editor's enum
catalog with the scripted virtual runtime, including face buttons and bumpers.
Community imports record a pinned original URL, source hash, author, redistributable
license and explicit behavioral changes. Source links also live in each program.
Sensor lessons and Xbox/LEGO remote programs reuse existing palette blocks; custom
mechanics include ports, dimensions, motor directions and startup positioning.
Controller inputs are percentages: mixing must keep motor duty within its declared
limit. Mode changes stop inactive actuators, toggles use button edges, and missing
ultrasonic measurements do not become full-speed following commands. Async examples
await device I/O and explicitly stop motion when a race finishes or fails.
These invariants have short scripted runtime checks, separate from compilation,
block rebuilding and physical verification. The community review records duplicate,
incomplete and out-of-scope sources instead of presenting them as working examples.
Four prepared activities join Beginner; homing and steering centering start at
Intermediate, with controller settings and background targets at Advanced.
Check coverage without generic catch-all assignments, rebuild library fragments,
and compare command traces with scripted virtual inputs. Keep upstream revision,
attribution, API migrations and hardware limitations beside the examples.

The toolbar omits Parameters, To Scratch and Python fragment; menus and shortcuts
retain these actions. Upload sends the active source snapshot without running.
Run sends and executes the snapshot; neither asks for a filename or saves ordinary
files. Open imported modules supply their current text. Recovery is flushed before
submission; runtime diagnostics retain original paths and executed text.
Run stored program starts the existing hub program;
Stop halts execution. Physical uploads contain compiled code without an additional
source archive. Source read-back and bytecode decompilation are out of scope.

Firmware installation is a desktop workflow with model, kind and version selection,
local packages, cached official downloads, package review, progress and errors.
Inventor/Prime uses USB DFU; BOOST and Technic use Bluetooth bootloaders. Model
compatibility is checked before erase. LEGO downloads provide Inventor/Prime
recovery 1.3; BOOST/Technic restoration requires a local compatible LEGO package.
Automation prepares images and tests public transport boundaries; physical flashing
requires separate hardware verification.

Stable is the default firmware channel; Beta explicitly exposes prereleases and
release notes in Qt and TUI. New USB Serial firmware uses the Pybricks 1.6+ SPIKE
COBS protocol through a shared native serial adapter. BLE remains the connection
default and the legacy USB adapter remains available. Inventor/Prime and EV3 use
the same serial workflow; EV3 is experimental and has no hardware verification,
port monitor, simulator or Bluetooth Classic transport yet.

Metadata v3 firmware variants are validated during preparation and selected by
the actual hardware at install time. Public Pybricks flash tools and the required
second-stage bootloader are pinned and verified in the user cache. New beta
flashing requires libusb. On F4, restoring stable/LEGO firmware requires entering
the original bootloader with the Bluetooth-button USB sequence. Incompatible
bootloader revisions must be rejected before erase.

### USB adapter ownership and access diagnostics

BLE, legacy USB and firmware installation use public Pybricks implementations.
USB Serial is a temporary compatibility layer until pybricksdev provides a public
adapter for the current protocol; identifiers and compilation remain upstream-owned.
EV3 shares the serial protocol but remains experimental until hardware verification;
initial physical checks target Inventor. Existing EV3 Linux/SD-card systems are excluded.

Serial-open failures retain their system error and receive localized, actionable
instructions. Linux advice inspects the actual port group and mode, registered
membership and current process groups. Only serial-specific groups can produce an
add-membership command. Stale sessions require a fresh login; other restrictions
require administrator review. The app does not modify system permissions. Upstream
udev rules are obtained from pybricksdev, never copied into this repository. Qt
provides offline USB help and error copying; the same diagnosis reaches TUI and CLI.

### Cancellable hub connections and persistent firmware cache

The hub connection action distinguishes connecting, connected and disconnecting.
The toolbar hub button and F7 cancel a pending connection or disconnect an active
one; they never open the port monitor. A connection attempt has a 20-second deadline.
Cancellation finishes transport cleanup before enabling a new attempt; late callbacks
cannot revive the cancelled connection. A child process owns native USB resources,
allowing termination when driver discovery or a handshake blocks indefinitely.

Firmware catalog and archives persist in the platform user cache. Opening the
firmware dialog reads the saved catalog; only explicit refresh accesses releases.
GitHub API rate limiting records a retry deadline and falls back to the public
release feed, retaining known asset hashes and older cached versions. Network
failure leaves the saved catalog available. Archive URLs identify cached downloads
across channels and restarts; preparation reports cache reuse or download in the UI.

### Structural expression and function editing

The desktop exposes expression leaves, call receivers and callees, function names,
parameters and operators as fields derived from source. Calls, definitions and
Boolean operations share insertion, removal and reordering of list items; calls
and definitions allow zero items, while `and`/`or` keep at least two operands.
Explicit expression replacement and wrapping preserve grouping and evaluation
order. Occupied fields remain protected against accidental drag replacement.

Public subexpressions are independently selectable and highlighted only while
active. A contextual chooser composes, replaces and wraps expressions; list tools
also cover collections and comparison chains. `...` denotes an unfinished input,
survives save/recovery/Undo and blocks Run/Upload until filled; `None` remains a
normal value. Local search, palette filtering and drops use the same type/unit
compatibility contract, retaining unknown types. Ambiguous statement inputs require
an explicit destination choice. Keyboard navigation visits public inputs, and
Escape selects the enclosing statement; explicit pinned catalog search remains
active until its back action or source/catalog invalidation.

Building representative bundled programs from scratch is a one-time manual design
review, with findings in `AI`. Recurring tests protect focused semantic and UI
invariants, without replaying full GUI construction scenarios.

Module-level user definitions contribute a transient My functions library group.
Calls without a returned value are statements. Return values and generators make
expression cards; result annotations are respected, and decorated functions have
unknown results. Returns inside nested definitions do not classify their parent.
Selecting a `pass` insertion hole takes precedence over its enclosing recognized
template when adding actions from the library.
Definition renames follow resolved lexical bindings, including known keyword
calls. Signature changes retain existing call sites. Proven argument mismatches
have a red frame and a generated error-comment row; unknown dynamic signatures
are not treated as errors. Syntax validation and one-step Undo apply to all edits.
The Beginner range block fixes `range` and exposes the counter/count; the Intermediate
variant exposes start, exclusive stop and step as well.

Block titles are interface elements; source comments retain their `#` prefix.
The enlarged icon and title may align with a nested expression without
increasing row height. They share backgrounds, ancestor bands, hover, selection
and ownership hit testing with code. Origin and destination markers use explicit,
contrasting colors; the origin starts at the moved block's former indentation.
Library search matches all query words across the complete localized help, source,
name and group.


### Block context navigation and repeated fields

Recognized inline blocks have an upper-right A/P/D button. A click cycles Auto,
Program comments, Definition comments, then Auto without opening a menu.
Auto uses program comments when the block owns comments in the program;
otherwise it uses definition comments. Blank lines do not choose a mode.
All modes preserve actual program code, names, annotations, parentheses and code
layout. Definition comments are attached to corresponding AST owners, never used
to regenerate code. Expressions have no extra permanent nesting decoration;
their selected or hovered span uses the common block color pass.
Each block's choice is independent and retained through parameter edits in the
open view. Switching is a source-mapped presentation change, never a document
commit. Hover, parameters and drag/drop resolve to the original logical owner.
Definitions retain their source text alongside the AST. Inline insertion emits
code without explanatory comments; function definitions preserve their comments
in the managed helper section. Function blocks always show the actual call and
its program comments; their bodies are inspected through Open definition or Python
view. The comment-source switch applies to inline blocks. Program comments and
definition comments are never merged automatically.

The program and Scratch context menus target the block under the pointer, including
its generated comment. Open definition carries the recognized Snippet object so a
historical match opens the exact source path/version read-only. Built-ins are
read-only; current user definitions remain editable. Help, expansion, duplication,
Scratch transfer and deletion share the normal editor operations and undo history.
Expression-editing submenus remain available over parameter fields.

Repeated field occurrences are indexed by (matched block, parameter name), never
by source text. Hover and active editing highlight the group and show its use count.
Editing any occurrence commits all occurrences once; Escape changes nothing.
Inline expressions still evaluate at every use, while function-block arguments
evaluate once. UI synchronization does not change Python evaluation semantics.

### Optional lessons and assembly workspaces

Workspace navigation stays on the left in a 48-pixel strip with centered 24-pixel
SVG icons and 48-pixel rows. Names appear only in localized tooltips and remain
available to assistive technology. Language and font changes do not widen the
strip. When height is limited, the list scrolls without changing the current
workspace. Assembly is also available independently. A lesson project shows a
full-height right task panel in every workspace, collapsible to a progress
control beside hub connection. At narrow widths the panel opens as an overlay
without shrinking the editor; Scratch shares the right dock area on wide windows;
ordinary files show neither. Hidden modes cannot be selected from the keyboard.
Dimensions use logical pixels for display scaling.

Lessons (`.pylesson`) are immutable, localized materials with goals, stages,
progressive hints, recommended block identities and explicit completion criteria.
Student projects (`.ltr`) snapshot these materials together with ordinary
Python files, per-file Scratch, editor state and lesson progress. The writable
working directory belongs to the user data directory. Archives are atomic, detect
external modifications and retain unfinished Python. Recovery retains archive
save baselines; for a retained attempt, the working copy's record of a successful
save takes precedence over an older window recovery checkpoint. Template attempts
remain in user data across normal close.

Bundled Pybricks exploration projects reuse licensed example programs through explicit file
references; packaging resolves them into immutable lesson resources. The `programs`
mapping creates independent student copies, including shared modules and licenses,
and `main` selects the entry point. Named stage programs and `program:` document
links reopen the existing copy, preserving unfinished edits. Localized Markdown
sections provide stage descriptions without one file per short page. Guided
lessons and exploration projects occupy separate menu groups; localized activity
groups form submenus, and nested directories are discovered recursively.
Only explicitly licensed repository material is reproduced; website-only content
and heavy media remain external links. No assembly sequence is inferred from a
project page. Console input supplies line or focused immediate-key input to a
physical hub, serialized with other writes and unavailable during port monitoring.

Selecting a task title opens its section in the same Help document, changes
recommendations, and reveals its card. Other cards remain compact with their
checkboxes, titles, and points visible. Checking a task changes completion only;
it does not change the selected task or workspace. Opening a starter creates one named document
in the current project and reopens that document on later clicks; it never
replaces another document, including unfinished Python drafts.
Visiting an assembly step, changing a camera or viewing a hint never completes a
physical task. Manual completion and observable device checks remain distinct.
Each device-checked task names at least one distinct robot device. Robot devices
have unique physical ports; a monitored connection must report the expected type
on every required port before the task can be marked complete.
A right-side task panel shows the selected task's Markdown, revealed hints,
links and completion status across workspaces. Help shows the whole localized
lesson instruction file from the top on first open, or at the selected task
when an attempt is resumed. The lesson
has one tree entry; task Instructions links scroll that same document to the
selected task's stable section anchor without creating section leaves. Legacy
stage files are combined into one navigable document at runtime.
Instruction links do not open a dialog. At narrow widths they temporarily hide
the task overlay without changing the saved panel preference. The document has
an inline task list and in-document Find; reading another section does not select
its task. The Help tree keeps one lesson leaf and no section leaves.
Completion does not navigate; completed tasks have checked rows and earned points.
Assembly stages also expose an `assembly:` link at the start of their description,
so instructions remain reachable when the task panel is collapsed. Opening a stage
description scrolls to its anchored section after layout and formatting. Both entry points
select the active lesson's robot and preserve its step within the stage range,
independently of any separately opened robot instructions.
Hints and starter actions are available only where authored. Opening a saved project shows its instructions in Help,
including when its document is already open. Hub callbacks after closing must not
read removed project resources.

The assembly viewer consumes a robot description and progress state, not a student
project. Independent instructions and the active lesson have separate viewers and
state; only the lesson viewer updates lesson progress. Independent assembly stores
its last model, step and camera in user settings and loads resources lazily.
Robot descriptions may declare a localized title. The model chooser appears only
for multiple open models; opening instructions belongs to File and the empty viewer.

The For this task library view shows task recommendations, including blocks above
the selected level. It does not restrict normal catalog search, contextual
expressions, Scratch, editing, or existing source. The full catalog remains
available while the task panel is open.
The main toolbar uses 24-pixel icons with localized tooltips and shortcuts;
hub name and connection status retain text. Multiple programs can belong to one
project; saving any of them saves the project's open programs and progress together.
Explicit input searches expose a back button restoring the previous catalog view
and search. Hover and parameter selection do not change the catalog. Inline
fields consume their commit key: Return must not also invoke the parent editor's
expression chooser.
Qt's automatic focus traversal when a child field closes is not structural
navigation; it must preserve the edited argument selection. Delete and the block
context menu share the same extraction operation and Undo transaction.
Window shortcuts and the focused editor route Escape through the same cancellation
and whole-block selection handler.

Robot models use LDraw/MPD geometry. Original models and instructional materials
belong to the lesson. Small community MPD assemblies may be bundled when their
licenses explicitly allow redistribution and adaptation; retain source URLs,
original/adapted hashes, authorship and license texts. Original LEGO PDF and author
links remain available alongside community instructions. Embedded part libraries
and unrelated editor metadata are removed; third-party part libraries stay
outside the repository. Model import must preserve transforms, colors and authored
steps; library substitutions are checked against the original geometry.
A library
reference pins its id, version, HTTPS URL and SHA-256. Opening Assembly lazily
downloads a verified ZIP into the shared user cache, with progress, cancellation,
retry and local ZIP import. The loader indexes the archive once and reads only
needed members into memory, without extracting the library. Updates are explicit;
a changed remote archive fails verification instead of silently changing geometry.
Local project-owned libraries may also be ZIP files or directories.

Prepared scenes persist in the user cache as numeric NumPy arrays and JSON metadata,
without pickle. Keys include model content, the verified library archive digest
and converter revision; working-copy paths do not distinguish identical models.
Directory libraries and local overrides are validated by content, including missing
lookup candidates so adding a higher-priority file invalidates old geometry.
Atomic cache writes, cancellation and rebuilding corrupt entries keep source
models authoritative; unavailable cache storage must not block viewing. Shared
meshes compute their bounds once rather than scanning vertices for every instance.

Normal project saves retain external references. Export with resources creates a
separate offline project containing only the model's transitive dependencies,
colors, attribution and licenses. It includes current drafts, Scratch and progress
without changing the original save path or save baseline. Export workers own an
independent snapshot so closing a project cannot invalidate an ongoing export.

The scene
contains shared meshes, transformed instances, stable identities, submodel groups
and authored steps. Device metadata binds instance IDs to expected ports. This is
instructional wiring; the Python program remains the runtime source of truth.
LDCad path/spring components consume their supplied fallback geometry as a single
component. Their generated wire segments must not become individual assembly
steps or selectable parts. Models without step divisions open as whole models;
unavailable instructions are not invented. Authored MPD steps may differ from
official PDF page numbers and do not imply physical validation.
Assembly uses its own workspace and supports orbit/pan/zoom, picking, current-step
parts, previous-step muting, optional future outlines and camera hints. Selection
and clearing it leave the camera unchanged. Ctrl+click in the model or parts list
centers the selection without changing scale or viewing angle. Shift+left drag and
right/middle drag pan freely. Zoom-in applies only the pan needed to hold selected
outer edges inside a 5% viewport margin, stopping correction at the selection center.
With no visible selection, the target is the built portion of the active group;
future outlines never affect navigation. If already outside after panning, correction
holds the existing outer edge rather than jumping to the margin. Correction is
continuous in scale, independent of wheel event subdivision, and absent on zoom-out.
Geometry clipping depends on scene depth rather than zoom. Recommended view frames
the current construction. Camera changes are retained in assembly progress.
The renderer uses a contained native OpenGL surface: opening, replacing or closing
it must not recreate or hide the LittleTinker Rig window's native surface. Native rendering
checks cover this lifecycle as well as rendered pixels and resource cleanup.
Rendering and picking use the same physical viewport size, including fractional
display scaling. Inspection never changes construction progress: devices and subassemblies are limited to
what is built at the current step. A part-list row selects every matching instance
added in that step. Repeat click, Escape, background click or changing step clears
selection. Hidden selected surfaces are translucent and selected edges are drawn
on top; filled faces and picking still exclude future parts and isolated-out groups.
Device and subassembly controls appear only when they offer a choice. Future
outlines share a row with the selection caption and disappear at the last step.
OpenGL failure must leave instructional text and part information usable. No physics,
automatic assembly planning or proprietary asset extraction is implied.

The first complete lesson teaches a two-wheel SPIKE Prime base: assemble, check
motor ports, drive, experiment, add a distance sensor and stop before an obstacle.
Full lesson construction is reviewed once as a development exercise. Recurring
checks protect persistence, palette isolation, geometry reuse, mating coordinates,
step visibility, picking and completion semantics.
