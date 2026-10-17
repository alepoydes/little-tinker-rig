# Lessons and student projects

Lessons are optional. **File → Lessons → First drive · SPIKE Prime 45678** starts
an independent student project. Ordinary Python editing works as before.

The **Lesson** workspace presents the goal, stages and progressive hints.
**Open program**, **Open controls** or **Open assembly** opens the stage's workspace.
The task and its controls stay together at the top in Program, Control, Lesson
and the lesson's Assembly. Help and Block Editor use the full height. Outside
Lesson, the card shows a compact stage title; its tooltip contains the goal.
Previous, next and complete actions use icons with tooltips.
**Mark complete** records the result without changing workspace;
completed stages get green checkmarks in the list. **← Previous stage** and
**Next stage →** open neighboring descriptions, even before completion.
**Open lesson** returns to the overview. Hide the task card with **×** and restore
it with **View → Current task**. Visiting a stage never completes it or replaces
code. **Open starter program** opens a new unsaved program tab in this lesson
project, preserving the current program. Physical assembly and experiments are
marked complete by the learner; a connection-check stage requires live readings
from the port monitor. Its status explains any missing connection or device.

Each stage shows a small palette, including its permitted contextual expression
operations. Existing code still uses the full library for recognition and editing.
**Show all blocks**, in the block library, enables free experiments while retaining
lesson progress.
Selecting or hovering over an input does not filter the library. Right-click the
input and choose **Find value blocks** to search for compatible expressions, or
**Find creation blocks** to find a declaration for a missing variable. The back
button above the catalog restores the previous view and search. Escape in the
editor returns selection to the enclosing statement.
Ordinary **File → New** creates a program outside the lesson, with the normal library.

## Pybricks projects

**File → Lessons → Pybricks · BOOST / Robot Inventor / SPIKE Prime / Technic**
offers 24 project lessons with English/Russian goals, port tables, experiments and
restricted block palettes. A lesson can contain several runnable variants and
shared modules. **Open program** and program links select the indicated student
copy; reopening it preserves edits. Stage navigation only changes the task.

Programs, dependencies, descriptions, licenses and progress are saved together.
Blast 51515, R2-D2 75253, X-treme Off-Roader 42099 and Liebherr 42100 include
community LDraw models with authored steps. Select **Open 3D building instructions**
at the top of the preparation description, or **Open assembly** in the task card.
The description link remains available when the card is hidden and opens the
lesson robot even if another model was opened separately.
Author credits, licenses and official LEGO PDF links
remain available. Steps follow the MPD rather than PDF page numbers. Other lessons
retain their building links. PDFs, photos and videos open in your browser and
require internet or a separately saved copy. For keyboard
projects, open **Console**, focus **Hub input** and enable **Send keys immediately**.
Only that field sends keys; Escape returns to line input. In line mode, Enter
sends the text and a carriage return. Input needs a physical Bluetooth/USB hub
with its port monitor stopped. It is not a terminal or REPL emulator.

Imported lesson text comes from the [MIT-licensed Projects repository](https://github.com/pybricks/pybricks-projects/blob/master/LICENSE).
The 42100 activity uses existing LittleTinker Rig MIT programs and original guidance.
The four community models have separate CC BY 2.0 attribution and licenses in
their `robot` directories; their part geometry remains in the external library.
Additional [website projects](https://pybricks.com/project/) remain links because
[the website terms](https://pybricks.com/legal/#pybricks-website-site-content)
require permission to reproduce that content. Source attribution is included in
every activity. EV3 is not included.

## Save and resume

**Save** writes a portable `.ltr` archive containing ordinary Python programs,
Scratch, a copy of the lesson materials and robot arrangement, editor view state,
hints and progress. Invalid unfinished Python can be saved too. Open this file to
continue; open the lesson again to start a separate project. Use **File → New
program in lesson project** for another program in the same archive.

Downloaded part libraries are referenced by version and checksum. **File → Export
lesson project with resources…** creates a separate offline copy containing only
the required parts, colors and attribution. It includes current unfinished code
and Scratch, and keeps the original project's save path. User-authored model files
remain in the project; they are never placed only in a disposable cache.

Working files and crash recovery live in the platform's user data directory,
under `little-tinker-rig/projects` and `little-tinker-rig/recovery`, never in the
installation or lesson directory. Recovery is debounced; it is not a replacement
for saving the portable archive. A changed archive is not silently overwritten.
The working copy is removed after a normal close; an abnormal close leaves it
available for recovery. Archive contents can also be extracted with a ZIP tool.

## Assembly

**File → Open robot instructions…** opens a `robot.json` description independently
of a lesson. Assembly remains available from the left sidebar. The model selector
appears only when both independent instructions and the lesson robot are open.
It uses the model names; a single model needs no selector.
Standalone assembly remembers its last model, step and camera in application
settings; each lesson keeps its own assembly progress inside its project.

The bundled training base contains 20 parts and 11 assembly steps. Steps 1–7 build
the rolling base; 8–11 add its distance sensor. Left motor: **A**, right motor: **B**,
distance sensor: **D**. Wheel diameter: **56 mm**, axle track: **136 mm**.
Its mounting geometry is checked digitally; physical fit and calibration need
verification on a real set.

- Left drag rotates, Shift+left drag or right/middle drag pans, and the wheel zooms.
  Zooming in holds the outer edges of the selected parts near the viewport boundary,
  gradually bringing their center into view. Without a selection it protects the
  current construction or isolated subassembly; future parts are ignored.
  Once the selection grows larger than the window its edges can extend outside.
  Zooming out preserves the resulting center, and manual panning remains unrestricted.
- Previous parts are muted, current parts keep their colors, future parts are
  hidden unless their outlines are enabled.
- Click a part to identify it. The step's parts list includes quantity, color
  swatches and authored lengths; tooltips retain LDraw part names and numbers.
  Selecting a row highlights all copies added in that step, in their actual
  positions, including through other parts. Selecting and clearing a selection
  preserve the camera. Ctrl+click a part or list row to center it without changing
  the zoom or viewing angle; rotation then uses this new center.
  Click the row again, press Escape,
  click the model background or change step to clear selection.
- **Recommended view** frames the current assembly. A subassembly selector can
  isolate an assembled group in imported models; **View: Whole robot** restores
  the full construction. Inspection never advances the assembly step.
- **Locate a device** highlights the device and marks its expected hub port.
  Only devices installed by the current step are listed. Expected wiring is
  instructional; the Python program remains authoritative.

The viewer loads local LDraw/MPD files in a worker, shares repeated part meshes,
and uses Qt OpenGL with ModernGL. No TopoVEC dependency is required. An unavailable
OpenGL context leaves the step text and parts list usable. The viewer does not
simulate physics, infer assembly order, or route flexible cables.

## External parts and offline use

Opening **Assembly** downloads the pinned official LDraw archive if it is missing
from the shared user cache. Opening a lesson or editing a program does not start
this download. Assembly shows progress and a Cancel button; after a failed or
cancelled download, retry or choose **Open parts ZIP…** with a matching local copy.
The first-drive archive is about 139 MiB. It is downloaded once for all projects.

On Linux the default cache is `~/.cache/little-tinker-rig/ldraw/`; other platforms use
their standard cache directory. Archives are stored under their SHA-256, checked
before use, and installed atomically. The viewer reads only referenced ZIP members
into memory without extracting thousands of files. No geometry is downloaded
during rendering, camera movement or step changes.

Prepared model geometry is cached in the `scenes/` subdirectory and reused after
restarting LittleTinker Rig, including across working copies of the same lesson. The first
open builds this cache; subsequent opens read it directly. Changes to the model,
referenced parts, colors or geometry converter trigger a rebuild. Camera settings
and lesson progress remain separate. The graphics card still receives the geometry
when the viewer opens.

Deleting only `scenes/` rebuilds geometry from the model and cached parts without
downloading them again. An unreadable or unwritable scene cache does not prevent
opening a valid model.

The official `complete.zip` URL changes with library releases. A checksum mismatch
never substitutes new geometry silently: use the matching local archive or an
offline export. Future pinned release archives can use the same library reference
format. Clearing the cache requires downloading the referenced version again;
an offline export is the way to keep a project independent of the download server.

## Author a lesson

A `.pylesson` is a ZIP archive with `lesson.json` at its root. A lesson directory
has the same layout and can be placed in the development `lessons/` tree.
Use stable stage and block identities:

```json
{
  "format": 1,
  "id": "my-first-drive",
  "title": {"en": "First drive", "ru": "Первая поездка"},
  "robot": "robot/robot.json",
  "stages": [{
    "id": "drive",
    "title": {"en": "Drive", "ru": "Поездка"},
    "description": {"en": "en/drive.md", "ru": "ru/drive.md"},
    "mode": "program",
    "blocks": ["pybricks/drive/create_robot", "pybricks/drive/straight"],
    "hints": [{"en": "Set distance to 200.", "ru": "Укажи расстояние 200."}]
  }]
}
```

English is the fallback. Descriptions are Markdown files; titles, goals and hints
are localized strings. Optional `starter` names a Python file (at the lesson level
it initializes a new project; at stage level it opens a new program explicitly).
Optional `collection` names a normal block collection included in the lesson.

Optional localized `group` creates a submenu in **File → Lessons**. Nested lesson
directories are discovered recursively. A description may select an ATX Markdown
section, for example `en.md#prepare`; preceding HTML anchors provide stable stage
names across translations. Subheadings and fenced code remain in that section.

For multi-file activities, `programs` maps workspace paths to lesson files and
`main` names the initial Python program, for example:

```json
{
  "programs": {"main.py": "code/main.py", "robot.py": "code/robot.py"},
  "main": "main.py"
}
```

A stage's optional `program` selects one of these Python files. Markdown links
such as `[Open robot](program:robot.py)` open its editable copy without resetting
it. Other files, such as licenses, may also be copied through `programs`.
Local documentation links stay inside the lesson; HTTP(S) links open the browser.

Bundled lessons may additionally map local paths to installed examples, e.g.
`"examples": {"code/main.py": "pybricks/boost_17101_auto_builder.py"}`.
Use `Lesson.load(directory).archive()` to produce a portable `.pylesson`: this
materializes the referenced files and removes the `examples` mapping. Creating a
student project does this automatically. The student's archive never depends on
its author's installation or a future version of the example catalog.

Stage `mode` is `program`, `control` or `assembly`; `assembly: [1, 7]` names an
inclusive range of model steps. `check` is `manual` (default) or `devices`; a stage's
`devices` can restrict the robot-device check to named instances. `operations`
optionally lists expression templates, such as `"$ + ..."` and `"$ < ..."`;
names and literals remain editable. It is empty by default in a restricted lesson.

`robot.json` uses `format: 1` and gives `model`, optional `library`, localized
`title` and `description`, optional `parts` descriptions, `steps` keyed by one-based
step number, and `devices` with
`instance`, localized `name`, `port` and `type`. `ports` maps letters to model-space
LDraw coordinates. A step can provide `text` and a recommended `camera` containing
`center`, `extent`, `yaw`, `pitch`. No 3D metadata is inserted into program source.

An external `library` is an object with `id`, `version`, an HTTPS `url` and `sha256`;
see the bundled robot description for an actual pinned archive. A string instead
names a local directory or ZIP inside the lesson, useful for original user models
and offline exports. Both standard ZIPs with an `ldraw/` root and compact archives
with `parts/`, `p/` and `LDConfig.ldr` at the root are supported. External part data
belongs in the cache or release assets, never in Git.

LDraw `0 STEP`/`0 ROTSTEP` delimit authored steps. Nested submodel steps are visited
in assembly order at their final positions; automatic ROTSTEP camera conversion
and texture maps are not implemented. Parts use triangles, quads, explicit and
conditional edges. Faces are double-sided, including mirrored and uncertified
parts. `0 !LITTLE_TINKER_RIG ID left-motor` immediately before a reference assigns a stable
instance ID; submodel paths compose IDs. Keep these IDs stable when annotating
wiring. Referenced geometry must belong to the model's local files or its declared
library and retain attribution. To prepare a compact resource archive for release,
run `tools/bundle_ldraw.py model.mpd --library complete.zip --output /path/outside/repo/parts.zip`.
The tool prints its checksum and refuses to write third-party resources into this
repository. Without `--output` it writes to the user's parts cache.
