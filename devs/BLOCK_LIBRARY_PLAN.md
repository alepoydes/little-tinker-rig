# Block library work plan

Status: complete. Baseline and verification date: October 16, 2026.

The source-derived [inventory](BLOCK_LIBRARY_INVENTORY.md) accounts for all 253
templates. Consolidation defines 191 families, with 250 selectable forms
and three compatibility aliases. Family metadata, validation, and exact-variant
filtering are implemented in the core. The desktop exposes families, exact variant
selection for insertion, category branches, and independent level/view buttons.
Favorites, Recent, and Frequent use local family references and successful
insertion records, including both Scratch paths. Explicit existing-program variant
editing, compact additional parameters, and Block Editor catalog controls are
implemented. Titles and descriptions cover the family operations, with English
and Russian user help. The final integration evidence is recorded below.

The objective is a smaller, easier-to-find set of block cards with explicit
operation variants, predictable Python behavior, and personal navigation.
This plan implements the [library redesign target](UX_DESIGN.md#library-redesign-target)
using the findings in the [catalog research](BLOCK_CATALOG_RESEARCH.md).

## Scope and established decisions

- Separate button groups select the level and the library view.
- Levels remain Beginner, Intermediate, Advanced, Expert, and All. Difficulty
  remains cumulative and does not restrict editing existing Python.
- Views are Catalog, Favorites, Recent, Frequent, and For this lesson.
- Subject categories are expandable tree branches replacing module headings.
  The eight proposed categories are listed in the
  [research](BLOCK_CATALOG_RESEARCH.md#121-main-sections); detailed membership is
  determined by the inventory. No extra Python/devices/model hierarchy is added.
- Related operation variants share a card. Essential arguments are prominent;
  additional options remain accessible, and active behavioral differences are visible.
- Personal views reference the same block families without duplicates within a view.
- For this lesson uses the existing current-stage palette. New laboratories,
  learning sequences, and a prescribed function-based program architecture are
  outside this work. Functions remain ordinary Python tools.
- Developer artifacts are English-only. GUI, block descriptions, and affected
  user help retain English and Russian support under the [project rules](../AGENTS.md).

The baseline catalog had 253 templates in 23 module groups, including 147 with the
action role. The resulting catalog has 191 families, including 105 action families.
These counts follow from the audit; no useful operation was removed merely to
meet a numerical quota.

## Delivery sequence

| Phase | Deliverable | Depends on |
|---|---|---|
| 1. Inventory | Every current template mapped to a proposed family and destination | Existing research |
| 2. Contracts and interaction design | Concrete family, variant, identity, and navigation rules | 1 |
| 3. Working consolidation pilot | Six families covering 23 current motor/drive cards | 2 |
| 4. Full catalog revision | Audited families, parameters, categories, and levels across the library | 3 |
| 5. Catalog navigation | Level/view buttons, category tree, search, existing lesson integration | 3; final coverage from 4 |
| 6. Favorites, Recent, and usage tracking | Persistent personal references and a shared insertion record | 5; stable identities from 2 |
| 7. Frequent | Bounded local frequency statistics and stable ranking | 6 |
| 8. Integration and documentation | Verified release candidate, localized help, final inventory report | 4–7 |

Phases 4 and 5 can progress independently once the pilot establishes the contracts.
Each phase produces a reviewable change with its own appropriate checks and local
commit. Publishing is separate from completing this plan.

## 1. Audit every existing block

Produce one inventory covering all current identities, including their existing
source definition, insertion kind, level, and module. For each entry record:

- proposed family and variant, subject category, and introduction level;
- required and optional arguments, defaults, units, result type, and device support;
- whether it waits, when it completes, and any state left active after completion;
- disposition: keep, consolidate, relocate, or remove a redundant catalog entry;
- compatibility needs, including existing examples, lesson references, and help anchors.

Distinguish catalog removal from removal of supported Python or recognition forms.
Separate real semantic differences from alternate spellings and optional-argument
combinations. Review model actions for their relevant catalog destination without
developing new lessons or removing their availability from complete discovery.

**Done when:** 253/253 baseline templates are accounted for; unexplained omissions
and ambiguous merges are resolved; proposed family counts and category sizes are
reported. If the catalog changes during the work, update the baseline explicitly.

## 2. Specify the shared contracts and interaction

Turn the inventory into a concrete representation before changing the collection
format. Specify the smallest change needed to existing source metadata and loading;
keep one authoritative definition for code and descriptions. Review the proposed
contract changes before implementation.

Resolve the following together:

- Stable family identity, variant identity, and mapping from existing template IDs.
  Category moves and translations must not change personal references.
- Where category membership and variant information live, how defaults are inherited,
  and how older or external collections without new metadata continue to load.
- Required, optional, and omitted arguments. Omission is not equivalent to passing
  `None` or eagerly evaluating a default expression.
- Reuse of API enums, Boolean values, existing operator choices, and editable
  expressions. Operation selection maps to ordinary Python; it does not introduce
  a runtime enum for every menu.
- Variant switching, preservation of compatible arguments, result-type/context
  checks, and visible changes to waiting, units, or final device state.
- Level rules for families and advanced variants. A hidden choice must not erase
  a value already present in a program.
- Lesson references to old IDs: selecting a family must not expose variants that
  the current stage did not permit. Preserve existing operation restrictions.
- Scope for document-defined functions. Equal names in different files must not
  share personal records accidentally.
- Search, level, view, and lesson interactions; unavailable states; restoration
  of selection and expansion after clearing search or changing language.

Prepare a compact UI layout with separate level and view buttons and a category
tree. Check readable English and Russian labels at the minimum sidebar width;
allow wrapping where necessary rather than reverting to drop-down selectors.
Specify icon tooltips, keyboard access, and active states. Personal views retain
their own ordering rather than forcing chronological results into category order.

The research proposes 12 recent/frequent entries and a 30-day frequency window.
These are initial defaults to settle in this phase, not fixed limits on Favorites.

**Done when:** concrete examples cover an optional argument, an API enum, a
different-method variant, and a returned value; source outcomes and migration
behavior are unambiguous; the layout fits without adding a new navigation layer.

## 3. Implement a representative pilot

Use the [six audited families](BLOCK_CATALOG_RESEARCH.md#142-first-consolidation-candidates):

| Family | Current cards |
|---|---:|
| Turn motor by angle | 4 |
| Move motor to position | 6 |
| Run motor for time | 2 |
| Run motor until stalled | 5 |
| Stop motor | 3 |
| Drive a distance | 3 |

Implement the shared loading, validation, expansion, recognition, and card-editing
behavior needed for these families. Include both argument variants and method
selection, rather than validating only the simplest consolidation case.

Update Block Editor support and preview sufficiently to create and edit the new
definitions without a second handwritten catalog. Preserve imports, result types,
helper ownership, typed insertion, and one Undo operation per accepted edit.

Existing programs retain their source and effects. Preserve evaluation order,
including keyword argument expressions with side effects. Catalog regrouping or
reloading must not silently rewrite source or replace an existing helper body.

**Done when:** the 23 cards are represented by six discoverable entries, all
audited behavior remains expressible, and both existing and newly inserted source
work in document and Scratch contexts. The mechanism is reusable by other families.

## 4. Apply the audit across the catalog

Convert families in small domain batches: setup and devices; movement and control;
measurements and input; light and sound; Python expressions and flow; collections,
functions, tasks, and communication. Review composite model actions within the same
inventory rather than treating them as a new curriculum project.

Give each entry a concise action/value title, meaningful defaults, visible units,
and precise behavior documentation. Keep reading settings distinct from changing
them, coordinate reset from physical movement, and an expression from an assignment.
Do not merge operations solely because they call the same method name.

Assign subject categories and reassess levels after consolidation. Keep role colors
independent of category membership. Retain existing IDs through the mapping decided
in phase 2; migrate bundled references without weakening lesson restrictions.
Use historical recognition only where an actual source form requires it.

Update block-description translations and generated help alongside each batch.

**Done when:** the complete audit is implemented, category membership is coherent,
duplicate catalog entries are eliminated, and useful existing operations remain
available. Report resulting families and visible cards per level against the baseline.

## 5. Build navigation and integrate existing lessons

Replace the level selector with exclusive level buttons and add an independent
view button group. Render the subject categories as stable tree branches. Preserve
expansion where possible and hide empty branches under active filters.

Search across categories using localized titles, English API names, synonyms, and
descriptions, with one result per family. Prioritize direct matches over incidental
words in source examples. Clearing search restores the prior view and tree state.
Explain matches hidden by active filters and provide the existing explicit way to
broaden discovery; All does not bypass type or lesson constraints.

Connect For this lesson to the current stage's existing blocks and allowed
operations. Required cards must not disappear because of the general level choice.
Preserve access to the existing Show all blocks behavior and restore the user's
ordinary level when leaving the lesson context. Define the unavailable state when
no lesson is open. Do not require a connected hub for offline program construction.

**Done when:** buttons, tree, search, typed insertion, and lesson restrictions work
together in both languages. Filtering, language changes, and collection reloads
preserve source, unfinished edits, and document/Scratch state.

## 6. Add Favorites, Recent, and one usage record

Store personal data locally using stable family references. Favorites support
adding/removing links and explicit ordering. Recent contains distinct families;
reusing one moves it to the front. Reuse across variants does not create duplicates.
Unavailable favorites remain recognizable and can recover after collection reload.

Record successful explicit catalog insertions through dragging, double-click,
and the insertion button in both document and Scratch. Use one consistent success
event; do not infer use from rendering, code recognition, or refreshes. Capture the
bounded data needed by Frequent here so the two views do not develop separate counters.

Cancelled or rejected insertion, program execution, opening a document, and automatic
helper insertion do not count. Undo retains a recorded use; redo does not count again.
Personal records do not save old parameter bindings or rewrite project files.
Provide clearing/reset controls while keeping Favorites independently controlled.

**Done when:** records survive restart, language changes, and category moves;
successful uses count once across both insertion paths; unavailable or filtered
entries do not silently delete favorites; document-scoped names remain isolated.

## 7. Add Frequent

Use the bounded usage records from phase 6 with the window settled in phase 2.
Define ranking and deterministic ties, expire old counts, and show an honest empty
state before use exists. No remote service or account is required.

Keep the displayed order fixed during selection, editing, and dragging. Refresh
usage-based ordering when entering the view again. Never reorder the subject
category tree according to personal frequency.

**Done when:** repeated uses rank correctly, expired uses stop contributing,
variants aggregate into one family, reset works, and navigation does not move
the card a user is interacting with.

## 8. Verify integration and finish documentation

Validate behavior at the boundaries where consolidation can cause errors:

| Area | Evidence required |
|---|---|
| Python semantics | Representative calls retain arguments, evaluation order, units, results, waiting, and stop behavior |
| Compatibility | Old source and external collections load; help and lesson references resolve; existing helper bodies survive |
| Editing | Variant changes, expression insertion, imports, Undo/Redo, and Scratch remain consistent |
| Discovery | A finite move, motor stop, measurement, condition, and function can be found without module names |
| Personal views | No duplicate rows; correct counting, persistence, expiration, and document scope |
| Interface | Both button groups, tree, search, keyboard access, narrow layout, and both languages work together |

Extend focused tests for shared mechanisms and interactions, not one repetitive
test per card or assertions that mirror implementation details. Use existing
programs and virtual device traces for behavior checks; real-hardware claims need
hardware evidence and must remain separate from simulator results. Run the relevant
small test set after each change, then the repository's required integration checks
for the completed revision. Record any necessary exception to the quick-test budget.

Maintain English developer documentation and localized end-user help, generated
block descriptions, and screenshots where the interface changes. Validate links,
translation coverage, packaging of new assets, and startup with saved settings.
Replace planned language with implemented behavior only for completed work.

**Done when:** all phases meet their criteria, the final inventory reconciles with
the baseline, appropriate checks pass, and the result is saved in local commits.

## Primary integration points

- [Metadata](../little_tinker_rig/core/block_metadata.py),
  [snippets and collections](../little_tinker_rig/core/snippets.py), and
  [parameter choices](../little_tinker_rig/core/parameters.py): family contracts,
  loading, recognition, expansion, and editing.
- [Library](../little_tinker_rig/qt/library.py),
  [application](../little_tinker_rig/qt/app.py), and
  [Block Editor](../little_tinker_rig/qt/authoring.py): cards, navigation,
  authoring, application settings, and successful insertion.
- [Scratch](../little_tinker_rig/qt/scratch.py),
  [lesson UI](../little_tinker_rig/qt/lessons.py), and
  [help](../little_tinker_rig/qt/help.py): secondary insertion paths, existing
  stage restrictions, and stable documentation links.

These are integration points to inspect, not a requirement to introduce a new
service or abstraction for each concern.

## Delivery audit

| Phase | Implemented result and evidence |
|---|---|
| 1. Inventory | The [generated inventory](BLOCK_LIBRARY_INVENTORY.md) records all 253 identities, source links, parameters, units, defaults, levels, variants, categories, and authored behavior. No source identity was removed. |
| 2. Contracts | [Family metadata and editing](DESIGN_SPEC.md#191-catalog-family-metadata) define inheritance, aliases, exact filtering, shared fields, explicit edits, and compatibility. Older uncategorized collections retain their module headings. |
| 3. Pilot | The six motor/drive families account for all 23 audited forms. Defaults, fixed options, enum choices, returned expressions, imports, typed inputs, and one-edit Undo use the shared variant mechanism. |
| 4. Full catalog | All 23 source modules are classified into eight branches and 191 families; 250 forms remain ordinarily selectable and three are compatibility aliases. Families retain distinct reads/writes, assignment/value forms, and reset/movement semantics. Introduction levels remain attached to exact forms. |
| 5. Navigation | Separate level/view buttons, category branches, localized/API search, matching variant previews, keyboard access, and exact lesson-stage palettes are implemented. EN/RU screenshots cover the new navigation and editing controls. |
| 6. Personal records | Family references support ordered Favorites, unique Recent, all successful program/Scratch insertion paths, independent clearing, persistence, unavailable links, and recovery-safe document scopes. First save transfers unnamed-document links and counts. |
| 7. Frequent | One local insertion record supplies the latest 30 UTC calendar days; deterministic ranking is capped at twelve entries and remains fixed until the view is entered again. |
| 8. Integration | User guides, definition-format help, developer contracts, translations, screenshots, inventory checks, and CI are updated. Final verification results follow below. |

The eight branch sizes are 18 Program, 15 Values, 19 Variables/collections,
8 Functions, 54 Movement, 42 Input, 18 Output, and 17 Devices/communication.
Cumulative family counts are **19 / 66 / 124 / 191** for Beginner through Expert;
All also shows 191. Grouping reduces ordinary cards by 62 (24.5%) and action cards
by 42 (28.6%). There is no additional hierarchy above the category branches.

Comparison with the captured pre-consolidation definitions confirms identical
identities, introduction levels, default expanded Python, imports, and helper
bodies for all 253 templates. `tools/catalog_report.py --check --verify-transitions`
also prepares and re-recognizes all **305** built-in family transitions with default
bindings while checking that previews preserve state and Undo history.

Focused behavioral checks cover side-effectful argument ordering, declaration
names, comments and string values, typed results, invalid/stale edits, exact lesson
aliases, personal ordering/counting/expiration, document isolation, and text/structural
Undo. Native Qt checks additionally exercised a Scratch variant edit with parent
Undo, keyboard activation, saved-settings startup, and Russian labels in a
930 × 620 window. Hardware evidence is unchanged: the revision uses source and
virtual-runtime checks and makes no new claim about physical robots.

Final verification:

- Full integration suite: **654 passed, 2 skipped**, 394.39 seconds. The run exceeds
  the quick-test budget because it includes the complete Qt/TUI, virtual-hub,
  firmware, lesson, and example-compilation suites. Eight warnings originate in
  the dependency's deprecated `semver.compare` call.
- The final argument-order safeguard was checked separately: **9 variant tests
  passed** in 2.16 seconds; all 305 default transitions still pass. No later
  application changes followed these checks.
- Ruff, Black (all 176 Python files), documentation links and language boundaries,
  translation coverage/compiled catalogs, UTF-8 without BOM, inventory freshness,
  and `git diff --check` pass. CI now checks the inventory and transitions too.
- Offline wheel and source-distribution builds succeed. Packaged source,
  translations, icons, help, and screenshots match the working tree. The source
  archive includes the inventory, tests, and documentation.
- The wheel installed in an isolated **Python 3.11.16** environment outside the
  repository passes catalog loading, variant preview/apply/Undo, Ruff formatting,
  localized-resource discovery, and virtual motor movement/completion checks.
  Core dependencies match the development versions.

The implementation is saved in local commits; publication is outside this plan.
