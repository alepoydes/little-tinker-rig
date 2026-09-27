# Pybricks project lessons

Open **File → Lessons → Pybricks · …** to start a separate student project.
These 24 activities cover BOOST, Robot Inventor, SPIKE Prime and Technic, with
40 Python programs and 87 stages. EV3 projects are outside this catalog.
Each lesson provides preparation, program variants, a focused experiment, port
tables, a restricted block palette, and English/Russian guidance. The original
MIT explanations are also available offline in English.

| Lesson | Python files | Stages |
|---|---:|---:|
| [17101 · Auto Builder](boost_17101_auto_builder/en.md) | 1 | 3 |
| [75253 · R2-D2](boost_75253_r2_d2/en.md) | 1 | 3 |
| [51515 · Balancing robot](inventor_51515_balancer/en.md) | 1 | 3 |
| [51515 · Blast](inventor_51515_blast/en.md) | 1 | 3 |
| [51515 · Block Flipper](inventor_51515_block_flipper/en.md) | 1 | 3 |
| [51515 · Exploration Rover](inventor_51515_exploration_rover/en.md) | 1 | 3 |
| [51515 · Gelo activities](inventor_51515_gelo/en.md) | 7 | 8 |
| [51515 · Mini Loader](inventor_51515_mini_loader/en.md) | 1 | 3 |
| [51515 · M.V.P.](inventor_51515_mvp/en.md) | 1 | 3 |
| [51515 · API exploration](inventor_51515_quick_reference/en.md) | 1 | 3 |
| [51515 · Steer Bot](inventor_51515_steerbot/en.md) | 1 | 3 |
| [51515 · Tricky and soccer](inventor_51515_tricky/en.md) | 2 | 4 |
| [45678 · CNC drawing machine](spike_45678_cnc/en.md) | 1 | 3 |
| [45678 · Hand-controlled grabber](spike_45678_grabber/en.md) | 1 | 3 |
| [45678 · Kiki sees colors](spike_45678_kiki/en.md) | 1 | 3 |
| [42099 · X-treme Off-Roader](technic_42099/en.md) | 5 | 7 |
| [42100 · Liebherr R 9800](technic_42100/en.md) | 2 | 4 |
| [42109 · Top Gear Rally Car](technic_42109/en.md) | 2 | 4 |
| [42114 · Volvo articulated hauler](technic_42114/en.md) | 1 | 3 |
| [42124 · Off-Road Buggy](technic_42124/en.md) | 1 | 3 |
| [42129 · Zetros trial truck](technic_42129/en.md) | 1 | 3 |
| [42131 · CAT D11 bulldozer](technic_42131/en.md) | 1 | 3 |
| [42140 · Transformation vehicle](technic_42140/en.md) | 2 | 4 |
| [42160 · Audi RS Q e-tron](technic_42160/en.md) | 3 | 5 |

## Sources and licensing

Most software and documentation adapted here come from the
[Pybricks Projects repository](https://github.com/pybricks/pybricks-projects)
at revision `faaacce09ffe1d865fd1db241bcacb056234d597`, under its
[MIT license](../../examples/pybricks/LICENSE.txt).
Each `sources.json` records the source documents, hashes, revision, authors and
program adaptations. A license copy accompanies both the lesson materials and
student programs. The 42109 Xbox activity uses the catalog's MIT Audi adaptation
with the 42109 configuration; it is not a copy of the website's downloadable code.
The 42100 lesson reuses the existing PyBlocks MIT implementations of the community
Xbox control scheme; its source record distinguishes those programs from the
upstream references.

## LDraw assembly instructions

Four lessons include digital models and authored LDraw steps by **Philippe Hurbain
(Philo)**, under **CC BY 2.0**. Original robot designs are by LEGO Group. These are
independent community reconstructions, not official LEGO instructions. Each model
keeps its author/license headers; `robot/CAreadme.txt` contains attribution,
adaptation details and the full license. `sources.json` records original and
adapted hashes, publications, downloads and official LEGO instruction links.

| Model | Studio steps | MPD size |
|---|---:|---:|
| 51515 · Blast | 91 | 719 KiB |
| 75253 · R2-D2 | 104 | 77 KiB |
| 42099 · X-treme Off-Roader | 173 | 166 KiB |
| 42100 · Liebherr R 9800 | 530 | 571 KiB |

Open **Assembly** from the preparation stage. The step numbers follow the MPD,
including nested subassemblies, and differ from LEGO PDF pages. Existing authored
steps are displayed at their final positions; camera rotations, connection arrows
and mechanical assembly validation are not inferred. Use **Recommended view** to
frame the current construction. Technic models omit decorative stickers.
Official LEGO PDFs and source publications remain available beside the 3D view.

`tools/prepare_ldraw_model.py` reproduces the model preparation from the original
MPD and the pinned external library. It retains CC BY 2.0 assembly sections,
transforms, colors and flexible geometry, removes embedded part definitions and
their separate editor metadata, and checks transitive dependencies before writing.
Part geometry is read from the shared LDraw library; it is not copied into Git.
The other lessons retain their available instruction links; an unverified or
unlicensed 3D reconstruction is not substituted for a missing model.

The [current website project catalog](https://pybricks.com/project/) contains
additional projects. Its [content terms](https://pybricks.com/legal/#pybricks-website-site-content)
require written permission for reproduction. Website-only downloads and text are
not included in these lesson packages. A link to a page does not grant permission
to redistribute its contents. The [website example inventory](../../examples/pybricks/website/README.md)
likewise provides external links without bundling those programs.

## Storage and offline use

Each source directory contains a manifest, two Markdown documents and provenance;
lessons with a digital model also contain a small `robot` directory.
The `examples` manifest mapping reuses the installed example catalog. Creating or
exporting a lesson with `Lesson.archive()` resolves these references into ordinary
files, retaining a fixed copy even if Studio or the catalog is updated. Student
programs keep their module filenames; multi-file activities such as Gelo therefore
work without a separate import or download step.

Saved projects include descriptions, programs, supporting modules, progress and
licenses. Videos, photographs and building PDFs remain external links opened in
the system browser. They require internet or a separately saved copy. No video
player dependency or fabricated 3D assembly sequence is included. Included LDraw
models work offline once their parts library is cached; **Export lesson project
with resources…** includes the required parts and their licenses for another
computer. Ordinary saves retain the library reference.
The model and its wiring must match the selected program. A virtual hub does not
simulate these robots' mechanics or their remote controllers.
