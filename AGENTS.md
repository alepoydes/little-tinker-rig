# Project rules

## Languages

- Use UTF-8 without a BOM for project text files.
- Write developer-facing documentation in English only, including architecture,
  design specifications, research, development guides, and project rules. Do not
  create or maintain translated copies of these documents.
- Write source-code comments and docstrings in English.
- Localize end-user content: GUI text, block names and descriptions, help, and
  lab/lesson text. English is the source language; Russian and other supported
  languages are user-facing translations.
- Keep Python keywords, identifiers, and executable code independent of UI
  language. Translation must not change program semantics.

## Development workflow

- After completing and successfully verifying each work stage, commit it with
  a short description. Keep unrelated or unfinished changes out of the commit.

## Documentation consistency

- Update affected guides, lesson steps and hints in every supported user language
  with changes to UI labels, catalog placement or interaction behavior. Use the
  visible localized card title and variant, not a description's first sentence.
- Verify documented workflows against the current controls and behavior. Link
  checks verify navigation, not factual accuracy; exercise the introductory path
  through the GUI when changing it.
- Keep the README showcase in English with English interface screenshots. Put
  localized UI screenshots only in instructional material for the matching
  language. The first tutorial teaches the workspace and a runnable Python
  program before robot assembly.
- Keep current contracts distinct from proposed designs and dated delivery
  evidence. Remove resolved items from open decisions, and link to the maintained
  guide or source-derived inventory instead of duplicating changing details.

## Structural editing

- Identify insertion destinations by their statement suite and index. Equal
  source offsets do not imply the same destination: a compound and its last
  child share an end offset but have different nesting.
- Keep move validation shared by pointer and keyboard workflows. Cover moves
  across shared boundaries with an independently specified resulting program,
  including the final compound, an emptied body, and one-step Undo.

## Catalog and parameter guidance

- Keep descriptive titles, full help, and executable source separate. Preserve the
  complete description when a short title replaces its first line in a view.
- Derive creation candidates from public declarations and result contracts, not
  from parameters consumed by an action. Unknown units are not confirmed reporter
  compatibility; ordinary Python expressions remain editable.
- Catalog filtering is explicit. Scalar selection and pointer hover must not
  change discovery state. In nested trees, sorting compares both group and card
  items with a total ordering, and filtering visits descendants before ancestors.
- Suggested expressions retain their imports and helpers through inline edits
  and variant changes. Apply dependencies and source as one Undo transaction.
  A numeric result alone does not make an operation a measurement: automatic
  readout suggestions require an explicit source declaration.
- Distinguish declarations from unresolved reads when creating public names.
  Prefer a compatible missing consumer name; preserve existing bindings and keep
  private helper names isolated from all references. Drag previews and committed
  insertions must use the same expansion rules. Missing-name guidance starts with
  a concrete creation or ordering fix before ordinary parameter help.
- Keep pinned searches attached to their source view and revision, independent
  of keyboard focus. Replacing a filled input by dragging requires an explicit
  search for that exact input; ordinary drops retain their existing protection.
  Switching that source to Python ends the search before a draft can diverge
  from its structural projection. Saved Scratch must match its visible text.
- Keep inner expression contracts available beneath a containing block's display
  ownership. Editing an inner value still updates the containing linked field.
  Catalog filtering and drop/variant validation must use these same contracts.
- Rename declarations through the shared lexical rename operation in every UI,
  including variant dialogs. References and the block edit form one transaction.
- Check name initialization in evaluation order, separately from lexical scope
  ownership. Same-scope reads precede assignment writes; closures may run later.
  A deferred write is not initialization merely because its function exists.
  Class-local reads before initialization can fall back to global names; preserve
  those dependencies during cleanup. Include parameter and return annotations,
  including quoted nested types, when retaining imports.
- An annotation without a value does not initialize or reserve a public creator
  name. Keep value declarations distinct from lexical ownership in suggestions,
  expansion and missing-name guidance. Deletion removes initialization, while
  preserving scope ownership; a later assignment restores it.
- Capture custom-block imports from free references at the selection boundary.
  Respect local aliases and Scratch shadowing, and verify the resulting block
  can be inserted with its dependencies into a fresh program.
  Deferred function bodies can use later outer imports; their defaults and
  decorators evaluate immediately. Method bodies do not close over class locals.
- Model implicit exception-alias cleanup as deletion. Distinguish loading an
  unbound module/class name (which may reach builtins) from deleting it or loading
  a function-local name. Verify both missing warnings and false positives.

## Workspace interactions

- Commit valid inline input before saving, running, switching views or leaving its
  document. Keep invalid input visible and editable; only explicit cancellation
  discards it. Hiding a widget is not a decision to discard its draft.
- Stop and disconnect bypass edit validation and preserve pending input. Exercise
  both toolbar actions and shortcuts while an invalid parameter is open.
- Route editing commands to a visible editor with a stable owner, including
  Scratch. Menus and catalog focus must not redirect edits to another document or
  a hidden structural projection. Non-editing workspaces must not undo programs.
- Retain the Python text document and its undo history across representation
  and document-tab switches, including Scratch. Each open document owns its
  Scratch widgets. Record structural updates to text buffers as undoable edits.
- Keep Scratch fragment identity in document history independently of its text
  and position. Moves, duplicate text and removal of neighboring cells must not
  exchange text buffers or their undo histories.
  Keep removed cells while their identities remain reachable through history.
- Program text drafts, block edits and Scratch share document Undo/Redo. Changing
  representation or parsing unchanged text must not introduce a second history
  or clear Redo. Verify transfers followed by Python Undo, save and reopen.
- Interrupted saves preserve the multiplicity of Scratch fragments. Recovery
  copies are a multiset union; identical text does not identify the same cell.
- Stop shortcuts must reach their owning window through modal dialogs. Test
  multiple windows so stopping one hub cannot target another.
- Coalesce pending control samples without losing the final neutral frame when
  input stops. Hub operations discard queued motion; verify delayed delivery and
  cancellation, not only successful writes on an idle connection.
  Stop and disconnect interrupt every task holding or waiting for the connection
  lock, including console input and configuration. Their timeouts must not be
  postponed indefinitely by unrelated writes.
- Momentary motor controls return to neutral on mouse/key release and focus loss.
  Cover slider grooves as well as handles: sliderReleased is not a general mouse
  release event. Verify emitted commands, not just the displayed position.
- Handle external file conflicts through explicit reload, copy or cancel actions.
  A failed reload leaves the open document intact; never bypass disk-change checks.
- Check compact layouts with Russian captions and lesson/device panels open.
  Icon controls retain tooltips and accessible names. Search must report misses,
  preserve the editor position on a miss, and support keyboard dismissal.
- Keep preview and source usable with Console open at the minimum window size.
  Help navigation must reveal its destination even when a search filter is active.

## Execution and example work

- Run and Upload use immutable current-source snapshots, including reachable open
  local modules, without requiring a file name or overwriting ordinary files.
  Persist recovery first; keep original source paths for runtime diagnostics.
- Bundled examples are templates. Resume the latest explicitly opened persistent
  attempt; create another only on an explicit restart. Keep origin and attempt
  identity through Save As, including imported modules and their open edits.
- Autosave retains Project's external-change checks and invalid-text support.
  Persist a recovery checkpoint even when autosave fails. Validate all module
  destinations before export; a main filename cannot replace an imported module.

## Hub dependency integration

- Use the Git-pinned pybricksdev public adapters and compiler through uv. Keep
  protocol framing and commands in the dependency; do not copy them into the app
  or reach into private client fields. Pins must be fetchable before publication.
- Verify changes through the USB child and a synthetic byte-stream peer, including
  cold-start slot selection, long binary input, interrupted upload and reconnect.
  A compiler mock cannot establish MPY ABI or imported-module compatibility.
- Waiting for program completion requires a fresh idle status after START;
  cached idle or a guessed startup delay is insufficient. Test disconnection and
  cancellation without treating simulated transport checks as hardware evidence.
