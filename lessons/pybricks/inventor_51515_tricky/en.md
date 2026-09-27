# 51515 · Tricky and soccer

<a name="prepare"></a>

## Prepare the model

Compare Tricky’s basic movement and soccer programs.

Use LEGO **51515** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=5Fa4m1XzlCA)
- [Building instructions](https://www.lego.com/cdn/product-assets/product.bi.additional.main.pdf/51515_Tricky.pdf)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/tricky/index.md). The Lương-Phạm Family. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try the program

[Open `inventor_51515_tricky.py`](program:inventor_51515_tricky.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `left_motor` |
| B | `Motor` | `right_motor` |
| D | `UltrasonicSensor` | `distance_sensor` |

Find the distance-sensor condition and predict how changing its threshold changes the moment of action. Change only one threshold at a time.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted LittleTinker Rig copies; installation and terminal names may refer to Pybricks Code.

#### Programs

The playing instructions for each robot variant are in the docstrings of the corresponding file.


The code for Tricky's basic dance is in `inventor_51515_tricky.py` as follows:


[Open `inventor_51515_tricky.py`](program:inventor_51515_tricky.py)

The code for Tricky Playing Soccer is in `inventor_51515_tricky_soccer.py` as follows:


[Open `inventor_51515_tricky_soccer.py`](program:inventor_51515_tricky_soccer.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/tricky/index.md). The Lương-Phạm Family. [MIT](LICENSE.txt).

<a name="run-2"></a>

## Try soccer

[Open `inventor_51515_tricky_soccer.py`](program:inventor_51515_tricky_soccer.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `right_motor` |
| B | `Motor` | `left_motor` |
| C | `Motor` | `self.kicker_motor` |
| D | `UltrasonicSensor` | `self.distance_sensor` |
| E | `ColorSensor` | `self.color_sensor` |

Find the distance-sensor condition and predict how changing its threshold changes the moment of action. Change only one threshold at a time.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted LittleTinker Rig copies; installation and terminal names may refer to Pybricks Code.

#### Programs

The playing instructions for each robot variant are in the docstrings of the corresponding file.


The code for Tricky's basic dance is in `inventor_51515_tricky.py` as follows:


[Open `inventor_51515_tricky.py`](program:inventor_51515_tricky.py)

The code for Tricky Playing Soccer is in `inventor_51515_tricky_soccer.py` as follows:


[Open `inventor_51515_tricky_soccer.py`](program:inventor_51515_tricky_soccer.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/tricky/index.md). The Lương-Phạm Family. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Find the distance-sensor condition and predict how changing its threshold changes the moment of action. Change only one threshold at a time.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/tricky/index.md). The Lương-Phạm Family. [MIT](LICENSE.txt).

