# Lessons and student projects

Lessons are optional. **File → Lessons → First drive · SPIKE Prime 45678** starts
an independent student project. Ordinary Python editing works as before.

The **Lesson** workspace presents the goal, stages and progressive hints.
**Start this stage** opens Program, Control or Assembly. A collapsible current-task
card stays above the program. Visiting a stage does not mark it complete and never
replaces your code. **Apply starter program** asks before replacement and supports
Undo. Physical assembly and experiments are marked complete by the learner;
a connection-check stage requires live readings from the port monitor.

Each stage shows a small palette, including its permitted contextual expression
operations. Existing code still uses the full library for recognition and editing.
**Show all blocks** enables free experiments while retaining lesson progress.

## Save and resume

**Save** writes a portable `.pyblocks` archive containing ordinary Python programs,
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
under `pyblocks-studio/projects` and `pyblocks-studio/recovery`, never in the
installation or lesson directory. Recovery is debounced; it is not a replacement
for saving the portable archive. A changed archive is not silently overwritten.
The working copy is removed after a normal close; an abnormal close leaves it
available for recovery. Archive contents can also be extracted with a ZIP tool.

## Assembly

The bundled training base contains 20 parts and 11 assembly steps. Steps 1–7 build
the rolling base; 8–11 add its distance sensor. Left motor: **A**, right motor: **B**,
distance sensor: **D**. Wheel diameter: **56 mm**, axle track: **136 mm**.
Its mounting geometry is checked digitally; physical fit and calibration need
verification on a real set.

- Left drag rotates, right/middle drag pans, and the wheel zooms.
- Previous parts are muted, current parts keep their colors, future parts are
  hidden unless their outlines are enabled.
- Click a part to identify it. The step's parts list includes quantity, color
  swatches and authored lengths; tooltips retain LDraw part names and numbers.
- **Recommended view** frames the current assembly. A subassembly selector can
  isolate a group in imported models; **Whole robot** shows its destination.
- **Locate a device** highlights the device and marks its expected hub port.
  Expected wiring is instructional; the Python program remains authoritative.

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

On Linux the default cache is `~/.cache/pyblocks-studio/ldraw/`; other platforms use
their standard cache directory. Archives are stored under their SHA-256, checked
before use, and installed atomically. The viewer reads only referenced ZIP members
into memory without extracting thousands of files. No geometry is downloaded
during rendering, camera movement or step changes.

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
it initializes a new project; at stage level it is applied explicitly). Optional
`collection` names a normal block collection included in the lesson.

Stage `mode` is `program`, `control` or `assembly`; `assembly: [1, 7]` names an
inclusive range of model steps. `check` is `manual` (default) or `devices`; a stage's
`devices` can restrict the robot-device check to named instances. `operations`
optionally lists expression templates, such as `"$ + ..."` and `"$ < ..."`;
names and literals remain editable. It is empty by default in a restricted lesson.

`robot.json` uses `format: 1` and gives `model`, optional `library`, localized `description`, optional
`parts` descriptions, `steps` keyed by one-based step number, and `devices` with
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
parts. `0 !PYBLOCKS ID left-motor` immediately before a reference assigns a stable
instance ID; submodel paths compose IDs. Keep these IDs stable when annotating
wiring. Referenced geometry must belong to the model's local files or its declared
library and retain attribution. To prepare a compact resource archive for release,
run `tools/bundle_ldraw.py model.mpd --library complete.zip --output /path/outside/repo/parts.zip`.
The tool prints its checksum and refuses to write third-party resources into this
repository. Without `--output` it writes to the user's parts cache.
