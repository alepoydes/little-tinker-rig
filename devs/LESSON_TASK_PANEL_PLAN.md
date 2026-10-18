# Lesson task panel implementation plan

Status: implemented in the desktop app. The delivery sequence and acceptance
criteria below record the original delivery design. Later refinements are listed
below; [the current user guide](../doc/en/lessons.md) describes the running behavior.

## Current interaction (2026-10-18)

The selected task expands; other rows keep their step number, checkbox, title and points
visible. Clicking a title selects the task and opens its section in the same
continuous Help document. Clicking a checkbox changes completion only. Help has
an inline task list and in-document Find. A new attempt starts at the top; a
resumed attempt opens at its selected task. On narrow windows the panel appears
as a transient overlay and destination links hide it without changing the saved
expanded preference. Bundled guided lessons and Pybricks exploration projects
have separate menu groups. Project goals now identify the program and concrete
activity for each stage or variant.

## Illustration authoring

First drive uses three local SVG schematics shared by its English and Russian
materials: the two-wheel base and ports, forward/reverse motion, and the sensor's
distance to an obstacle. These explain measurements alongside the part-by-part
Assembly model. The only visible symbols inside the SVGs are port letters and
numeric values with units; captions and descriptive image text live in localized
Markdown. The full instruction and each task panel refer to the same assets with
paths relative to their own Markdown file. `HelpBrowser` and `TaskMarkdown` fit
images to their visible text columns, and lesson/project packaging includes the
assets automatically.

For another lesson, use an image only when it clarifies a build, connection,
motion, or measurement. Verify physical claims against the model or real build,
provide descriptive alternative text and a caption in every supported language,
and keep the image local for offline projects. Preserve readable contrast in both
appearance themes. Exploration projects with linked third-party build manuals
should continue to link those manuals; no unrelated decoration is needed.

## Outcome

Opening a lesson attaches a right-side task panel to an ordinary student project.
Program, Control, Help, Block Editor, and Assembly retain their usual controls.
The panel lists tasks, opens the relevant materials or workspace on an explicit
click, and records completion and points. It is absent outside a lesson project.
It can collapse to a small progress control and reopen without losing context.

A task recommends blocks in a dedicated **For this task** catalog view. The full
catalog, level buttons, Scratch, Python editor, expressions, and existing-program
editing stay available. A lesson may create several editable Python files from
templates and may provide optional Scratch material. Starting or revisiting a
task never replaces student work.

## Original code assessment

- `core/lessons.py` already snapshots lesson materials, supports several programs
  per project, and stores progress in the portable `.ltr` archive. Keep stable
  stage IDs as task IDs so existing projects remain readable.
- `qt/lessons.py` owns the separate Lesson page, task card, stage navigation,
  checks, lesson robot, save/export, and project association. Replace its page
  and card presentation with the panel; retain its project and resource logic.
- `qt/library.py` already has a lesson-specific view. Make it a recommendation
  view. Remove `lesson_ids`, Scratch `allowed_ids`, and expression restrictions
  as lesson-enforced filters. Do not remove normal catalog level filtering.
- `qt/app.py` currently persists numeric workspace indices, including Lesson at
  index 4 and Assembly at 5. Move to stable workspace keys and migrate old values
  before removing the Lesson entry from the sidebar.
- `StudentProject.create()` currently makes a private working copy, while
  `Lessons.release_unused()` removes it on ordinary close. `Lessons.open()` only
  reuses an already-open project's archive path; a lesson template has no such
  path, so opening it again creates another copy. Fix this before relying on
  project-scoped progress.

## Original interaction contract (superseded where noted above)

1. The panel belongs to the active lesson project, not to one Python tab.
   Switching among its files preserves the selected task and panel state.
   Switching to an unrelated file hides the panel; returning restores it.
   An independently opened robot model does not change the lesson's task links.
2. A collapsed panel becomes a `Lesson · 3/6` progress control in the toolbar
   directly beside the hub connection control, with an accessible name and
   tooltip. No lesson means no panel or progress control. The expanded panel
   has a compact header and a full-height scrollable set of task cards. Every
   card shows its checkbox, title, points, authorable Markdown, status, and
   contextual links. Selection only changes recommendations and detail context.
3. Selecting a row changes the current task and recommendations only. It does
   not navigate, create files, run the hub, or mark completion. Explicit links
   open **Instructions** (one localized Markdown file in Help, positioned at the
   task section), **Program** (named student file or
   current file), **Assembly** (the lesson robot and relevant steps), and
   **Controls** as applicable. Hints appear in the panel on request. Opening a
   link never completes a task. Preserve the active editor and cursor where the
   destination does not require changing documents.
4. The panel is a full-height right dock, including when Console is open.
   Scratch shares the right dock area through tabs rather than adding another
   column. Escape, the collapse control, or clicking outside at narrow widths
   returns to the toolbar progress control. Switching to Scratch also exposes
   that control so the learner can return to tasks. Test English and Russian
   labels at 1024×768 and 1440×900.
5. Controls have keyboard focus, accessible names, and localized tooltips.
   Icons and short numbers carry the persistent chrome; descriptive labels live
   in row details and tooltips. Panel visibility is a layout preference, not a
   permission or lesson progress state.

## Data and compatibility contract

- Keep lesson `format: 1` and existing `stages` fields initially. Add optional
  nonnegative integer `points` per stage, defaulting to 1. A stage's existing
  localized `description`, `mode`, `program`, `assembly`, `blocks`, `hints`,
  `check`, and `devices` provide default card links. Optional localized `panel`
  Markdown provides each card's authored text, falling back to `goal`.
  `panel_intro` adds lesson-wide introductory Markdown. Add an optional list
  of typed, localized resource links only where a task needs extra Markdown or
  a second destination. Validate local paths inside the lesson snapshot and
  allow only known internal action types. Existing Markdown `program:` and
  `assembly:` links keep working.
- Authored lessons use one localized `instructions` Markdown file for their full
  text. Stage `description` references sections of that file by stable anchors.
  Opening a lesson presents the whole document in Help immediately. One lesson
  tree entry remains throughout; task links only scroll to sections. Legacy
  stage files are combined into one document at runtime. Help retains ordinary
  navigation and Back control.
- Treat `blocks` as recommendations. The **For this task** view shows every
  recommended block even if its normal difficulty is above the selected level;
  other views honor the user's level choice. Missing recommendations show a
  useful message and do not make the lesson unusable. A bundled `collection`
  remains available to the project, without hiding standard collections.
- Store completion as a unique set of stable task IDs. Compute points from
  completed IDs and stage weights whenever displayed or saved; never increment
  a separate score counter on clicks. An unchecked task loses its points.
  Existing duplicate `completed` entries are normalized without double credit.
  Show whether completion was learner-reported or verified. `check: devices`
  requires a fresh successful connection check before its checkbox can be set;
  disconnecting later does not retroactively erase a recorded observation.
  Code execution and physical success are not inferred from visiting a page.
- Persist selected task, revealed hints, completion, and panel collapse state in
  the project. Panel width may remain an application-level layout preference.
  Ignore or migrate legacy `guidance` and `explore` fields. Map legacy numeric
  `mode: 4` to Program and `mode: 5` to Assembly. Persist workspace names after
  migration so later sidebar changes do not corrupt navigation.
- Keep an application-managed, recoverable backing for the latest attempt from
  each lesson template. Its origin identity and attempt ID survive Save As and
  ordinary close. Reopening the same template resumes that attempt, including
  unsaved edits, progress, and Scratch; an explicit **Start new attempt** creates
  another. A user-selected `.ltr` remains a separate portable save target.
  Internal auto-persistence must not make **Save** silently write to an invisible
  path. Preserve external-change checks, recovery, and the ability to open older
  `.ltr` projects. Never overwrite a student's source from a changed template.
- Materialize top-level starter code and declared `programs` only when the
  attempt is created. Adapt stage-level starter actions to open or create one
  stable named student file, rather than making a fresh tab on every click.
  Optional Scratch seeds go into a named program's own Scratch state once at
  project creation; they are suggestions, never hidden requirements, and are
  never replayed when the lesson is reopened. Do not seed the same code in both
  Python and Scratch unless the lesson explicitly calls for two examples.

## Delivery sequence

| Phase | Work | Reviewable result |
|---|---|---|
| 1. Identity and persistence | Add origin/attempt metadata, persistent latest-attempt lookup, atomic backing, explicit restart, and archive migration | Opening one template twice, including after a normal restart, returns to the same work; Start new attempt is the only duplicate path |
| 2. Panel shell | Add the right panel and collapsed progress control to `Studio`; bind it to the active project and all workspace pages; make narrow layouts responsive | No lesson leaves no chrome; project/tab switches and Scratch/device coexist predictably |
| 3. Task navigation | Render full Markdown cards, hints, and inline destination links; remove the separate Lesson page and top task card | A task selection is non-navigating; each link reaches the correct student file or workspace and backtracking retains edits |
| 4. Open block discovery | Turn the lesson catalog view into recommendations; remove lesson-enforced block, Scratch, expression, operation, and level restrictions | A child can use any compatible block while recommended blocks remain easy to find |
| 5. Completion and points | Normalize completion, add weights and evidence status, wire manual/device checks, derive progress and score | Checking/unchecking/reopening cannot double count; unsupported automatic claims are not displayed |
| 6. Templates and materials | Make starter actions idempotent, add optional Scratch seed and extra resource-link support, update `first_drive` as the pilot | Partial code and materials appear once; multiple files remain editable and portable |
| 7. Release integration | Migrate bundled lessons, translate new GUI strings, update user guides in English and Russian, refresh developer design references | Documented introductory path matches the UI and old projects still open |

The delivered implementation combines phases 2 and 3 while preserving project
ownership of panel state and progress. Focused core, UI, and catalog tests cover
the contracts below.

## Acceptance checks

- Reopen a template repeatedly in one window and after a clean application
  restart: one latest attempt is resumed; its edited Python, Scratch, selected
  task, checkboxes, points, and panel state match. Start new attempt leaves the
  earlier one intact. Save As and opening the portable archive keep the correct
  project association and external-change protection.
- Switch among two lesson programs and an ordinary file. The panel follows the
  active lesson project, never leaks progress into the ordinary file, and does
  not create copies through task selection or starter clicks.
- Exercise Instructions, Assembly, Program, and Controls links from the pilot
  lesson. Markdown traversal remains blocked, external links keep their current
  behavior, and the lesson robot is selected when another model is open.
- Complete and uncomplete manual tasks; test device checks connected, wrong
  ports, and disconnected. Points equal the sum of completed task weights after
  every change, archive save, and recovery. Only verified evidence gets a
  verified label.
- Insert an unrelated catalog block and a Scratch block during a lesson; use
  a normal expression and edit an existing block variant. The full catalog and
  level buttons work, while **For this task** contains its recommendations.
- Capture English and Russian screenshots at 1024×768 and 1440×900 with panel
  expanded/collapsed, Console open, and Scratch/device panel open. Verify no
  clipped controls, unusable editor, hidden progress control, or inaccessible
  task action. Check keyboard and screen-reader names.
- Run focused core and Qt lesson tests, introductory end-to-end tests, the
  complete test suite, and Ruff after code changes. Exercise the documented
  first lesson manually before updating the current user guides.

## Delivery evidence (2026-10-17)

The core lesson, Qt lesson, and catalog discovery/navigation checks passed
(60 tests). Ruff, translation compilation/checks, documentation links, and
`git diff --check` passed. The first-drive lesson was opened in the GUI; its
task panel, progress control, and separate Markdown instructions were inspected
in English and Russian at 1024×768 and 1440×900, with Console and Scratch or
the device panel open.

The complete suite was attempted but did not finish: a firmware EV3 test reports
`PASSED` and then waits indefinitely while pytest-asyncio shuts down its default
executor. The introductory virtual-hub test also times out waiting for a simulated
connection in this environment. These checks do not establish physical-hub
behavior.

## Task-card refinement evidence (2026-10-18)

The panel now occupies the full right dock height, including with Console open.
Scratch uses the same dock tabs, and switching to it exposes the toolbar progress
chip beside hub connection. The pilot lesson has localized Markdown for all six
task cards. A visible Markdown link was clicked in a Qt test; the introduction
was also exercised through a revealed hint, repeated starter-file opening, and
panel collapse. English and Russian layouts were inspected at 1440×900 and
1024×768, respectively. The focused lesson and catalog suite passed (62 tests),
as did Ruff, translation validation, documentation links, and diff whitespace
checks. The earlier full-suite and physical-hub limits still apply.

The instruction viewer was then moved into the existing Help workspace. All
25 bundled lessons now declare one localized full instruction file; the pilot's
six former stage files were merged with stable section anchors. The Help view
was checked at 1024×768 and 1440×900, including direct section navigation,
ordinary local and program links, narrow-window panel collapse, and changing
languages while a section is open. The focused lesson suite passed (45 tests).
