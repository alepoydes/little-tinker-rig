# Architecture

The Python source is the only authoritative program representation. AST nodes,
source spans, snippet matches, lexical names and display regions are derived data
that can be rebuilt after every committed edit.

```text
Qt / CLI
        ↓
Session: snippets, imports, Scratch, files
        ↓
Editor: selection, undo, move navigation
        ↓
edit: pure source transformations → Document: validate and commit
                                           ↓
                                  Syntax → analysis and display
```

The Textual TUI uses `core/source_file.py` for unrestricted text editing. It does
not create a structural Session or touch block workspace metadata. Both frontends
use `pybricks/worker.py` for serialized hub operations, `pybricks/firmware.py` for
firmware validation and installation, and `core/completion.py` for static Jedi
analysis. Qt adapts worker callbacks to signals; TUI posts Textual messages.

Real hubs use the public BLE, legacy USB and CDC adapters of the Git-pinned
pybricksdev dependency selected by uv. It owns framing, protocol commands and
compilation. LittleTinker Rig owns discovery, process isolation, user-facing
diagnostics and application lifecycle. No local serial protocol implementation
is maintained.


Document validates structural revisions by formatting and compilation, without
executing code. Its history stores the valid source projection, optional raw
Python draft, Scratch text and fragment identities in one snapshot. Draft edits
do not require parsing. Applying an unchanged draft updates the projection
without creating another Undo entry or clearing Redo.

Block definitions use static decorators as their sole metadata source. The loader
feeds the library, authoring preview, help and structural edit permissions.
Signature, declaration and result annotations share a parsed type/unit model.
Known mismatches are diagnosed; unknown dynamic values stay usable. At commit,
reachable generated helpers and imports are reconciled with main and Scratch
references before the new snapshot is published.

Qt DocumentPage owns one Session and the structural and Python views. Native Qt
edit-command boundaries group typing in the shared document history; program
Undo/Redo, including text context menus, always restore that history. Scratch
widgets remain cached while their identities are reachable through Undo/Redo.
The window owns document tabs, global workspaces, help, console and one
hub connection. Changing tabs or language preserves document widgets and history.
Window actions resolve the active document when invoked.

Parameter slots are derived from snippet bindings and ordinary expression positions.
Changing one is a validated source transaction. Display-only parameter padding does
not alter the source; Qt UTF-16 positions are translated at the boundary. Move and
insertion previews use the same targets and template defaults as the committed edit.
Selection pulse and editor state are transient.

gettext PO catalogs are the translation source; MO files are compiled package data.
Static captions are captured and translated without rebuilding widgets; dynamic
messages use explicit format placeholders. User source, filenames and console
output are never translated. End-user documentation has corresponding language
directories; developer documentation remains English-only.

Real and virtual hubs share ControlState, MotorBinding and HubInfo. Qt owns I/O in
an asyncio thread and serializes lifecycle operations. Input frames never build a
queue of old commands. A separate monitor supplies telemetry and direct motor
control; user programs use a separate Controller protocol when requested.
Stop and disconnect cancel all earlier tasks holding or waiting for the worker
lock, including console writes and configuration, before acquiring it themselves.

Virtual programs run in stoppable processes over a small explicit device model.
The model advances time deterministically in unit tests; runtime tests exercise
real subprocesses and Qt signals. It is neither physical simulation nor a security
sandbox. Hardware transport and motor characteristics need separate testing.

Program snapshots freeze the entry and reachable local modules, with overrides
from open editor buffers. Run and Upload require recovery persistence, not an
ordinary-file save. Tracebacks map to the snapshot's original paths and text.
ExampleWork records each persistent attempt's bundled origin and current paths.
The Qt manager resumes attempts and autosaves through Project, retaining its disk
conflict checks. A failed autosave still leaves a separate recovery checkpoint.

Files are replaced atomically, but Python plus workspace is not one filesystem
transaction. Saving first writes a multiset union of old/new Scratch, then source,
then final metadata. An interruption can leave duplicate fragments, but should not
lose the only saved copy. External modifications are checked for both files.

Structural validity does not prove algorithm correctness. Lexical diagnostics do
not perform full type, units or execution-path analysis. Comments are preserved by
source slices because AST alone does not retain them.
