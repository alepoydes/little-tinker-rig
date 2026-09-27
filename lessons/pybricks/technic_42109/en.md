# 42109 · Top Gear Rally Car

<a name="prepare"></a>

## Prepare the model

Control the car from the keyboard or an Xbox controller.

Use LEGO **42109** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Building instructions](https://www.lego.com/service/buildinginstructions/42109)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [README.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42109_top_gear_rally_car/keyboard_remote/README.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try keyboard

[Open `technic_42109_keyboard.py`](program:technic_42109_keyboard.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| B | `Motor` | `steer` |
| D | `Motor` | `drive` |

Keyboard: q/a drive, o/p change steering, r or 0 centers it. Xbox: left stick steers and triggers control drive. Compare small changes to keyboard steering increments or Xbox speed scaling. Steering uses B, drive uses D.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

Open Console, focus Hub input and enable **Send keys immediately**. Keys go to the physical hub only while this field has focus. Escape leaves this input mode; Stop stops the program.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

Keyboard Remote

This program demonstrates how to use experimental 'getchar' (similar to 'input' but non-blocking).
The easiest way is running the program through the Pybricks IDE and use the I/O window, 
pressing Q/A/O/P/R keys to control the car:

Q - move forward
A - move backwards
O - turn left
P - turn right
R - reset steering (zero also works)

each time 'O' or 'P' is pressed the steering is increased a bit until the maximum is reached. 'R' or '0' resets the steering.

You can tweak these two parameters for a better driving experience:

TIME_DRIVE 

time in ms that the car moves forward or backward each time a 'Q' or 'A' is pressed
(smaller values will slow it down but it will react faster)

STEP_STEER

angle in degrees that is increased/decreased to the current steering angle each time 'O' or 'P' is pressed

Pressing 'R' or '0' resets the steering angle. Perhaps you want to pre-define some steering values and use
keys like '1' or '2' for turning the weels immediately to those values instead of increasing by steps?

For advanced users, you can replace the keyboard by an external program that connects to the hub through the Nordic UART Service
and sends the same key codes.

Sources: [README.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42109_top_gear_rally_car/keyboard_remote/README.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-2"></a>

## Try xbox

[Open `technic_42109_xbox.py`](program:technic_42109_xbox.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| B | `Motor` | `steering` |
| D | `Motor` | `drive` |

Keyboard: q/a drive, o/p change steering, r or 0 centers it. Xbox: left stick steers and triggers control drive. Compare small changes to keyboard steering increments or Xbox speed scaling. Steering uses B, drive uses D.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

Pair the controller using its pairing button after starting the program. Keep the robot supported during the initial steering calibration.

### Controller experiment

This Studio adaptation uses the MIT Audi controller example with the 42109 motor ports and steering direction. The building instructions for 42109 are in the preparation stage. Move the left stick to steer; use the right trigger to drive forward and the left trigger to reverse. Release both triggers to stop driving. Trace how `car.steer()` and `car.drive_power()` turn readings into movement.



Sources: [README.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42109_top_gear_rally_car/keyboard_remote/README.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Keyboard: q/a drive, o/p change steering, r or 0 centers it. Xbox: left stick steers and triggers control drive. Compare small changes to keyboard steering increments or Xbox speed scaling. Steering uses B, drive uses D.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [README.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42109_top_gear_rally_car/keyboard_remote/README.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). The Pybricks Team. [MIT](LICENSE.txt).

