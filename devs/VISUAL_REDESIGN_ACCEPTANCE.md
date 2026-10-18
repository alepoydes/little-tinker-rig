# Visual redesign acceptance record

Date: 2026-10-18. This record describes the delivered Qt interface and the
verification that was possible in the development environment. Design exploration
images and screen captures are local, ignored files under `report/design_concepts`;
they are not required for a checkout or installed package.

## Delivered interface

- Light and Dark use the same layout and can be switched without rebuilding open
  documents. The preference is saved; Light is the default on a fresh install.
- A shared title and menu row leaves file, history, and run controls at the left
  of the toolbar. The lesson progress chip and hub control remain at the right.
  The workspace rail, catalog levels and views, program blocks, Python, Scratch,
  Help, lessons, dialogs, device monitor, and Block Editor use the shared palette.
- Semantic block colors remain distinct in both themes. Program blocks have a
  compact title band and rounded outer corners; input, drag, and insertion
  geometry still follows the existing source representation.
- First drive, the only bundled guided lesson, has authored build, motion, and
  obstacle diagrams, localized captions and alternative text, and the same
  complete instruction in Help. Bundled Pybricks sample projects keep their
  available model/build resources; they are not guided lessons with task cards.
- The LEGO viewer changes its background with the theme while keeping model
  part colors. The manual controller deliberately keeps a dark hardware surface
  in both themes. Native file choosers retain the operating system's appearance.

## Verification

| Area | Evidence | Result |
| --- | --- | --- |
| Visual inspection | Offscreen Qt 6.11.2 captures of Light/Dark, English/Russian, 1380 × 880 and compact 930 × 620 windows, with populated program, Scratch, lesson, Help, Control, Block Editor, and Assembly views | Checked for legibility, clipping, control placement, and Cyrillic labels |
| Live appearance | Focused tests covering invalid parameter drafts, an open Python edit dialog, and multiple windows | Passed; document state and dialog colors retained |
| Lesson workflow | Opened First drive and inspected its full Help instruction, task cards, and three diagrams in the checkout; the installed wheel loaded the lesson, six cards, Help text, and an illustration | Passed within those scopes |
| Selected regression suite | 71 catalog, discovery, block display, and drag tests; 12 editor/window tests; 34 workspace and Scratch tests; 25 Block Editor tests; 12 language tests; 8 lesson UI tests; 13 LDraw tests | 175 passed; 2 additional OpenGL-dependent LDraw tests skipped in this environment |
| Editor rendering | Baseline and post-change 1000-line benchmark runs through `tools/benchmark_editor.py` | About 1.97 s before versus 1.99 s on repeat after rounding; no material measured regression |
| Packaging | Offline `uv build --wheel`, offline target installation, and smoke launch from outside the checkout | Passed; 30 Qt SVG icons, First drive diagrams, Russian translation, and lesson content present |
| Static checks | Ruff, documentation link check, translation check | Passed |

Two offscreen hub tests still time out while connecting:
`test_qt_upload_reports_worker_output_progress_and_failure[False]` and
`test_first_lesson_build_save_run_and_reopen`. Both fail at the same connection
wait on an archive of commit `6699455`, before the redesign. They are recorded
as existing test-environment limitations, not as passes or as evidence about
physical hub behavior. The introductory GUI path was exercised through block
creation and editing before that connection wait.

The offscreen platform cannot establish desktop window-manager behavior. Native
move, resize, snapping, fullscreen keyboard handling, high-DPI scaling, native
file-dialog appearance, and Windows rendering remain to be checked on those
desktops. The offscreen platform also cannot display the OpenGL lesson model;
the renderer is covered by synthetic EGL checks, not a physical desktop or hub.
Hub hardware interaction was outside this visual acceptance pass.

## Follow-up when those environments are available

On Windows and a normal Linux desktop, exercise the title/menu row at 100%,
150%, and 200% scaling; drag, resize, maximize, snap, and restore the window;
open menus by mouse and keyboard; open a lesson with the task panel and Console;
switch themes with an invalid input still open; and inspect the model viewer and
native file chooser. Confirm the hardware Stop and disconnect controls remain
reachable while a dialog is open. Record the platform, Qt version, and outcome
separately from the offscreen evidence above.
