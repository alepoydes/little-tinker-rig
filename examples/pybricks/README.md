# LEGO set examples from Pybricks

The catalog contains **69 Python files**: all 37 files in the BOOST, Robot Inventor,
SPIKE Prime and Technic families of the pinned Pybricks Projects revision, plus
a 42109 Xbox adaptation and 31 [website programs](website/README.md).
The Projects repository does not include every example
published on the Pybricks website. EV3 and City hubs are outside this import.
Filenames include the LEGO set number, not just
the hub family. A matching hub alone does not imply a matching mechanism.

Open a program in PyBlocks Studio and select **All** to see its complete palette.
Device operations use bundled templates; classes, functions, loops and expressions
use the standard Python structures. Custom robot methods use the ordinary function
call controls. No complete walker or balancer is hidden inside an opaque block.
The Beginner palette remains twenty blocks.

Sources: [Pybricks Projects](https://github.com/pybricks/pybricks-projects), revision
`faaacce09ffe1d865fd1db241bcacb056234d597`, retrieved 2026-09-25.
Copyright (c) 2018-2023 The Pybricks Authors. Original comments and author credits
are retained under the [upstream MIT license](LICENSE.txt) for repository imports.
Website downloads have their own [source notice](website/NOTICE.md).
[The machine-readable catalog](catalog.json) records original paths and SHA-256
hashes, set numbers, dependencies, roles and validation for every file.
The 42109 Xbox variant reuses the MIT Audi Xbox example with the motor configuration
and loop timing from the [official 42109 guide](https://pybricks.com/project/technic-42109-xbox/).
Its catalog entry distinguishes that guide from the code's upstream source.

## Repository inventory

The website additions and their equipment are listed in the [website inventory](website/README.md).
The rows below cover the pinned repository and the earlier 42109 adaptation.
Every program rebuilds recognized blocks without
changing executable AST structure, and compiles for MPY ABI 5 and 6. These checks
include the local Gelo dependency. Compilation does not establish firmware API
availability, available hub memory, or physical behavior.

| File | Set | Role / study level | Dependencies and extra equipment | Scripted runtime check |
|---|---|---|---|---|
| [boost_17101_auto_builder.py](boost_17101_auto_builder.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/boost/creative-toolbox/auto-builder/main.py) | 17101 | program / beginner activity / advanced details | Model motors/sensors | motor commands and state |
| [boost_75253_r2_d2.py](boost_75253_r2_d2.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/boost/droid-commander/r2-d2/main.py) | 75253 | program / advanced | Model motors/sensors | structural/compiler checks only |
| [inventor_51515_exploration_rover.py](inventor_51515_exploration_rover.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/fan-inventions/exploration-rover/main.py) | 51515 | program / expert | Model motors/sensors | structural/compiler checks only |
| [inventor_51515_blast.py](inventor_51515_blast.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/blast/blast-basic.py) | 51515 | program / expert | Model motors/sensors | motor commands and state |
| [inventor_51515_gelo.py](inventor_51515_gelo.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/gelo.py) | 51515 | library / expert | Model motors/sensors | structural/compiler checks only |
| [inventor_51515_gelo_basic.py](inventor_51515_gelo_basic.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/gelo_basic.py) | 51515 | program / expert | Model motors/sensors | structural/compiler checks only |
| [inventor_51515_gelo_remote.py](inventor_51515_gelo_remote.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/gelo_remote.py) | 51515 | program / expert | [inventor_51515_gelo.py](inventor_51515_gelo.py), LEGO Powered Up remote 88010 | structural/compiler checks only |
| [inventor_51515_gelo_repl.py](inventor_51515_gelo_repl.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/gelo_repl.py) | 51515 | interactive / expert | [inventor_51515_gelo.py](inventor_51515_gelo.py) | structural/compiler checks only |
| [inventor_51515_gelo_roam.py](inventor_51515_gelo_roam.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/gelo_roam.py) | 51515 | program / expert | [inventor_51515_gelo.py](inventor_51515_gelo.py) | structural/compiler checks only |
| [inventor_51515_gelo_template.py](inventor_51515_gelo_template.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/gelo_template.py) | 51515 | program / expert | [inventor_51515_gelo.py](inventor_51515_gelo.py) | structural/compiler checks only |
| [inventor_51515_gelo_tricks.py](inventor_51515_gelo_tricks.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/gelo_tricks.py) | 51515 | program / expert | [inventor_51515_gelo.py](inventor_51515_gelo.py) | structural/compiler checks only |
| [inventor_51515_mvp.py](inventor_51515_mvp.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/mvp/mvp-basic.py) | 51515 | program / expert | Model motors/sensors | motor commands and state |
| [inventor_51515_tricky.py](inventor_51515_tricky.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/tricky/tricky-basic.py) | 51515 | program / beginner activity / advanced details | Model motors/sensors | motor commands and state |
| [inventor_51515_tricky_soccer.py](inventor_51515_tricky_soccer.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/tricky/tricky-playing-soccer.py) | 51515 | program / expert | Model motors/sensors | structural/compiler checks only |
| [inventor_51515_balancer.py](inventor_51515_balancer.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/balancer/main.py) | 51515 | program / expert | upright robot; physical balance calibration | structural/compiler checks only |
| [inventor_51515_block_flipper.py](inventor_51515_block_flipper.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/block-flipper/block-flipper.py) | 51515 | program / expert | Model motors/sensors | structural/compiler checks only |
| [inventor_51515_mini_loader.py](inventor_51515_mini_loader.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/mini-loader/miniLoader_RC.py) | 51515 | program / expert | LEGO Powered Up remote 88010 | structural/compiler checks only |
| [inventor_51515_quick_reference.py](inventor_51515_quick_reference.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/quick-reference/Quick_Ref.py) | 51515 | reference / expert | Model motors/sensors | structural/compiler checks only |
| [inventor_51515_steerbot.py](inventor_51515_steerbot.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/steerbot/main.py) | 51515 | program / expert | Model motors/sensors | structural/compiler checks only |
| [spike_45678_cnc.py](spike_45678_cnc.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/cnc_machine/basic_cnc_machine.py) | 45678 | program / beginner activity / advanced details | Model motors/sensors | motor commands and state |
| [spike_45678_grabber.py](spike_45678_grabber.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/hand-controlled-grabber/main.py) | 45678 | program / beginner activity / advanced details | Model motors/sensors | motor commands and state |
| [spike_45678_kiki.py](spike_45678_kiki.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/kiki_dog/kiki_seeing_colors.py) | 45678 | program / beginner activity / advanced details | Model motors/sensors | motor commands and state |
| [technic_42099_off_roader.py](technic_42099_off_roader.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/main.py) | 42099 | program / beginner activity / advanced details | Model motors/sensors | motor commands and state |
| [technic_42099_keyboard.py](technic_42099_keyboard.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/main.py) | 42099 | program / advanced | connected computer keyboard | structural/compiler checks only |
| [technic_42099_keyboard_monitor.py](technic_42099_keyboard_monitor.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/remote.py) | 42099 | program / advanced | connected computer keyboard | structural/compiler checks only |
| [technic_42099_obstacle_avoidance.py](technic_42099_obstacle_avoidance.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/main.py) | 42099 | program / advanced | Model motors/sensors | structural/compiler checks only |
| [technic_42099_off_roader_remote.py](technic_42099_off_roader_remote.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/main.py) | 42099 | program / beginner activity / advanced details | LEGO Powered Up remote 88010 | motor commands and state |
| [technic_42109_keyboard.py](technic_42109_keyboard.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42109_top_gear_rally_car/keyboard_remote/main.py) | 42109 | program / advanced | connected computer keyboard | structural/compiler checks only |
| [technic_42109_xbox.py](technic_42109_xbox.py) · [guide](https://pybricks.com/project/technic-42109-xbox/) | 42109 | program / advanced | Bluetooth Xbox controller; Pybricks 3.5+; steering B, drive D | Xbox sampling, motor ports and loop timing |
| [technic_42114_hauler.py](technic_42114_hauler.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42114-volvo-articulated-hauler/powered-up-remote/main.py) | 42114 | program / advanced | LEGO Powered Up remote 88010 | structural/compiler checks only |
| [technic_42124_buggy.py](technic_42124_buggy.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42124-off-road-buggy/powered-up-remote/main.py) | 42124 | program / beginner activity / advanced details | LEGO Powered Up remote 88010 | motor commands and state |
| [technic_42129_zetros.py](technic_42129_zetros.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42129-mercedes-benz-zetros/powered-up-remote/main.py) | 42129 | program / advanced | LEGO Powered Up remote 88010 | structural/compiler checks only |
| [technic_42131_bulldozer.py](technic_42131_bulldozer.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42131-cat-bulldozer/powered-up-remote/main.py) | 42131 | program / advanced | LEGO Powered Up remote 88010 | structural/compiler checks only |
| [technic_42140_transformation.py](technic_42140_transformation.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42140-app-controlled-transformation-vehicle/powered-up-remote/main.py) | 42140 | program / advanced | LEGO Powered Up remote 88010 | structural/compiler checks only |
| [technic_42140_transformation_flipped.py](technic_42140_transformation_flipped.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42140-app-controlled-transformation-vehicle/powered-up-remote/main2.py) | 42140 | program / advanced | LEGO Powered Up remote 88010 | structural/compiler checks only |
| [technic_42160_audi_remote.py](technic_42160_audi_remote.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/powered-up-remote/main.py) | 42160 | program / advanced | LEGO Powered Up remote 88010 | structural/compiler checks only |
| [technic_42160_audi_xbox_blocks.py](technic_42160_audi_xbox_blocks.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/audi_blocks.py) | 42160 | program / advanced | Bluetooth Xbox controller; Pybricks 3.5+ | Xbox sampling and commands |
| [technic_42160_audi_xbox_python.py](technic_42160_audi_xbox_python.py) · [source](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/audi_python.py) | 42160 | program / advanced | Bluetooth Xbox controller; Pybricks 3.5+ | Xbox sampling and commands |

## Dependencies and adaptation

Keep the Gelo files together: their imports refer to `inventor_51515_gelo.py`.
Upload/run compiles local dependencies through pybricksdev. The REPL example is
an interactive session; Quick Reference is an API tour to study by section.
Their roles are explicit in the catalog.

For direct imports, ports, gearing, motor directions, dimensions, speeds, waits, input sampling,
stop modes and algorithm structure are preserved. Leading keyword arguments
become positional only in the same evaluation order. The original eight examples
also name Tricky's nested motor constructors in their original order.

API migrations use `PrimeHub` (the `InventorHub` alias), `parameters.Axis`,
`display.icon()` and `motor.done()`. `curve()` has different sign semantics from
modern `arc()`: an ordinary managed helper preserves both travel direction and
turn direction. The keyboard helper replaces obsolete `experimental.getchar`
with nonblocking `poll` and one-character input. Helpers are visible Python,
shared and removed automatically when unused. The Xbox blocks-file editor header
is discarded; its executable code still reads triggers twice per iteration, while
the Python variant reads them once. These are deliberately separate examples.

Two upstream omissions are repaired: Gelo imports `micropython.const`; the Audi
remote program constructs its `TechnicHub` before inactivity shutdown uses it.
No source archive or extra runtime framework is sent to the hub.

## Validation and limitations

`tests/test_pybricks_examples.py` checks the complete inventory, source rebuilding,
specific device-block coverage, editor opening, both compiler ABIs, ten virtual motor scenarios (including Blast and MVP), Xbox sampling, keyboard readiness and curve signs.
The ten motor scenarios also agree with ordered commands and final virtual state
from the pinned original sources. The importer audits all upstream hashes and
compares the other 29 adaptations structurally:

```bash
uv run python tools/adapt_pybricks_examples.py /path/to/pybricks-projects
```

The additional 42109 adaptation shares the Audi source hash. Its scripted check
verifies steering B, drive D, trigger sampling and the 50 ms loop delay. Pairing
and stopping instructions: [English](../../doc/en/examples.md#technic-42109-with-xbox) ·
[Русский](../../doc/ru/examples.md#technic-42109-с-xbox).

The interactive virtual hub models a limited device subset. Mechanical stops,
remote/Xbox input and keyboard readiness in tests are explicit scripted boundaries.
Gearing, PID control, R2-D2's tipping, Gelo's gait and physical balancing are not
validated by compilation or these tests. Connect the required hardware and check
firmware capabilities before running these advanced models. Xbox needs a compatible
Bluetooth controller and Pybricks 3.5 or later; the migrated arc helper needs a
firmware with `DriveBase.arc`.

Hardware and learning guides: [English](../../doc/en/examples.md) ·
[Русский](../../doc/ru/examples.md).
