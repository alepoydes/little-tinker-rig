# 45678 · CNC drawing machine

<a name="prepare"></a>

## Prepare the model

Draw a rectangle with two motor axes.

Use LEGO **45678** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.


No complete building guide is supplied by this upstream project; match its model before running.

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [README.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/cnc_machine/README.md). The Pybricks Authors. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try the program

[Open `spike_45678_cnc.py`](program:spike_45678_cnc.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `horizontal_motor` |
| C | `Motor` | `vertical_motor` |

Change width and height separately, then draw a square. The dimensions in this program are motor degrees, not millimetres. Explain why reversing each axis returns the pen to its start.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

### Example LEGO® SPIKE™ Prime programs for CNC Machine

These programs require PyBricks v3 firmware installed on the Prime Hub.

Building instructions can be found at https://education.lego.com/en-us/product-resources/spike-prime/downloads/building-instructions.

The playing instructions for each robot variant are in the docstrings of the corresponding file.

Sources: [README.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/cnc_machine/README.md). The Pybricks Authors. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Change width and height separately, then draw a square. The dimensions in this program are motor degrees, not millimetres. Explain why reversing each axis returns the pen to its start.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [README.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/cnc_machine/README.md). The Pybricks Authors. [MIT](LICENSE.txt).

