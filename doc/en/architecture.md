# Architecture

The Python source is the only authoritative program representation. AST nodes,
source spans, snippet matches, lexical names and display regions are derived data
that can be rebuilt after every committed edit.

```text
Qt / Textual / CLI
        ↓
Session: snippets, imports, Scratch, files
        ↓
Editor: selection, undo, move navigation
        ↓
edit: pure source transformations → Document: validate and commit
                                           ↓
                                  Syntax → analysis and display
```

Document publishes a revision only after formatting and compilation. Compilation
checks context but does not execute code. History stores source and Scratch
snapshots together. An invalid text draft stays outside the committed document.

Qt DocumentPage owns one Session, a structural view, a Python draft and its native
text undo. The window owns document tabs, global workspaces, help, console and one
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
output are never translated. Documentation has corresponding language directories.

Real and virtual hubs share ControlState, MotorBinding and HubInfo. Qt owns I/O in
an asyncio thread and serializes lifecycle operations. Input frames never build a
queue of old commands. A separate monitor supplies telemetry and direct motor
control; user programs use a separate Controller protocol when requested.

Virtual programs run in stoppable processes over a small explicit device model.
The model advances time deterministically in unit tests; runtime tests exercise
real subprocesses and Qt signals. It is neither physical simulation nor a security
sandbox. Hardware transport and motor characteristics need separate testing.

Files are replaced atomically, but Python plus workspace is not one filesystem
transaction. Saving first writes a recovery union of old/new Scratch, then source,
then final metadata. An interruption can leave duplicate fragments, but should not
lose the only saved copy. External modifications are checked for both files.

Structural validity does not prove algorithm correctness. Lexical diagnostics do
not perform full type, units or execution-path analysis. Comments are preserved by
source slices because AST alone does not retain them.
