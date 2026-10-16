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
