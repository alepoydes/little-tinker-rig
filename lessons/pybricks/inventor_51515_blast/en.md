# 51515 · Blast

<a name="prepare"></a>

## Prepare the model

Follow Blast’s movement sequence and identify its sensor inputs.

Use LEGO **51515** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=5Fa4m1XzlCA)
- [Building instructions](https://www.lego.com/cdn/product-assets/product.bi.additional.main.pdf/51515_Blast.pdf)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/blast/index.md). The Lương-Phạm Family. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try the program

[Open `inventor_51515_blast.py`](program:inventor_51515_blast.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `self.right_motor` |
| B | `Motor` | `self.action_motor` |
| C | `Motor` | `self.left_motor` |
| D | `Motor` | `self.arm_movement_motor` |
| E | `ColorSensor` | `self.color_sensor` |
| F | `UltrasonicSensor` | `self.distance_sensor` |

Find the coordinated motor movements. Reduce one movement speed and compare the timing, retaining the original motor directions and initial pose.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

#### Program
The playing instructions for each robot variant are in the docstrings of the corresponding file.

The code for Blast's basic dance is in `inventor_51515_blast.py` as follows:


[Open `inventor_51515_blast.py`](program:inventor_51515_blast.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/blast/index.md). The Lương-Phạm Family. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Find the coordinated motor movements. Reduce one movement speed and compare the timing, retaining the original motor directions and initial pose.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/blast/index.md). The Lương-Phạm Family. [MIT](LICENSE.txt).

