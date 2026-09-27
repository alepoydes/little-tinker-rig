# 51515 · Mini Loader

<a name="prepare"></a>

## Prepare the model

Drive the loader and operate its lifting mechanism with the remote.

Use LEGO **51515** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=L0gnDPXkx4U)
- [Building instructions](https://www.onekitprojects.com/51515/mini-loader)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/mini-loader/index.md). Dave Parker. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try the program

[Open `inventor_51515_mini_loader.py`](program:inventor_51515_mini_loader.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `UltrasonicSensor` | `eyes` |
| C | `Motor` | `scoop_motor` |
| D | `Motor` | `lift_motor` |
| E | `Motor` | `right_motor` |
| F | `Motor` | `left_motor` |

Trace each remote button to its motor action. Change one speed, leaving the stop behavior intact, and compare driving and lifting.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

#### Description

This Mini Loader has four motors to allow it to drive, steer, lift, and dump.
The program connects to the LEGO Bluetooth Remote and uses the remote's buttons 
in several ways to implement a variety of control features. 

#### Instructions

Twist the controls on the remote to make the left side vertical with + on top,
and the right side horizontal with + on the right.

Establish the connection between the hub and remote using these steps:
1. Download the Pybricks program to the hub.
2. If the program is running (display animating), press the hub button to stop it. 
3. Press the green center button on the Remote (light flashes white).
4. Immediately press the Inventor hub button to run the program.
5. If the connection is successful, both the remote and hub lights turn green. 

The remote has two modes, which you toggle between using the green center button 
on the remote. The modes are indicated by both the remote and hub lights. 
Use Drive mode (green) to drive and steer, and Lift mode (Orange) to control the lift. 

##### Drive Mode (Green light)

Use the left side buttons to control the drive direction and the right side buttons 
to steer. You can drive and steer at the same time, or just steer to pivot in place.

By holding down either of the two red buttons, you can reduce both the driving and steering
speed for more precise positioning. You can do this either by holding a red button 
with one thumb (like a shift key) while using +/- controls with your other thumb,
or with a single thumb, you can roll between pressing both Center and +/- at the same time
(slow) or just +/- (fast). 

##### Lift Mode (Orange Light)

Tap the three left side buttons to make the lift and scoop move together to three 
preset positions: Carrying High, Carrying Middle, or Ready Low.

Tap -/+ on the right side to dump/undump the scoop without moving the lift. 

The red right center button runs a special feature to help position
the mini loader to prepare to dump. Pressing and holding this button will make
the robot drive straight forward until the distance sensor measures 5 cm
(or until you release the button to cancel). The lights on the ultrasonic sensor
are turned on when the robot is using them, so a fun side effect is that quickly
tapping the right center button just flashes the sensor lights.

#### Program


[Open `inventor_51515_mini_loader.py`](program:inventor_51515_mini_loader.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/mini-loader/index.md). Dave Parker. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Trace each remote button to its motor action. Change one speed, leaving the stop behavior intact, and compare driving and lifting.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/mini-loader/index.md). Dave Parker. [MIT](LICENSE.txt).

