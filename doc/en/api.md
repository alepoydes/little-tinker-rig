# Developer API

`little_tinker_rig.core` imports neither Qt, Textual, SDL nor connection libraries. Session
is the main integration entry point; pure transformations are also public.

## Documents and sessions

```python
from pathlib import Path
from little_tinker_rig.core.session import Session

session = Session(Path("main.py"))
snippet = next(s for s in session.snippets if s.identity == "python/basics/display")
session.insert_snippet(snippet, {"value": '"Hello"'})
session.project.save()
```

`State(source, scratch)` is immutable. `Document.commit(source, scratch=None)`
validates and formats before publication and returns whether it changed anything.
Failure changes neither state nor history. `None` retains Scratch. Empty commits
do not clear redo. Use Editor.undo/redo when keeping an editor selection.

`Session(path, collections=(), allow_draft=False)` combines Project, Editor,
collections, recognition and analysis. `matches`, `visible_matches` and `analysis`
refresh with the source revision. Operations include `edit_python`,
`edit_parameters`, `insert_snippet`, `upgrade_selected`, `to_scratch`,
`set_scratch`, `restore_scratch` and `toggle_expansion`.

Project detects the input Python encoding and external changes. Save and Save As
write UTF-8 without a BOM, normalizing an active encoding declaration in the saved
state. Saving uses atomic
per-file replacement and protects Scratch across interrupted multi-file saves.
With `allow_draft=True`, invalid source is returned in `project.draft` while the
committed document starts empty. Commit corrected source and clear `draft` before
saving. Structural CLI commands use the default strict behavior. TUI uses
`SourceFile` independently: it shares UTF-8 normalization, preserves other source
text and checks disk changes
without parsing, formatting or rewriting block workspace metadata.

## Spans and transformations

Spans are Unicode character intervals `[start, end)`. Lines start at 1, columns
at 0. Syntax exposes `offset`, `position`, `at`, `spans`, `owned_spans`, `parent`,
`children`, `ancestors`, `text`, `block_span` and statement `suites`. AST nodes and
Target objects belong to one revision and must be reacquired after changes.

The `edit` module provides `replace`, `delete`, `insert`, `move`, `reindent`,
`patches`, `targets` and `target_position`. `Target(suite, index)` is an insertion
before a statement or at the end of its list. Expressions retain necessary
parentheses; unparenthesized output is accepted only when its AST agrees with the
protected replacement. Compiler checks enforce contextual Python rules.

Editor provides parent/child/sibling navigation and a two-stage move:
`begin_move`, `navigate_move`, `preview_move`, `commit_move` or `cancel_move`.
Use Session.begin_move to include all statements of a compound snippet.

`parameters.slots(session)` exposes editable source spans and their parameter
metadata. `choices` suggests values; `default_bindings` supplies library insertion
bindings. `change_parameter` verifies the source revision, updates repeated
occurrences together, and commits atomically.

## Libraries and analysis

`load_module` and `load_collection` parse without execution. `instantiate`
returns `Expansion(source, imports, helpers)`, accepting expressions as strings or AST.
Decorators supply insertion mode, level, appearance and editable declarations;
`legacy=False` treats undecorated functions as helpers. `occupied` enables hygienic
local renaming. `recognize` returns Match objects with
bindings, local names and occurrences. `upgrade` checks version/signature
compatibility. `manage_imports` only manages its marked section and retains
references from ordinary code and Scratch.

`Session.insert_snippet` installs imports and reachable helpers in the same undo
transaction. Existing generated implementations survive collection reloads.
`Analysis.type_info` returns a known type/unit pair or `None`; `compatibility`
distinguishes compatible, incompatible and unknown values. `Analysis.available`
lists lexical names; diagnostics report unknown references and known contract errors.
`presentation.regions` exposes source spans, roles, depth, line extension and
fold/move capability. `PALETTE` and `snippet_role` keep library and source colors
consistent; renderers own geometry and animation.

## Hubs and input

`Connection(output=None, changed=None)` accepts bytes-output and HubInfo callbacks.
Async methods are `connect(name=None, transport="ble")`, `run(path, wait=False)`,
`stop`, `start_monitor`, `drive`, `send(ControlState)` and `disconnect`. Use one event
loop and serialize lifecycle operations. Run stops the previous program first.
Disconnect stops an active monitor; ordinary autonomous programs are separate.

`VirtualConnection(..., model="inventor")` provides the same interface plus
`configure(port, kind, value=None)`. Models are inventor, boost and technic.
A sensor value can be a number or a field dictionary. `run(wait=True)` reports
program failure; Stop kills the child and restores manual mode. HubInfo includes
identity, connection/program/monitor flags, ports, battery and virtual errors.

`MotorBinding(port, source, mode="speed", scale=500, center=0, inverted=False)`
maps a stick or trigger. `motor_commands` rejects duplicate ports. An empty motor
command list brakes active motors. The lease expires after 500 ms.

ControlState has four axes in `[-1, 1]`, a 16-bit button mask, a legacy slider and
two triggers in `[0, 1]`. The stdin frame `~XXXXXXXXBBBBSS\n` is 16 bytes; nonzero
triggers add `LLRR` before the newline for 20 bytes. Axes have precision 0.01.
The monitor uses separate ASCII motor commands and framed dictionary telemetry,
parsed safely without executing it. BOOST requires neither ujson nor PUPDevice.

SyntaxError indicates invalid Python, ValueError an invalid operation, binding or
conflict, and OSError a file/device failure. Failed source edits are never published.


## Detached fragments

`Session.fragment(text, snippets)` creates a structural projection without a file.
It formats and parses, but does not compile the surrounding execution context or
add imports. Arbitrary invalid text stays separately in Scratch.
`Transfer.capture(owner, index=None, fragment=None)` prepares a move without
changing state. `to_scratch(position)`, `to_program(target)` and
`to_fragment(index, session, target)` check the revision and commit both areas in
one owner transaction. `index=None` denotes the main document.

`Analysis.type_of(node)` and `name_type(name, offset)` conservatively infer known
types for editing suggestions; they are not a Python type checker.
