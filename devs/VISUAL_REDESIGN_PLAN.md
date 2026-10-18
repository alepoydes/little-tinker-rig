# Visual redesign implementation plan

Status: initial implementation delivered on 2026-10-18. The
[acceptance record](VISUAL_REDESIGN_ACCEPTANCE.md) covers that first pass; it
does not establish visual parity with the selected mockups. The remaining work
and its acceptance criteria are maintained in the
[reference design completion plan](VISUAL_REFERENCE_COMPLETION_PLAN.md).

The goal is a coherent robotics workshop interface: a distinct navigation rail,
readable rounded Python blocks, compact controls, and an illustrated lesson
companion. Both themes use the same layout and interaction model. The existing
[interaction design](UX_DESIGN.md) and [project rules](../AGENTS.md) continue to
govern editing, navigation, lessons, and hub control.

Exploratory images, prompts, screenshots, and the isolated Qt header probe remain
in locally ignored `report/design_concepts`. This plan is self-contained so an
ordinary checkout does not depend on those files. Commit implementation and
maintained documentation after each successfully verified stage; keep internal
design artifacts out of those commits.

## Agreed design requirements

- Combine the compact LittleTinker Rig wordmark, menus, document title, and
  window controls in one header row. Emphasize Rig with the accent color.
- Start file, history, and execution toolbar groups at the left edge. Put the
  expanding gap after those groups, before lesson progress and hub connection.
  Keep Upload, Run, and Stop distinct and directly available.
- Use a dark narrow workspace rail with clear active icons. Keep Program,
  Control, Help, Block Editor, and Assembly separate from document representation
  and catalog filtering. Tooltips carry workspace names.
- Keep separate icon groups for catalog levels and views, nested category
  branches, stars on cards, and context-menu variants. Preserve current discovery
  semantics and the availability of ordinary Python editing.
- Use rounded colorful blocks with readable source, clear nesting, compact
  titles, and recognizable editable inputs. Keep a family consistent across the
  catalog, program, Scratch, and preview.
- Give tasks clear numbering, selection and completion states, progress, points,
  inline links, and meaningful illustrations. Collapse the panel into a progress
  chip beside hub connection and release its width. Keep the complete lesson
  instruction in Help and all normal workspaces available.
- Deliver explicit Light and Dark choices with a saved preference. Use Light for
  installations without a saved choice. Following the operating-system theme is
  optional follow-up work, not a prerequisite for this delivery.
- Keep developer documentation and comments English-only. Localize new interface
  and lesson content through the existing English and Russian resources.

## Technical starting point before implementation

The original [window setup](../little_tinker_rig/qt/app.py) used a frameless
window and a [custom title bar](../little_tinker_rig/qt/window.py), but stacked
that bar and the menu vertically. The isolated header probe confirmed a shared row
and working menu actions at 930 and 1380 logical pixels on Qt 6.11.2 using the
offscreen platform. Desktop move, resize, snapping, and keyboard integration
remain to be verified. The implementation used the existing supported Qt
baseline; a newer native title-area API was not required.

At baseline, appearance spanned widget styles, custom painters, text formats,
HTML, and fixed SVG strokes. In particular, the
[block renderer](../little_tinker_rig/qt/editor.py) multiplied color over already
painted text. Its compositing strategy needed evaluation for dark backgrounds;
a global stylesheet alone could not implement the design.

[Semantic roles](../little_tinker_rig/core/presentation.py) are shared with other
frontends and also accept source-authored color values. Resolve Qt theme colors
at the Qt boundary. Preserve role identities, source definitions, and explicit
custom-color meaning. Keep Qt theme state out of the core and TUI.

## Delivery sequence

| Stage | Deliverable | Dependencies |
| --- | --- | --- |
| 1 | Baseline, shared theme values, state colors, and icon support | Current implementation |
| 2 | Unified header, aligned toolbar, navigation rail, and appearance controls | 1 |
| 3 | Catalog tree, filter buttons, cards, and discovery feedback | 1–2 |
| 4 | Program blocks, Python, parameters, Scratch, and previews | 1–3 |
| 5 | Lesson panel, Help, and instructional illustrations | 2–4 |
| 6 | Control, Assembly, devices, dialogs, and remaining surfaces | 1–5 |
| 7 | Cross-platform acceptance, packaging, documentation, and final polish | 1–6 |

Each stage ends with focused functional checks, visual inspection of the affected
screens in both themes, and a short commit. Large stages may use several coherent
commits. A completed stage does not imply that later stages are already styled.

## 1. Baseline and shared theme support

Capture current representative screens and control locations before editing.
Include a populated First drive lesson, a long nested program, invalid inline
input, Python and Scratch drafts, Help, and all other workspaces. Keep captures
and benchmark results in `report`. Use temporary projects and isolated settings
for fixtures so inspection cannot alter the user's work.

Introduce a Qt theme module, distinct from the existing source-definition
`appearance.py` controls. Define named values for surfaces, text, selection,
focus, errors, disabled controls, semantic blocks, syntax, borders, spacing,
corners, and typography. Adapt the existing SVG icon family through a shared
loader that accounts for theme, state, and display scaling. Preserve meaningful
multicolor parts, such as completion and favorite indicators.
If a font or icon asset is bundled, include its redistribution license and
package resources; rendering must not depend on an online font or icon service.

Connect standard widget palettes and styles, painter colors, and text/HTML
formats to this shared source. Establish how custom colors retain their hue
while foregrounds remain readable. Record initial spacing and font values from
real Qt rendering, including Cyrillic. Avoid fixed row heights that clip larger
fonts. Audit the editor's blend mode before selecting a dark block palette.

Apply theme changes to existing widgets and repaint or invalidate visual caches.
Do not reconstruct documents, editors, Scratch cells, or lesson projects. All
open application windows should follow the selected appearance without asking
an invalid draft to commit. Save the preference using the existing settings
mechanism and preserve the block-intensity preference.

**Complete when:** the shared mechanism can render representative widgets, block
colors, syntax, and Markdown in both themes; switching preserves drafts, undo,
selection, and scroll state; the baseline and remaining surface inventory are
recorded. Full workspace styling is delivered in the later stages.

## 2. Header and application shell

Replace the stacked title/menu layout with one horizontal header. Keep the real
QMenuBar and existing actions; retain a stable reference to the embedded menu
bar. Allocate a compact brand area, menu width, an eliding document title and
drag area, and the window buttons. Menus and buttons must not start a window
drag. Preserve keyboard access, maximize/restore behavior, fullscreen exit,
window resizing, and access to menus in fullscreen.

Align the toolbar from the left across its available row. Keep file actions,
Undo/Redo, and Upload/Run/Stop grouped before the expanding gap. Connection and
lesson controls stay together at the right. At compact widths, shorten labels
or use their named icons before sacrificing important actions or the drag area.
Stop and disconnect must continue to bypass invalid edit validation.

Style the workspace rail, document tabs, dock headers, splitters, and status
area consistently. Give active, hovered, focused, busy, and disabled elements
distinct treatments. Add a compact appearance menu for Light/Dark and move the
existing block-color intensity control there, retaining its saved value.
Update affected user guidance in both languages.

**Complete when:** the header fits both languages at the nominal minimum width;
menus and existing commands retain their owners; action groups start at the
left; lesson and connection status remain usable; native window interactions
are checked on available desktops, with outstanding platforms explicitly listed.

## 3. Catalog and discovery feedback

Update `library.py` and `navigation.py` to use shared dimensions and colors.
Keep search, level choices, and view choices compact and visually separate.
Use measured title/code geometry, with room for favorite stars and variant
information. Long translated titles must not overlap stars or erase the source
preview. Preserve full descriptions in help and tooltips.

Apply the same role colors used by the editor. Keep tree indentation, branch
expansion, personal ordering, empty views, search misses, and pinned creation
searches understandable. Preserve expansion and selection across theme changes.
Do not change family counts, levels, variants, applicability, or usage statistics
as part of styling. Empty information badges must not reappear.

**Complete when:** favorites, variants, nested filtering, personal views, and
creation guidance remain functional by pointer and keyboard; English and Russian
cards remain legible in both themes at compact catalog widths.

## 4. Editor and block presentation

Update `editor.py`, `annotations.py`, `parameters.py`, `code.py`, `scratch.py`,
and the Block Editor preview through shared visual components. Rework painting
order or compositing as necessary to give readable light and dark card surfaces
without obscuring source text. Use restrained rounded boundaries, compact title
bands, and clear editable fields. Preserve generic Python and existing block
display modes; titles are presentation, not added source statements.

Use consistent geometry for painting, parameter editors, hit testing, drag
previews, and insertion indicators. Account for wrapping, multiline strings,
folded blocks, long expressions, partial visibility, and nested suites. A drop
after the final loop must look different from a drop inside that loop. Avoid
clipped corner artifacts at viewport edges and cumulative darkening of nesting.

Selection, keyboard focus, diagnostics, and drop feedback must coexist. Missing
name help continues to lead with the concrete creation or ordering fix. Runtime
errors and text search remain visible. Apply the theme to syntax highlighting,
line numbers, completion popups, parameter units, and validation messages.

**Complete when:** catalog, inserted blocks, Scratch, and preview share a visual
language; parameter editing and pointer/keyboard moves agree with displayed
geometry; Undo and representation changes preserve document state; long-program
measurements show no material regression requiring resolution.

## 5. Lessons, Help, and illustrations

Restyle task headers and authored content with numbered steps, clear completion
indicators, a distinct selected task, progress, and points. Preserve completion
semantics and existing link behavior. Task actions remain inline links. Keep
the full-height dock, narrow-window overlay, and collapsed progress chip. Hiding
the panel must release its space in every workspace, including Help.

Theme Markdown, code examples, links, search matches, history controls, and Help
contents. Opening a lesson still opens its complete instruction; section links
scroll within that document without creating duplicate tree pages. Preserve
search, reading position, and page identity when changing appearance.

Use First drive as the complete illustration pilot: actual rolling base and
ports, motion direction, and distance to an obstacle. Derive build visuals from
verified model assets or authored diagrams. Give instructional images localized
captions and alternative text; avoid language baked into otherwise reusable
images. Check legibility in both themes and at compact widths.

First drive is the only bundled guided lesson. Bundled Pybricks examples are
sample projects with their own model/build resources, not task-card lessons.
Keep lesson images local, include them in lesson resources and export, and
verify installed/offline use. Illustrations are content assets; future guided
lessons should follow the same authoring guidance.

**Complete when:** First drive is usable end to end with accurate illustrations;
task collapse, links, progress and points work unchanged; lesson image coverage
is accounted for; supported language resources and exported projects contain
the required content.

## 6. Remaining workspaces and dialogs

Complete the theme and component pass over manual Control, the device monitor,
Console, Block Editor properties and validation, Assembly and its viewer chrome,
connection and firmware dialogs, variant forms, tooltips, and error surfaces.
Keep all existing controls represented. Preserve physical LEGO part colors in
the model viewer while adjusting its background, labels, and selection cues.

Distinguish app-owned dialogs from operating-system dialogs. Style the former
and verify the latter on the platform; do not promise that an application palette
can recolor native file dialogs. Check momentary control feedback, neutral on
release/focus loss, and immediate access to Stop and disconnect.

**Complete when:** every app-owned surface uses the shared design values or has
an intentional semantic color; no hardcoded light surface makes the dark theme
unreadable; controls and previews remain usable with auxiliary panels open.

## 7. Acceptance and delivery

Use the following matrix for final inspection. Fully exercise the compact
Russian and populated lesson cases in both themes; use representative coverage
for the remaining combinations rather than duplicating identical checks.

| Dimension | Required coverage |
| --- | --- |
| Appearance | Light and Dark; live switching; reopening the application |
| Language | English and Russian, including long labels and changed language |
| Window | Nominal 930 × 620, 1366 × 768, and larger desktop; maximized/fullscreen |
| Scaling | Available Windows/Linux desktop configurations at 100%, 150%, and 200% |
| Content | Empty and long programs; nested suites; long fields; multiple files; generic Python |
| Panels | No lesson; tasks open/collapsed/overlay; Console; Scratch; hub/devices |
| Input | Pointer and keyboard; menus; invalid draft; missing declaration; runtime error |
| Hub | Disconnected, busy, running, and error; Stop/disconnect with an invalid field or modal dialog |

Run existing relevant suites first. Add focused regressions only for new
behavioral risks such as live theme changes retaining drafts, header command
routing, and hit geometry after card layout changes. Use screenshots to inspect
appearance; do not substitute brittle tests of decorative pixel values.

| Area | Existing verification starting points |
| --- | --- |
| Catalog | `test_catalog_navigation.py`, `test_catalog_discovery.py`, `test_ux.py` |
| Editor | `test_block_display.py`, `test_drag.py`, `test_editor_workflows.py`, `test_workspace_interactions.py`, `test_scratch.py` |
| Lessons and Help | `test_lesson_ui.py`, `test_first_steps.py`, `test_languages.py` |
| Other workspaces | `test_authoring.py`, control cases in `test_workspace_interactions.py`, `test_ldraw.py` |

Use the existing uv environment for checks. Run `tools/check_docs.py`,
`tools/translations.py check`, and applicable lint/test commands. Record comparable
editor measurements with `tools/benchmark_editor.py` before and after painting
changes. At final integration, run the broader regression suite and verify an
installed build includes themes, icons, fonts if bundled, and lesson images.
Do not add a CI or dependency migration project to this visual redesign.

Exercise the documented introductory lesson manually. Update English and Russian
user guides where visible controls or workflows change, and update the maintained
English design documents to describe delivered behavior. Record desktop checks
separately from offscreen checks and simulated hub checks separately from hardware
checks. Unavailable platform verification remains explicitly pending; it is not
reported as a pass.

**Complete when:** the agreed control inventory is accounted for, both themes are
coherent across workspaces, the acceptance evidence is recorded, affected guides
match the application, and every completed stage has a verified commit.
