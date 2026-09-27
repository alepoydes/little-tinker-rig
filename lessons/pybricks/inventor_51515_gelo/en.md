# 51515 · Gelo activities

<a name="prepare"></a>

## Prepare the model

Explore walking, obstacle avoidance, tricks and remote control.

Use LEGO **51515** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Building instructions](https://www.lego.com/cdn/product-assets/product.bi.additional.main.pdf/51515_Gelo.pdf)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try basic

[Open `inventor_51515_gelo_basic.py`](program:inventor_51515_gelo_basic.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `self.rear_right_leg_motor` |
| B | `Motor` | `self.rear_left_leg_motor` |
| C | `Motor` | `self.front_right_leg_motor` |
| D | `Motor` | `self.front_left_leg_motor` |
| E | `UltrasonicSensor` | `self.distance_sensor` |
| F | `ColorSensor` | `self.color_sensor` |

Use the template to combine two existing Gelo actions. Keep the shared Gelo module beside the program. Compare a short walk with a longer one before changing the gait itself.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

#### Program

The playing instructions for each robot variant are in the docstrings of the corresponding file.

The code for Gelo's basic walk is in `inventor_51515_gelo_basic.py` as follows:


[Open `inventor_51515_gelo_basic.py`](program:inventor_51515_gelo_basic.py)

Follow the main walking sequence, starting from the original standing pose. Compare the front and rear leg timing.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-2"></a>

## Try remote

[Open `inventor_51515_gelo_remote.py`](program:inventor_51515_gelo_remote.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `self.back_right` |
| B | `Motor` | `self.back_left` |
| C | `Motor` | `self.front_right` |
| D | `Motor` | `self.front_left` |
| E | `UltrasonicSensor` | `self.ultrasonic` |
| F | `ColorSensor` | `self.color` |

Use the template to combine two existing Gelo actions. Keep the shared Gelo module beside the program. Compare a short walk with a longer one before changing the gait itself.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

Shared modules are already included beside this file: [inventor_51515_gelo.py](program:inventor_51515_gelo.py).

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

#### Instructions

This program requires the LEGO Powered Up remote control. The left <kbd>+</kbd>
and <kbd>-</kbd> buttons control the speed and the right <kbd>+</kbd> and
<kbd>-</kbd> buttons control the steering. Either red button will make Gelo stop.

[image of LEGO remote](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.png)

This script makes use of the [inventor_51515_gelo.py](program:inventor_51515_gelo.py) module, so make
sure to save that program in Pybricks Code first.

Then save the script below as `inventor_51515_gelo_remote.py` and run it.

When the program starts, the light will turn yellow. This means Gelo is waiting
to connect to the remote control. Turn on the remote and it will connect
automatically and the light on Gelo will turn green. Then you can press the
buttons on the remote to control Gelo.

#### Program


[Open `inventor_51515_gelo_remote.py`](program:inventor_51515_gelo_remote.py)

Start the program, then turn on the Powered Up remote. Yellow means waiting for a remote; green means connected. Left +/− changes speed, right +/− changes steering, and either red button stops walking.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-3"></a>

## Try repl

[Open `inventor_51515_gelo_repl.py`](program:inventor_51515_gelo_repl.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `self.back_right` |
| B | `Motor` | `self.back_left` |
| C | `Motor` | `self.front_right` |
| D | `Motor` | `self.front_left` |
| E | `UltrasonicSensor` | `self.ultrasonic` |
| F | `ColorSensor` | `self.color` |

Use the template to combine two existing Gelo actions. Keep the shared Gelo module beside the program. Compare a short walk with a longer one before changing the gait itself.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

The original REPL activity requires firmware with an interactive prompt. If a `>>>` prompt appears, send commands from Console in line mode, for example `gelo.walk()`. If the firmware only stops, use the template activity; Studio does not emulate a hub REPL.

Shared modules are already included beside this file: [inventor_51515_gelo.py](program:inventor_51515_gelo.py).

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

#### Using the command prompt

Python has an interactive command prompt. This is also sometimes called the
REPL (Read Evaluate Print Loop). It can be used to run Python code as you
type it in.

Save the program below as `inventor_51515_gelo_repl.py` in Pybricks Code. And make sure you
have the [inventor_51515_gelo.py](program:inventor_51515_gelo.py) saved there too.

Then connect to Gelo and run the program. In the terminal window in Pybricks
Code, you will see a prompt like this:

```
>>>
```

Type in a command like this and press enter:

```
>>> gelo.walk()
```

##### Tips

* To save some typing, after typing `gelo.`, you can press the <kbd>tab</kbd>
  key to provide a list of available methods. Then type the first few letters
  and press <kbd>tab</kbd> again to complete the name.
* To cancel a running command, you can press <kbd>ctrl</kbd>+<kbd>c</kbd>.


#### Program


[Open `inventor_51515_gelo_repl.py`](program:inventor_51515_gelo_repl.py)



Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-4"></a>

## Try roam

[Open `inventor_51515_gelo_roam.py`](program:inventor_51515_gelo_roam.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `self.back_right` |
| B | `Motor` | `self.back_left` |
| C | `Motor` | `self.front_right` |
| D | `Motor` | `self.front_left` |
| E | `UltrasonicSensor` | `self.ultrasonic` |
| F | `ColorSensor` | `self.color` |

Use the template to combine two existing Gelo actions. Keep the shared Gelo module beside the program. Compare a short walk with a longer one before changing the gait itself.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

Shared modules are already included beside this file: [inventor_51515_gelo.py](program:inventor_51515_gelo.py).

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

#### Quick start

This script makes use of the [inventor_51515_gelo.py](program:inventor_51515_gelo.py) module, so make
sure to save that program in Pybricks Code first.

Then save the script below as `inventor_51515_gelo_roam.py` and run it.

Gelo will walk forward until it "sees" an obstacle. Then it will randomly turn
left or right then start walking again until it sees the next obstacle.

#### Program


[Open `inventor_51515_gelo_roam.py`](program:inventor_51515_gelo_roam.py)

#### Change it up

Try changing the program to attack obstacles instead avoiding them.

* Change the main loop to turn until an obstacle is detected.
* Then walk towards the obstacle until Gelo crashes into it!

Observe the distance reading: an obstacle triggers a randomly chosen turn, then walking resumes. Compare one distance threshold at low speed.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-5"></a>

## Try template

[Open `inventor_51515_gelo_template.py`](program:inventor_51515_gelo_template.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `self.back_right` |
| B | `Motor` | `self.back_left` |
| C | `Motor` | `self.front_right` |
| D | `Motor` | `self.front_left` |
| E | `UltrasonicSensor` | `self.ultrasonic` |
| F | `ColorSensor` | `self.color` |

Use the template to combine two existing Gelo actions. Keep the shared Gelo module beside the program. Compare a short walk with a longer one before changing the gait itself.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

Shared modules are already included beside this file: [inventor_51515_gelo.py](program:inventor_51515_gelo.py).

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

#### Program

Use this script as a starting point for your own Gelo program.

This script makes use of the [inventor_51515_gelo.py](program:inventor_51515_gelo.py) module, so make
sure to save that program in Pybricks Code first.

##### Tip

In Pybricks Code, type `gelo` and then `.` to see what Gelo can do and get help
on what parameters you can pass to the methods.


[Open `inventor_51515_gelo_template.py`](program:inventor_51515_gelo_template.py)

The template imports the shared Gelo class. Add calls inside its context so cleanup still stops the motors when the sequence finishes.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-6"></a>

## Try tricks

[Open `inventor_51515_gelo_tricks.py`](program:inventor_51515_gelo_tricks.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `self.back_right` |
| B | `Motor` | `self.back_left` |
| C | `Motor` | `self.front_right` |
| D | `Motor` | `self.front_left` |
| E | `UltrasonicSensor` | `self.ultrasonic` |
| F | `ColorSensor` | `self.color` |

Use the template to combine two existing Gelo actions. Keep the shared Gelo module beside the program. Compare a short walk with a longer one before changing the gait itself.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

Shared modules are already included beside this file: [inventor_51515_gelo.py](program:inventor_51515_gelo.py).

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

#### Instructions

This script makes use of the [inventor_51515_gelo.py](program:inventor_51515_gelo.py) module, so make
sure to save that program in Pybricks Code first.

Then save the script below as `inventor_51515_gelo_tricks.py` and run it.

[image of Gelo's bone](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/gelo-bone.png)


Wave one of the colors on the bone in front of the color sensor on Gelo and
watch which trick he does.

The tricks work best when Gelo is on carpet where he can get a good grip.

#### Program


[Open `inventor_51515_gelo_tricks.py`](program:inventor_51515_gelo_tricks.py)

Show the different colored bones to the color sensor and compare the tricks. Use a surface with enough grip for the feet.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Use the template to combine two existing Gelo actions. Keep the shared Gelo module beside the program. Compare a short walk with a longer one before changing the gait itself.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

