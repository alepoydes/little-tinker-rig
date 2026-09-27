# 51515 · Block Flipper

<a name="prepare"></a>

## Prepare the model

Move two blocks between platforms with the four-motor arm.

Use LEGO **51515** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=IBtZhiKN9qI)
- [Building instructions](https://www.onekitprojects.com/51515/4-motor-arm)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/block-flipper/index.md). Dave Parker. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try the program

[Open `inventor_51515_block_flipper.py`](program:inventor_51515_block_flipper.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `lift` |
| B | `Motor` | `turntable` |
| D | `Motor` | `wrist` |
| F | `Motor` | `claw` |

Start with blocks on the two outside platforms and the arm near the middle. Identify which operations wait and which overlap. Reduce one speed before changing destinations.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted LittleTinker Rig copies; installation and terminal names may refer to Pybricks Code.

#### Description

This robot arm has four motors to allow it to grab, lift, flip, and move blocks
between the three small raised platforms. The program uses some of the advanced
motor control APIs to control all four motors at the same time and get fast
and accurate motion. 

#### Instructions

This program controls the 4-Motor Arm autonomously, so you don't have to build
the hand controller. You can just attach the hub to the base as shown.

Start with the two blocks on the outside (left and right) platforms, and the arm
near the middle between them. 

#### Program


[Open `inventor_51515_block_flipper.py`](program:inventor_51515_block_flipper.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/block-flipper/index.md). Dave Parker. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Start with blocks on the two outside platforms and the arm near the middle. Identify which operations wait and which overlap. Reduce one speed before changing destinations.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/block-flipper/index.md). Dave Parker. [MIT](LICENSE.txt).

