# 51515 · Exploration Rover

<a name="prepare"></a>

## Prepare the model

Identify the rover motors and try one movement sequence.

Use LEGO **51515** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=3gbAc6iKAJg)
- [Building instructions](https://raw.githubusercontent.com/pybricks/pybricks-projects/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/fan-inventions/exploration-rover/exploration-rover.pdf)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/fan-inventions/exploration-rover/index.md). Laurens Valk. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try the program

[Open `inventor_51515_exploration_rover.py`](program:inventor_51515_exploration_rover.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `ColorSensor` | `self.sherloc` |
| B | `UltrasonicSensor` | `self.mast_cam` |
| C | `Motor` | `self.left_front_wheel` |
| D | `Motor` | `self.right_front_wheel` |
| E | `Motor` | `self.left_rear_wheels` |
| F | `Motor` | `self.right_rear_wheels` |

Name the mechanism driven by each port. During calibration point the color sensor at the floor. Compare a red or cyan rock with an obstacle, then shorten one reversing duration and predict the stopping position.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

#### Description

The upstream project does not supply a complete building guide.

#### Program



[Open `inventor_51515_exploration_rover.py`](program:inventor_51515_exploration_rover.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/fan-inventions/exploration-rover/index.md). Laurens Valk. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Name the mechanism driven by each port. During calibration point the color sensor at the floor. Compare a red or cyan rock with an obstacle, then shorten one reversing duration and predict the stopping position.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/fan-inventions/exploration-rover/index.md). Laurens Valk. [MIT](LICENSE.txt).

