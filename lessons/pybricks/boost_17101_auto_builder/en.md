# 17101 · Auto Builder

<a name="prepare"></a>

## Prepare the model

Build a figure by moving the conveyor and the lifting arm.

Use LEGO **17101** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=TXvCEK1MNGQ)
- [Building instructions](https://www.lego.com/cdn/product-assets/product.bi.additional.main.pdf/17101_A_AutoBuilder.pdf)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/boost/creative-toolbox/auto-builder/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try the program

[Open `boost_17101_auto_builder.py`](program:boost_17101_auto_builder.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| B | `Motor` | `belt` |
| D | `Motor` | `arm` |

Change the order of brick positions, predict the resulting figure, then compare it with the result. Adjust one conveyor position by a few degrees if alignment is poor.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted LittleTinker Rig copies; installation and terminal names may refer to Pybricks Code.

### Coding instructions

This program resets the motors to known positions, and then constructs the
LEGO figure brick-by-brick.

This works by repeatedly:
- moving the belt motor to the given brick;
- picking the brick up by moving the arm down and up;
- moving the belt back to the base position;
- putting the brick down.

The brick positions are given as the degrees the belt motor turns relative to
the base position. You can tweak these values by a few degrees if needed.


[Open `boost_17101_auto_builder.py`](program:boost_17101_auto_builder.py)


### Further exploration

The provided program is very basic, demonstrating only the core principles.
Here's a few ideas and challenges for further exploration:
- Change the order of the bricks in the `for`-loop to build something else.
- Instead of pushing the element down for two seconds, you could stop sooner.
  Try experimenting with the [run_until_stalled](https://docs.pybricks.com/en/latest/pupdevices/motor.html#pybricks.pupdevices.Motor.run_until_stalled)
  method. This can speed up the build process.
- Speaking of increasing speed, how fast can you make it? Optimize this robot
  and set a new world record!

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/boost/creative-toolbox/auto-builder/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Change the order of brick positions, predict the resulting figure, then compare it with the result. Adjust one conveyor position by a few degrees if alignment is poor.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/boost/creative-toolbox/auto-builder/index.md). The Pybricks Team. [MIT](LICENSE.txt).

