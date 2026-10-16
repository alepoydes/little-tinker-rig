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
- Keep pinned searches attached to their source view and revision, independent
  of keyboard focus. Replacing a filled input by dragging requires an explicit
  search for that exact input; ordinary drops retain their existing protection.
- Keep inner expression contracts available beneath a containing block's display
  ownership. Editing an inner value still updates the containing linked field.
- Check name initialization in evaluation order, separately from lexical scope
  ownership. Same-scope reads precede assignment writes; closures may run later.
