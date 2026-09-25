# LEGO set examples from Pybricks

Open any program below in PyBlocks Studio. All device operations are represented
by bundled templates; conditions, loops, assignments and functions use the standard
Python blocks. Existing programs remain fully visible at any library level.
Select **All** to rebuild a complete program, or **Beginner** to use its prepared
activities. There are no project-specific libraries or hidden helper modules.

These examples are adapted from
[Pybricks Projects](https://github.com/pybricks/pybricks-projects) at revision
`faaacce09ffe1d865fd1db241bcacb056234d597`, retrieved 2026-09-25.
Copyright (c) 2018-2023 The Pybricks Authors. Distributed under the
[upstream MIT license](LICENSE.txt), including the activity templates derived from
these examples. Original comments and individual author credits are retained.

| Program | Set and behavior | Original source at the pinned revision |
|---|---|---|
| [boost_auto_builder.py](boost_auto_builder.py) | BOOST 17101: home the arm/conveyor and assemble five parts | [Auto Builder](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/boost/creative-toolbox/auto-builder/main.py) |
| [inventor_tricky.py](inventor_tricky.py) | Robot Inventor 51515: dance when an object comes near | [Tricky intro](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/tricky/tricky-basic.py) |
| [spike_cnc.py](spike_cnc.py) | SPIKE Prime 45678: draw a rectangle | [CNC machine](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/cnc_machine/basic_cnc_machine.py) |
| [spike_grabber.py](spike_grabber.py) | SPIKE Prime 45678: operate a force-controlled gripper | [Hand-controlled grabber](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/hand-controlled-grabber/main.py) |
| [spike_kiki.py](spike_kiki.py) | SPIKE Prime 45678: display sky, house or grass for different colors | [Kiki](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/kiki_dog/kiki_seeing_colors.py) |
| [technic_buggy.py](technic_buggy.py) | Technic 42124: calibrate steering and drive with a LEGO remote | [Off-Road Buggy](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42124-off-road-buggy/powered-up-remote/main.py) |
| [technic_off_roader.py](technic_off_roader.py) | Technic 42099: calibrated steering and a timed route | [X-treme Off-Roader driving](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/main.py) |
| [technic_off_roader_remote.py](technic_off_roader_remote.py) | Technic 42099: steer and drive both axles with a remote | [X-treme Off-Roader remote](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/main.py) |

## Adaptation rules

Ports, dimensions, motor directions, speeds, timing, sensor thresholds, braking
modes, input sampling and loop termination are preserved. Leading keyword
arguments are written positionally in the same evaluation order to match the
existing templates. Tricky's nested motor constructors are named immediately
before its DriveBase constructor, in their original evaluation order. Unused
imports are removed; active dependencies remain explicit.

Kiki's obsolete `display.image()` is written as the current
[`display.icon()` API](https://docs.pybricks.com/en/stable/hubs/primehub.html), with
identical brightness matrices. No algorithm is replaced with a superficially
similar new recipe. In particular, the remote examples retain `run(0)` on release,
their original button mappings and indefinite loops; they do not use the different
beginner remote activity with center-button exit.

The import was checked against the pinned original programs by comparing ordered
device commands and final virtual state with the same scripted inputs. Regression
tests rebuild recognized fragments from library templates and repeat the comparison.
Mechanical stops, color sequences and Bluetooth button input are scripted test
boundaries; this does not validate real gearing, controller profiles or pairing.

Hardware, levels and virtual-hub limits: [English guide](../../doc/en/examples.md)
· [Русское руководство](../../doc/ru/examples.md).
