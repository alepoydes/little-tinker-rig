# PyBlocks Studio: Design and Implementation Specification

**Status:** consolidated design specification for implementation

**Working name:** PyBlocks Studio

This document describes the current design of a Python structural editor and robotics development environment intended to be implemented with Codex. It consolidates the agreed ideas, requirements, architecture, interaction model, snippet model, UI principles, and Pybricks integration. It intentionally omits the history of how the design was reached.

Where a detail has not yet been decided, the document marks it explicitly rather than inventing a choice.

---

## 1. Core idea

PyBlocks Studio is not a Scratch clone and not a separate visual programming language.

It is a **structural editor for ordinary Python source code**.

The normal `.py` file is the single source of truth. The editor parses the source into a Python AST and uses that structure to provide block-like interaction, constrained editing, drag-and-drop, semantic highlighting, completion, snippet recognition, validation, and educational guidance.

The most important invariant is:

> A project must remain normal, readable, executable Python even if PyBlocks Studio disappears.

A user must be able to open the file in Vim, VS Code, Helix, or any other text editor, modify it, and later reopen it in PyBlocks Studio. PyBlocks-specific metadata must not be required for the Python file to make sense or execute.

PyBlocks Studio may lose some enhanced presentation or snippet recognition after arbitrary external edits, but it must degrade to generic structural Python editing rather than making the source unusable.

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

PyBlocks Studio should keep the constraint and guidance of a block editor while using Python from the beginning.

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

Comments are not represented directly in Python's `ast` tree. If comment ownership is needed for movement or presentation, standard tokenization can be used. The exact comment-attachment policy is not yet fully specified.

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

The exact layout can differ in the TUI, but the same concepts should exist.

### 7.1 Main source

The main editor represents a valid Python program.

A local text edit may be temporarily incomplete while an editor field is active, but the user may only commit/finish an edit in the main source when the resulting Python is syntactically valid.

If an edit is invalid, the user can continue editing or cancel it and restore the previous valid state.

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

The persistence format for Scratch content has **not yet been decided**. It must not contaminate `main.py` with editor-specific metadata.

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
some_call(None)
```

`pass` and `None` are examples of context-dependent valid placeholders. The exact rules for when to introduce them should remain simple and Python-native.

The UI may present an automatically introduced placeholder as an editable slot rather than emphasizing the literal `None` or `pass` to a beginner.

---

## 9. Structural highlighting and the visual block model

PyBlocks should be capable of looking visually close to a block editor without drawing puzzle-piece geometry.

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

### 9.2 Hover and selection

Permanent coloring should remain pale enough that the source still looks like readable Python.

When the pointer or cursor is over a region:

- the exact node under consideration should become more prominent;
- it should be possible to navigate to the parent or child structural node;
- selection should be visually stronger than mere hover.

### 9.3 Presentation intensity

A useful long-term UI idea is a presentation continuum between:

```text
plain text  <-------------------------->  strongly block-like
```

This is a presentation choice over the same source and AST, not a conversion between languages.

The exact control for this continuum is not yet specified.

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
blank line selects nesting. Only compatible expressions fit empty parameter slots;
populated slots are not replaced by a drop.

A new Insert here row opens space before descriptions and owned comments. Adding
or removing it must preserve the same source row and relative pointer position.
Decorations are not new structural targets. Invalid contexts offer no insertion;
they must not snap to a distant valid context. Edge autoscroll is explicit; dragging
does not automatically fold code.

### 11.2 TUI interaction

The same move state can be controlled by keys, for example conceptually:

```text
previous / next target
move outward / inward
commit
cancel
```

The exact key bindings are a frontend decision.

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

## 15. Snippet definitions as ordinary Python functions

Snippet libraries should themselves be ordinary Python modules.

The preferred authoring form is a restricted Python function used as a static template definition.

For example:

```python
def run_motor(motor, speed: "deg/s" = 500):
    """Run the motor continuously at the selected speed."""
    from pybricks.pupdevices import Motor

    motor.run(speed)
```

The snippet loader should parse these modules as source/AST. Third-party snippet definitions should not need to be imported or executed merely to become available to the editor.

From the function definition the system derives:

- function name -> snippet identity/name basis;
- formal parameters -> editable placeholders;
- defaults -> initial placeholder values;
- annotations -> optional semantic/type/unit metadata;
- docstring -> help text;
- imports inside the function -> dependencies;
- remaining body -> AST template.

This keeps snippet authoring close to ordinary Python and avoids verbose declarative schemas.

### 15.1 Statement snippets

A function whose effective body contains statements expands to those statements.

Example:

```python
def run_motor(motor, speed=500):
    motor.run(speed)
```

may instantiate to:

```python
left_motor.run(700)
```

### 15.2 Expression snippets

A function whose effective snippet body is a `return` can define an expression template.

Example:

```python
def reflection_below(sensor, threshold: "%" = 30):
    """True when reflected light is below the threshold."""
    return sensor.reflection() < threshold
```

may instantiate to:

```python
sensor.reflection() < 30
```

### 15.3 Complex snippets

A snippet may contain a substantial algorithm:

```python
def follow_edge(drive, sensor, target: "%" = 50, gain=2):
    """Follow the edge of a line."""
    while True:
        error = sensor.reflection() - target
        drive.drive(200, gain * error)
```

In the main source this remains ordinary expanded Python.

In the visual editor it may be treated as one recognized compound block whose public editable parameters are `drive`, `sensor`, `target`, and `gain`.

The internal AST does not need to be individually exposed until the user chooses to edit/expand the snippet as generic Python.

### 15.4 Restrictions on snippet-definition functions

Snippet-definition functions are templates, not general programs.

Agreed restriction:

- snippet definitions should be non-recursive.

Other restrictions should be added only when implementation requires them; they have not yet been fully specified.

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

The exact package/manifest format is not yet fixed.

A major design goal is that writing a new snippet should require mostly writing normal Python rather than authoring a large schema or UI definition.

---

## 20. Snippet versioning and upgrades

Snippet code can change between Studio/library versions. The system must avoid depending on fragile inline metadata in the Python source.

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

### 20.3 Historical template matching

Recognition should first attempt installed/current snippet templates.

When a current template does not match, the system should be able to try historical patterns from older versions of the same snippet collection.

If a historical template matches, the editor can identify the code as an old form of a known snippet and offer an upgrade.

The source is still ordinary Python; historical matching is an optional enhancement.

### 20.4 Automatic upgrade by preserving bindings

If old and new snippet versions have compatible signatures, an upgrade can be generated mechanically:

```text
match old template
    -> extract placeholder bindings
    -> instantiate current template with the same bindings
    -> replace old source region
```

This avoids requiring explicit migration code for ordinary snippet evolution.

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

The main source should clearly distinguish imports managed automatically by PyBlocks from imports written by the user.

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

- PyBlocks may freely recompute, sort, add, or remove imports in the managed section.
- User imports outside the managed section must be preserved.
- Removing the last use of a managed dependency may remove its managed import.
- The markers themselves are ordinary explanatory comments, not hidden block metadata.

---

## 23. Units and engineering metadata

Engineering units are a general problem in robotics and scientific code. Pybricks APIs frequently use quantities such as degrees, degrees per second, milliseconds, millimeters, percentages, and similar units.

The initial implementation should keep runtime Python simple: values on the hub remain ordinary numbers unless the underlying API itself requires otherwise.

Units are primarily editor/static metadata.

Snippet annotations are a natural place to express them, for example:

```python
def run_motor(motor, speed: "deg/s" = 500):
    ...
```

or:

```python
def wait_ms(time: "ms" = 1000):
    ...
```

This allows frontends to show compact unit hints beside editable values without changing the generated/runtime Python.

The annotation model may later also support semantic object kinds such as `Motor`, `ColorSensor`, `DriveBase`, etc.

The exact annotation syntax beyond simple useful cases is not yet fixed.

A future static diagnostic may detect obvious incompatible-unit operations, but a full physical-units type system is not required for the first implementation.

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
- A true-color TUI can use ANSI backgrounds, gutters, indentation, and selection emphasis.
- A limited-color terminal can approximate the palette.

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

- main source text;
- Scratch workspace contents if Scratch is persistent in the current session.

After every committed atomic operation:

- push the previous state to undo history;
- clear redo history.

Undo restores an earlier source state and reparses it.

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
pyblocks/
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

Qt and TUI implementations should be developed in parallel rather than treating one as a later port.

This is intentional: if a substantial feature can only be implemented through Qt-specific APIs, that is evidence that too much logic has leaked out of the core.

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

The TUI is a first-class frontend, not merely a debugging utility.

It is important for:

- old or lightweight laptops;
- remote/terminal workflows;
- architecture validation;
- users who prefer keyboard interaction;
- environments where installing a large GUI toolkit is undesirable.

The TUI should implement the same essential concepts:

- Library;
- main source;
- Scratch;
- structural selection;
- semantic coloring as terminal capabilities permit;
- move/navigation through structural targets;
- snippet insertion;
- help/documentation;
- run/stop/console where the Pybricks extra is installed.

The exact TUI library has **not yet been chosen**. It should be mature, reliable, cross-platform where practical, and optional.

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
pyblocks                 -> core + CLI
pyblocks[tui]            -> TUI dependencies
pyblocks[qt]             -> PySide6 GUI
pyblocks[pybricks]       -> Pybricks host integration
pyblocks[gamepad]        -> optional physical-controller support
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

The Pybricks integration should expose a small, stable project-local API for the rest of PyBlocks.

It needs to support at least the concepts of:

- discover/connect to a hub;
- upload/run the current Python program;
- stop a program;
- receive console/output data;
- send low-latency application/control state where supported;
- handle reconnection/errors cleanly.

The exact wrapper API should remain thin and follow what the underlying Pybricks library already provides rather than abstracting hypothetical future transports.

BLE/USB transport details stay inside this integration.

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

The exact normalized state format is not finalized.

The controller input implementation should be optional so that users who do not need physical gamepads do not inherit unnecessary dependencies.

A mature cross-platform controller library based on SDL is a plausible implementation direction, but the exact dependency is not yet selected.

---

## 39. Source-side controller API

The eventual user-facing Pybricks code should be ordinary readable Python.

A future convenient API may allow code conceptually like:

```python
controller = Controller()

while True:
    drive.drive(
        controller.left_y * 500,
        controller.left_x * 120,
    )
```

Whether this helper lives in a small bundled hub-side module, is generated inline, or uses an existing Pybricks application-data API has not yet been finalized.

The important point is that virtual and physical controllers should feed the same conceptual state.

---

## 40. Library panel behavior

The Library is the source of available snippets.

It should support:

- grouping by collection/module/category;
- compact browsing;
- search/fuzzy search where practical;
- drag/drop insertion in Qt;
- keyboard insertion in TUI;
- concise display rather than large permanent previews.

A snippet should be usable without opening its full documentation.

Hover/selection may show quick help. Full documentation is explicitly separate.

---

## 41. Snippet recognition in existing source

Snippets are not only inserted from the Library.

When opening any Python file, the editor should scan its AST and identify regions matching known snippet templates.

This allows ordinary source written externally to gain enhanced PyBlocks presentation automatically.

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

1. save a normal `.py` file from PyBlocks;
2. edit it in another editor;
3. reopen it in PyBlocks.

PyBlocks reparses the source from scratch.

Possible consequences:

- generic AST structure is always recoverable from valid Python;
- snippet recognition may change depending on how closely code matches templates;
- old snippet forms may be detected using historical patterns;
- no editor-specific source markers need repair.

This graceful degradation is more important than perfect preservation of every enhanced visual annotation.

---

## 43. Error handling and validity

The main source should maintain a strong invariant:

> Between committed operations, the document is syntactically valid Python.

Structural edits must be atomic.

A failed edit should leave the previous source unchanged.

Temporary text-edit widgets may contain invalid text while active, but invalid text cannot be committed to the main document.

Scratch is explicitly exempt from this rule.

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

Qt and TUI tests should concentrate on translating frontend events into the same tested core operations, rather than duplicating structural logic tests.

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

One mature terminal UI dependency, choice TBD.

### Pybricks integration

Use the existing Pybricks host-side Python library where practical.

### Physical gamepads

Optional mature cross-platform controller dependency, likely SDL-based, exact choice TBD.

Do not introduce browser runtimes, JavaScript build systems, Rust sidecars, local RPC daemons, or similar layers unless a concrete later requirement justifies them.

---

## 47. Important invariants

The implementation should preserve these invariants:

1. **Python source is the truth.**
2. **A normal `.py` file must remain useful outside PyBlocks.**
3. **No per-block/source provenance tags are required for correctness.**
4. **AST/block presentation is derived from source.**
5. **The committed main document is syntactically valid Python.**
6. **Scratch may be syntactically invalid.**
7. **Structural edits are atomic.**
8. **Snippet recognition is an enhancement, never a requirement for execution.**
9. **Unknown/modified code degrades to generic Python blocks.**
10. **Heavy UI/hardware dependencies are optional.**
11. **Qt and TUI reuse the same core editing behavior.**
12. **Style semantics are shared; rendering mechanics are frontend-specific.**
13. **Undo/redo is required.**
14. **Managed imports are clearly separated from user imports.**
15. **Snippet definitions should be concise Python, not verbose metadata schemas.**
16. **When data can be reliably derived, do not persist duplicate state.**

---

## 48. First implementation milestones

The following sequence reflects the current design without requiring speculative features.

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

### Milestone 2: minimal Qt and TUI views

Implement both frontends in parallel with:

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
- TUI keyboard mapping.

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
- compact Library UI in Qt and TUI;
- insertion;
- tooltip/quick help in Qt;
- explicit full help view;
- equivalent help access in TUI.

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

Exact project metadata format can be chosen when this milestone is reached.

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

The following questions remain intentionally open and should not be guessed during initial implementation unless they become necessary:

1. Which canonical Python formatter to use.
2. Exact TUI framework/library.
3. Exact snippet collection package/manifest format.
4. Exact persistence format for Scratch workspace.
5. Exact project-level mechanism for selecting/pinning snippet collections.
6. Exact historical-pattern storage format.
7. Precise conflict-resolution rules when multiple snippet templates match the same region.
8. Exact type/unit annotation syntax beyond simple cases.
9. Exact comment-attachment policy when moving source blocks.
10. Exact Pybricks host API calls and supported transports in the current library version.
11. Exact hub-side helper API for virtual/physical controller state.
12. Exact physical gamepad library.
13. Exact visual palette and animation details.
14. Whether and how a presentation-intensity slider should be exposed.

These are implementation decisions to make from concrete evidence, not places to invent complexity in advance.

---

## 50. Final design summary

PyBlocks Studio should be built around a very small set of strong ideas:

- Python source is the program.
- The AST turns Python into manipulable structure.
- Structural blocks are source ranges, not a second model.
- Indentation plus semantic backgrounds can provide a Scratch-like visual hierarchy while showing real Python.
- Main source remains syntactically valid; Scratch is the place for unfinished code.
- Drag-and-drop is generalized as navigation through legal structural insertion targets.
- Snippets are Python-function AST templates with parameters as placeholders, docstrings as help, imports as dependencies, and annotations as optional semantic/unit metadata.
- Snippets are recognized structurally in ordinary Python source.
- Snippet versions are handled by collection versioning and historical AST matching, without adding per-snippet markers to source.
- Compatible snippet upgrades are generated by extracting old bindings and instantiating the new template.
- Auto-managed imports are clearly separated from user imports using ordinary comments.
- Scope analysis provides lightweight completion and undefined-name checking.
- Style semantics and interaction primitives live in the core; Qt, TUI, and CLI are thin independent frontends.
- Qt and TUI are developed together to enforce this separation.
- Heavy dependencies are optional.
- Pybricks is an optional execution/domain integration rather than part of the editor core.
- Virtual and physical controllers feed a shared normalized control state.
- Code volume should be reduced by representation and algorithmic simplicity, not by collapsing modules or hiding complexity.

The project should feel like ordinary Python that has acquired structure, constraints, discoverability, drag-and-drop, and domain-specific intelligence, rather than like a visual language that happens to generate Python.

## Desktop library and hub actions

Every block has one manifest level: beginner, intermediate, advanced, or expert. All exists only
as a filter choice. Levels are cumulative and a fresh installation starts at
Beginner: sixteen blocks for motor/sensor and robot setup, bounded moves, waits,
repetition, console feedback and complete line/remote activities. Intermediate
adds decisions, readings, hub feedback, variables, arithmetic and reusable
functions. Advanced adds collections, numeric helpers, curves, steering cars and
individual remote operations. Expert adds exception handling and raw motor duty.
Legacy standard settings and manifests migrate to intermediate. Above Beginner,
groups start collapsed; search expands matching groups and restores their prior
expansion when cleared. Python view is the
path to broader language/API features; levels never restrict editable source.
Search, groups and the persisted level filter combine; help
uses the same metadata. Generated comments place the action symbol before text,
use the owning block's color, and preserve enclosing indentation bands.

Hover and selection increase HSL saturation and moderately reduce lightness at
fixed hue and opacity. Saturation alone cannot distinguish already-pale saturated
colors sufficiently; verify the final composited contrast, not only HSL values.
Each pixel retains its most specific block's color, including under an active
ancestor; comments and code use the same region pass. Never stack dark selection
overlays on the base colors. The shared transform resolves both changes before
painting a region, preserving each descendant's hue and comment ownership.

Prepared activities use short inline templates and native Pybricks operations.
Their source is visible and can be expanded without changing its behavior.
Expansion is a temporary editing view and is recalculated after source changes;
separate use/unpack level metadata is not implemented. Shared helper lifecycle,
general events, gait frameworks and host media blocks remain deferred.
Sensor/motion activities specify termination and brake in Python cleanup. Direct
remote pairing and steering-stop calibration are hardware capabilities, not
features of the virtual physics model.

The toolbar omits Parameters, To Scratch and Python fragment; menus and shortcuts
retain these actions. Upload saves and sends the active program without running.
Run uploads and executes; Run stored program starts the existing hub program;
Stop halts execution. Physical uploads contain compiled code without an additional
source archive. Source read-back and bytecode decompilation are out of scope.

Firmware installation is a desktop workflow with model, kind and version selection,
local packages, cached official downloads, package review, progress and errors.
Inventor/Prime uses USB DFU; BOOST and Technic use Bluetooth bootloaders. Model
compatibility is checked before erase. LEGO downloads provide Inventor/Prime
recovery 1.3; BOOST/Technic restoration requires a local compatible LEGO package.
Automation prepares images and tests public transport boundaries; physical flashing
requires separate hardware verification.

### Structural expression and function editing

The desktop exposes expression leaves, call receivers and callees, function names,
parameters and operators as fields derived from source. Calls, definitions and
Boolean operations share insertion, removal and reordering of list items; calls
and definitions allow zero items, while `and`/`or` keep at least two operands.
Explicit expression replacement and wrapping preserve grouping and evaluation
order. Occupied fields remain protected against accidental drag replacement.

Module-level user definitions contribute a transient My functions library group.
Definition renames follow resolved lexical bindings, including known keyword
calls. Signature changes retain existing call sites. Proven argument mismatches
have a red frame and a generated error-comment row; unknown dynamic signatures
are not treated as errors. Syntax validation and one-step Undo apply to all edits.
The Beginner range block fixes `range` and exposes the counter/count; the Intermediate
variant exposes start, exclusive stop and step as well.

Generated comments begin with `#` at their containing statement's indentation;
the following enlarged icon and text may align with a nested expression without
increasing row height. They share backgrounds, ancestor bands, hover, selection
and ownership hit testing with code. Origin and destination markers use explicit,
contrasting colors; the origin starts at the moved block's former indentation.
Library search matches all query words across the complete localized help, source,
name and group.
