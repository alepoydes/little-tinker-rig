# 45678 · Hand-controlled grabber

<a name="prepare"></a>

## Prepare the model

Use the force sensor to control a grabber.

Use LEGO **45678** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=8uyx5npo4LA)
- [Building instructions](https://education.lego.com/v3/assets/blt293eea581807678a/blt56a81c75560c9a81/5f8802cbf71916144453a493/supercleaup-bi-pdf-book1of3.pdf)
- [Building instructions](https://education.lego.com/v3/assets/blt293eea581807678a/bltb5e585f94cb4e72b/5f8802e5a302dc0d859a734d/supercleaup-bi-pdf-book2of3.pdf)
- [Building instructions](https://education.lego.com/v3/assets/blt293eea581807678a/bltb8840f08a6d0362b/5f8802dc2792080f7721405c/supercleaup-bi-pdf-book3of3.pdf)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/hand-controlled-grabber/index.md). The Lương-Phạm Family. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try the program

[Open `spike_45678_grabber.py`](program:spike_45678_grabber.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `motor` |
| E | `ForceSensor` | `force_sensor` |

Press the force sensor to close the gripper; release it to open against its mechanical stop. This program uses pressed/released, not proportional force. Lower the speed argument of force_gripper and compare closing and opening times.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

This program is for the Hand-Controlled Grabber in the [Invention Squad: Super Clean-Up](https://education.lego.com/en-us/lessons/prime-invention-squad/super-cleanup) lesson unit.

#### Program


[Open `spike_45678_grabber.py`](program:spike_45678_grabber.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/hand-controlled-grabber/index.md). The Lương-Phạm Family. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Press the force sensor to close the gripper; release it to open against its mechanical stop. This program uses pressed/released, not proportional force. Lower the speed argument of force_gripper and compare closing and opening times.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/spike-prime/core-set/hand-controlled-grabber/index.md). The Lương-Phạm Family. [MIT](LICENSE.txt).

