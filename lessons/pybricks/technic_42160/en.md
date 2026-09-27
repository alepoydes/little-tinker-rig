# 42160 · Audi RS Q e-tron

<a name="prepare"></a>

## Prepare the model

Compare Powered Up remote and analog Xbox control.

Use LEGO **42160** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=c0KVNdJlAkc)
- [Building instructions](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6508358.pdf)
- [Video](https://www.youtube.com/watch?v=fxInp9cutNg)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/powered-up-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). Geoff Stearns, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try audi remote

[Open `technic_42160_audi_remote.py`](program:technic_42160_audi_remote.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `rear` |
| B | `Motor` | `front` |
| D | `Motor` | `steer` |

With Xbox, compare small and large stick/trigger movements. Read the two Xbox variants and notice when input is sampled. Change one drive scale factor while preserving steering calibration.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

In this project we'll show you how to control the Audi RS Q e-tron with the Powered Up remote.

### Program

This program enables control of the vehicle with the Powered
Up Remote. Check out the video above for an additional program, and more coding
ideas.


[Open `technic_42160_audi_remote.py`](program:technic_42160_audi_remote.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/powered-up-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). Geoff Stearns, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-2"></a>

## Try audi xbox blocks

[Open `technic_42160_audi_xbox_blocks.py`](program:technic_42160_audi_xbox_blocks.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| D | `Motor` | `steer` |

With Xbox, compare small and large stick/trigger movements. Read the two Xbox variants and notice when input is sampled. Change one drive scale factor while preserving steering calibration.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

Pair the controller using its pairing button after starting the program. Keep the robot supported during the initial steering calibration.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

In this project we'll show you how to control the Audi RS Q e-tron with the
Xbox Controller, using either block programming or Python.

Be sure to check out the documentation in the Pybricks app for instructions
to pair the controller with the hub.

Note: This is brand a new feature. Try it with [Pybricks beta](https://beta.pybricks.com/)!

### Block Program

You can easily code this with the new block coding feature. Just drag and drop
the blocks as shown below, or download the ready-made project here. In
Pybricks, just go to the file menu and click the "Import a file" icon to open
it.

<a href="./audi_blocks.py" target="_blank" class="btn btn--primary"><i class="fas fa-puzzle-piece"></i>&nbsp;&nbsp;Download block program</a>

[Xbox Block Program](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/audi-xbox-program.png)

### Python Program


[Open `technic_42160_audi_xbox_python.py`](program:technic_42160_audi_xbox_python.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/powered-up-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). Geoff Stearns, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-3"></a>

## Try audi xbox python

[Open `technic_42160_audi_xbox_python.py`](program:technic_42160_audi_xbox_python.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| D | `Motor` | `steer` |

With Xbox, compare small and large stick/trigger movements. Read the two Xbox variants and notice when input is sampled. Change one drive scale factor while preserving steering calibration.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

Pair the controller using its pairing button after starting the program. Keep the robot supported during the initial steering calibration.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

In this project we'll show you how to control the Audi RS Q e-tron with the
Xbox Controller, using either block programming or Python.

Be sure to check out the documentation in the Pybricks app for instructions
to pair the controller with the hub.

Note: This is brand a new feature. Try it with [Pybricks beta](https://beta.pybricks.com/)!

### Block Program

You can easily code this with the new block coding feature. Just drag and drop
the blocks as shown below, or download the ready-made project here. In
Pybricks, just go to the file menu and click the "Import a file" icon to open
it.

<a href="./audi_blocks.py" target="_blank" class="btn btn--primary"><i class="fas fa-puzzle-piece"></i>&nbsp;&nbsp;Download block program</a>

[Xbox Block Program](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/audi-xbox-program.png)

### Python Program


[Open `technic_42160_audi_xbox_python.py`](program:technic_42160_audi_xbox_python.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/powered-up-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). Geoff Stearns, The Pybricks Team. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

With Xbox, compare small and large stick/trigger movements. Read the two Xbox variants and notice when input is sampled. Change one drive scale factor while preserving steering calibration.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/powered-up-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). Geoff Stearns, The Pybricks Team. [MIT](LICENSE.txt).

