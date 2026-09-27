# 51515 · Balancing robot

<a name="prepare"></a>

## Prepare the model

Study how motor feedback keeps a two-wheel robot upright.

Use LEGO **51515** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=muVCJEmVa_M)
No complete building guide is supplied by this upstream project; match its model before running.

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [README.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/balancer/README.md). The Pybricks Authors. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try the program

[Open `inventor_51515_balancer.py`](program:inventor_51515_balancer.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `ColorSensor` | `sensor` |
| C | `Motor` | `left` |
| D | `Motor` | `right` |

First read the control loop without running it. Identify measured and target values. On the exact built robot, compare one small parameter change while keeping a hand ready to catch it.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted LittleTinker Rig copies; installation and terminal names may refer to Pybricks Code.

### LEGO® MINDSTORMS® Robot Inventor balancing robot

Use current Pybricks firmware on the Inventor Hub.

The upstream project does not supply a complete building guide.

Check out a video of the robot in action [here](https://www.youtube.com/watch?v=muVCJEmVa_M)

Sources: [README.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/balancer/README.md). The Pybricks Authors. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

First read the control loop without running it. Identify measured and target values. On the exact built robot, compare one small parameter change while keeping a hand ready to catch it.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [README.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/balancer/README.md). The Pybricks Authors. [MIT](LICENSE.txt).

