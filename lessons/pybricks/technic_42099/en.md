# 42099 · X-treme Off-Roader

<a name="prepare"></a>

## Prepare the model

Compare autonomous driving, keyboard, remote and obstacle detection.

Use LEGO **42099** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. Open Assembly to follow the included LDraw construction steps. Their numbering differs from the official PDF.

- [Building instructions](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6314518.pdf)
- [Video](https://www.youtube.com/watch?v=kN47P6mksj4)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

### 3D model and building sources

Follow the authored LDraw steps, rotate the model and select parts to inspect their placement. Step numbers differ from the LEGO PDF. Recommended view frames the current construction. Flexible components are shown as single items, including their attached cables.

Digital model and authored steps: [Philippe Hurbain (Philo)](https://forums.ldraw.org/thread-23139.html), [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/). Original robot: LEGO Group. Adapted for Studio; parts come from the external LDraw library.

- [Official LEGO instructions (PDF downloads)](https://www.lego.com/en-us/service/building-instructions/42099)

Decorative stickers are not included.

<a name="run-1"></a>

## Try off roader

[Open `technic_42099_off_roader.py`](program:technic_42099_off_roader.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| C | `Motor` | `steer` |

For the keypad program, 7/8/9 drive forward, 1/2/3 reverse, and 5 stops. For obstacle avoidance attach the exact sensor named in the program. Change one steering or distance setting and predict the result.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

### Basic driving and steering

This program centers the steering motor, and defines a function called
``drive`` which can be used to control the vehicle. Further details
are given as comments in the program.


[Open `technic_42099_off_roader.py`](program:technic_42099_off_roader.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-2"></a>

## Try keyboard

[Open `technic_42099_keyboard.py`](program:technic_42099_keyboard.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| C | `Motor` | `steer` |

For the keypad program, 7/8/9 drive forward, 1/2/3 reverse, and 5 stops. For obstacle avoidance attach the exact sensor named in the program. Change one steering or distance setting and predict the result.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

Open Console, focus Hub input and enable **Send keys immediately**. Keys go to the physical hub only while this field has focus. Escape leaves this input mode; Stop stops the program.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

### How it works

Your MicroPython programs can produce *output* using the `print` command, but
it can also read *input*. You can learn more about this
in [this tutorial](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/tutorials/wireless/hub-to-device/pc-keyboard/index.md).


### The remote control program

This program combines the keyboard example linked above with
the [basic driving program](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md). This allows you to control the
truck using the numeric keys on your keyboard. If your keyboard does not have
separate numeric keys, just adapt the program to use other keys.


[Open `technic_42099_keyboard.py`](program:technic_42099_keyboard.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-3"></a>

## Try keyboard monitor

[Open `technic_42099_keyboard_monitor.py`](program:technic_42099_keyboard_monitor.py). This is your project copy; reopening it preserves your edits.



For the keypad program, 7/8/9 drive forward, 1/2/3 reverse, and 5 stops. For obstacle avoidance attach the exact sensor named in the program. Change one steering or distance setting and predict the result.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

Open Console, focus Hub input and enable **Send keys immediately**. Keys go to the physical hub only while this field has focus. Escape leaves this input mode; Stop stops the program.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

### How it works

Your MicroPython programs can produce *output* using the `print` command, but
it can also read *input*. You can learn more about this
in [this tutorial](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/tutorials/wireless/hub-to-device/pc-keyboard/index.md).


### The remote control program

This program combines the keyboard example linked above with
the [basic driving program](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md). This allows you to control the
truck using the numeric keys on your keyboard. If your keyboard does not have
separate numeric keys, just adapt the program to use other keys.


[Open `technic_42099_keyboard.py`](program:technic_42099_keyboard.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-4"></a>

## Try obstacle avoidance

[Open `technic_42099_obstacle_avoidance.py`](program:technic_42099_obstacle_avoidance.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| C | `Motor` | `steer` |
| D | `ColorDistanceSensor` | `sensor` |

For the keypad program, 7/8/9 drive forward, 1/2/3 reverse, and 5 stops. For obstacle avoidance attach the exact sensor named in the program. Change one steering or distance setting and predict the result.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

### Selecting a sensor
This project will work with any sensor that can measure distance.

You can use
the [Color and Distance sensor](https://docs.pybricks.com/en/latest/pupdevices/colordistancesensor.html)
as in this example, but you can also use the
[Ultrasonic Sensor](https://docs.pybricks.com/en/latest/pupdevices/ultrasonicsensor.html)
or the
[Infrared Sensor](https://docs.pybricks.com/en/latest/pupdevices/infraredsensor.html).
Mount the sensor somewhere on the front of your truck.

### Main program

This program builds on the basic [driving example](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md). It makes the
truck back up and turn when it detects an obstacle.


[Open `technic_42099_obstacle_avoidance.py`](program:technic_42099_obstacle_avoidance.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-5"></a>

## Try off roader remote

[Open `technic_42099_off_roader_remote.py`](program:technic_42099_off_roader_remote.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| C | `Motor` | `steer` |

For the keypad program, 7/8/9 drive forward, 1/2/3 reverse, and 5 stops. For obstacle avoidance attach the exact sensor named in the program. Change one steering or distance setting and predict the result.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

### Block Program

You can easily code this with the new block coding feature. Just drag and drop
the blocks as shown below.

[Powered Up Remote Control](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/off-roader-blocks-screenshot.png)

### Python program

This program expands the [basic driving program](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md) with the Powered
Up Remote.


[Open `technic_42099_off_roader_remote.py`](program:technic_42099_off_roader_remote.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

For the keypad program, 7/8/9 drive forward, 1/2/3 reverse, and 5 stops. For obstacle avoidance attach the exact sensor named in the program. Change one steering or distance setting and predict the result.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

