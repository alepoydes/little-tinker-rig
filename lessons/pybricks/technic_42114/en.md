# 42114 · Volvo articulated hauler

<a name="prepare"></a>

## Prepare the model

Explore steering, dumping and automatic/manual gear changes.

Use LEGO **42114** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=j4ZxOhXygNY)
- [Building instructions](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6396116.pdf)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42114-volvo-articulated-hauler/powered-up-remote/index.md). Repkovsky. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try hauler

[Open `technic_42114_hauler.py`](program:technic_42114_hauler.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `drive` |
| B | `Motor` | `self.gearbox` |
| D | `Motor` | `steer` |

The green remote button switches automatic/manual mode. In manual mode the red buttons change gears. In automatic mode right red selects dumping and left red returns to driving. Observe the remote light and change only one gearbox threshold.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

### Manual and automatic switching mode

The program for controlling Technic Volvo Articulated Hauler with remote
control is a bit more complicated than the other remote control programs
because of the 3-gear gearbox, which works both in manual and automatic mode.

Manual gear switching requires not only detection whether the remote button is
pressed or not, but also detection of the button press (or release) moment
itself. This is realized using the ``Key`` class.

The automatic gearbox needs to detect the proper time for switching the gear
up or down. This is possible by measuring the speed of XL motor, when it is
running. If the speed is systematically very low, the gear is decreased.
If the speed is systematically close to maximum, the gear is increased.

To make speed measurement robust to random variations, values obtained from
the speed sensor are filtered using simple
[exponential smoothing](https://en.wikipedia.org/wiki/Exponential_smoothing).
Threshold values of speed, measurement time and smoothing constant are defined
by the constants `HI_SPEED, LO_SPEED`, `STABLE_SPEED_TIME` and `SMOOTHING`.
If the automatic gearbox does not change gears even if Hauler reaches full
speed, `HI_SPEED` should be decreased. Speed tracking, keeping the current
state of gearbox and handling the remote/hub LEDs was implemented in the
``Gearbox`` class.

### Driving and switching gears

By default, the left controller controls the left/right steering, and the right
controller determines the direction of driving. This can be changed easily by
setting the constant `LEFT_STEER_RIGHT_DRIVE` to False.

The gearbox can be used in two modes, as in the original LEGO smartphone app:
*automatic* and *manual*. You can switch between the modes by pushing the green
button on the remote. *Automatic* is default starting mode, but this can be
easily changed by modifying constant `INIT_GEARBOX_AUTO`.

In the *automatic* mode, gears are changed when program detects that motor's
speed is too slow or close to maximum speed. The current gear is indicated by
the color of the remote's LED:
1. Cyan
2. Blue
3. magenta
    
To enable dumper (remote LED: green), press the right red button on the remote.
To go back to driving mode, press left red button. If drive is idle for time
longer than defined in constant `GEAR_RESET_TIMEOUT`, the gear is set to 1.

In the *manual* mode, the gear is decreased by pressing left red button, and
increased with right red button. Gearbox positions are indicated by the color
of LED:

1. Yellow
2. Orange
3. Red

Sometimes gearbox tends to jam. If the target angle of gear selector is not
reached within the time defined by `GEAR_SWITCH_TIMEOUT` (1.5 sec by default),
the automatic gearbox reset is performed. The hub LED changes to red, while
the gearbox is recalibrated, which sets the gear to 1.

[Illustration](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42114-volvo-articulated-hauler/powered-up-remote/remote_description.png)

### Program


[Open `technic_42114_hauler.py`](program:technic_42114_hauler.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42114-volvo-articulated-hauler/powered-up-remote/index.md). Repkovsky. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

The green remote button switches automatic/manual mode. In manual mode the red buttons change gears. In automatic mode right red selects dumping and left red returns to driving. Observe the remote light and change only one gearbox threshold.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42114-volvo-articulated-hauler/powered-up-remote/index.md). Repkovsky. [MIT](LICENSE.txt).

