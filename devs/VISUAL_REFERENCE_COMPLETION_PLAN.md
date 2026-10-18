# Reference design completion plan

Status: in progress (2026-10-18). The shell, palette, catalog hierarchy,
program cards, compact Scratch layout, and several auxiliary surfaces have
verified visual passes. Long-line behavior, complete lesson and dialog review,
and final desktop acceptance remain open. The catalog wraps long titles at
compact widths and recalculates card height when its width changes.
The semantic block palette now uses the stronger blue, amber, green, and orange
families from the selected reference. Catalog cards and program blocks share
those colors, with clearer borders, separated program cards, and readable
header badges. Plain imports no longer appear as colored control blocks. The
selected workspace and catalog filters have stronger blue states, and Run/Stop
icons keep contrast against their filled buttons. Stage 3 now includes a fixed
source-line gutter outside the text viewport; long-line handling, Scratch
parity, and a full pointer/keyboard audit remain. At compact widths Scratch
now docks below the program so both structural editors keep enough horizontal
room for Python; at wider widths it returns to the right. Manual dock moves
stop automatic placement, and unfinished parameter input survives relocation.
Scratch diagnostics now recognize names initialized in the open program and
refresh when those declarations change, removing false missing-name emphasis
without excusing reads before a fragment's own later assignment.
The structural view now shares Python keyword, number, string, and comment
highlighting with the ordinary text editor; theme switches rehighlight it.
Stage 2 now gives top-level catalog categories semantic icon badges and
stronger type hierarchy; nested construction groups use a smaller color marker
while retaining tree expansion and keyboard navigation. The search field now
has a theme-aware search icon and built-in clear action without adding height.
Empty catalog views now present their localized reason and view icon within the
catalog viewport, including Favorites and searches with no results, instead of
leaving a blank tree and a distant status label.
Control now places its controller and actions near the top instead of centering
them in empty height, and its monitor-start action has a visible labeled button.
With the device panel open at 930 × 620, the motor-assignment table remains
vertically scrollable but the whole Control page no longer gains a horizontal
scrollbar from Russian action labels. The narrow motor fields still need a
compact layout in a later Stage 5 pass.
Block Editor and in-editor search now use the same theme-aware SVG icon path as
the shell. This removes the opaque square artifacts from standard desktop
icons in Dark while preserving the existing actions and tooltips.
The Block Editor's New block action now uses the primary accent and a matching
icon in both themes, making the creation path visible beside its secondary
collection actions.
The device panel now omits empty metadata instead of showing a dangling
separator above the hub state.
Assembly load failures now show a localized recovery message instead of a raw
network exception, retranslate when the language changes, and clear after a
successful retry. The model viewport now has a themed loading/error placeholder
instead of empty space, with a scalable brand illustration; 3D-only controls
and hints stay hidden until a view exists. Offscreen captures cannot establish
live 3D rendering.
This follows the first-pass
[visual redesign](VISUAL_REDESIGN_PLAN.md) and uses the selected local mockups
in `report/design_concepts` as visual
references. Those images and comparison captures remain ignored by Git. The
existing [UX interaction contract](UX_DESIGN.md) and [project rules](../AGENTS.md)
remain in force.

## Target and observed gap

The target is a coherent robotics workshop interface in Light and Dark, with a
compact branded header, clearly grouped controls, a useful catalog, readable
Python blocks, and an illustrated lesson companion. It should feel intentional
in the real Qt application, with every existing control and editing behavior
accounted for. The mockups are a guide to hierarchy, color, spacing, and states;
they are not a pixel specification or a reason to remove working features.

Initial offscreen captures of a populated First drive project at 1380 × 880 and
930 × 620 show the main gap. The first pass introduced theme support and a
shared header/menu row, but the toolbar, tabs, catalog cards, editor blocks,
and tasks are still flatter and denser than the reference. The original fixed
320 px catalog left too little room for source at compact width; responsive
sizing now uses 270 px by default, but long lines can still be clipped. The
catalog and editor do not yet share the same clear card
hierarchy. Task progress and selected/completed states need stronger visual
structure. Screenshots of an empty document would conceal these problems, so
the populated project is the primary fixture.

The title/menu question has a concrete answer: the current frameless Qt window
already embeds a real `QMenuBar` beside the brand in a custom title row. The
remaining work is to refine spacing, truncation, contrast, keyboard access, and
native move/resize behavior. No new window framework is required.

## Delivery sequence

| Stage | Work | Acceptance evidence |
| --- | --- | --- |
| 0. Stabilize the in-progress pass | Finish or correct the current header, toolbar, theme-switch, and task-panel edits. Fix newly found runtime errors before visual iteration. | Focused tests pass; the populated lesson opens in both themes and languages; one short commit. |
| 1. Shell and responsive layout | Keep brand, menus, document title, and window controls on one row. Align file/history/execution actions at the left; make Run and Stop distinct when usable. Refine active document tabs, appearance and hub controls, and the collapsed lesson chip. Resize the catalog and lesson area responsively while preserving user-adjusted splitter widths. | At 930 × 620, all essential actions remain reachable and the editor retains usable width; at 1380 × 880, the hierarchy matches the reference. Menu access, drag, resize, maximize, shortcuts, and language switching remain functional. |
| 2. Catalog discovery | Give tree branches and block cards consistent indentation, category color, icon, title, code, favorite, and selected/hover states. Balance card height against scanning speed. Clarify the separate level and view icon groups and empty/search states. | Long English and Russian labels remain legible at minimum catalog width; nested groups, favorites, recents, frequent, lesson view, filtering, and context-menu variants work by pointer and keyboard. |
| 3. Program and Scratch blocks | Replace flat source bands with a restrained rounded block component that shares semantic color with catalog cards. Establish source/heading hierarchy, editable parameter affordances, selection, diagnostics, drag targets, and nested-suite boundaries. Preserve Python as code, including accurate line positions and hit geometry. Carry the visual language into Scratch and previews. | The populated nested program reads clearly in both themes, including the final block after a loop. Long fields and narrow windows are usable without hidden actions; pointer and keyboard moves, inline editing, Undo, Python transfer, and drag previews retain their contracts. Benchmark the renderer before and after. |
| 4. Lesson companion and Help | Give the full-height task panel a visible progress bar, score, numbered task states, strong current-task focus, compact links, and illustration sizing that supports reading. Keep collapse/reopen and the narrow overlay. Align Help navigation, instruction styling, and Console/dock chrome with the same system. | First drive can be followed end to end; task completion/progress and links update correctly; collapsing the panel releases its width; the full instruction remains one document; no content is clipped at compact width. |
| 5. Remaining surfaces | Finish Control, Assembly, Block Editor, devices, connection/firmware and variant dialogs, errors, tooltips, status, and empty states. Correct contrast and spacing where generic widgets still show through. | Every app-owned surface is inspected in both themes, including invalid fields, disabled/busy states, and open auxiliary panels. The model retains meaningful part colors. |
| 6. Final acceptance | Recheck English/Russian, Light/Dark, wide/compact, empty/populated, lesson open/collapsed, Console open, disconnected/connected/busy. Update affected guides and translations; verify packaged assets and introductory path. | Relevant automated tests, lint, documentation and translation checks pass. Record visual comparisons and remaining platform limits. Commit each verified stage separately. |

## Implementation boundaries

- Maintain a single source of visual tokens for both themes. Favor shared card
  geometry and semantic roles over isolated stylesheet fixes. Keep custom source
  colors meaningful and keep comments and developer documentation in English.
- Responsive rules must preserve manual splitter choices. Do not force a resize
  on every window change or silently hide command actions. Compact mode may
  remove button captions while retaining icons, tooltips, accessible names, and
  keyboard shortcuts.
- Do not enable text wrapping in the structural editor until paint, hit testing,
  parameter positions, selection, and drag geometry support it. A narrower
  catalog, better source viewport, and clear horizontal scrolling are safer
  first steps for long lines.
- Keep the current lesson model: a collapsible task panel and one complete Help
  instruction, with ordinary workspaces and blocks still available. Visual work
  must not change project identity, task completion rules, or generated Python.
- Keep design screenshots and exploratory files in ignored `report`; commit only
  implementation, tests justified by behavior risks, localized user content,
  and maintained English developer documents.

## Review method

Capture the same representative project after each stage at 1380 × 880 and
930 × 620 in Light/Dark and English/Russian. Compare it with the selected
reference for control hierarchy, alignment, contrast, card density, source
legibility, progress, and illustration use. Also inspect the remaining
workspaces and edge states named above. Fix visible discrepancies before
declaring a stage complete; a passing unit suite alone is not visual acceptance.

Use focused functional tests for new behavior and run the relevant existing
editor, catalog, lesson, Help, workspace, and localization suites. Run Ruff,
`tools/check_docs.py`, and `tools/translations.py check`; measure long-program
rendering when editor painting changes. Verify a wheel from outside the checkout
contains new assets. Normal desktop window-manager and Windows checks require
those environments; record them separately from offscreen evidence rather than
reporting them as passed.
