# 75253 · R2-D2

<a name="prepare"></a>

## Prepare the model

Make R2-D2 move, turn, and return to a stable standing position.

Use LEGO **75253** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=aDA_RQq4t3k)
- [Building instructions](https://www.lego.com/cdn/product-assets/product.bi.additional.main.pdf/75253_X_Artoo.pdf)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/boost/droid-commander/r2-d2/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try the program

[Open `boost_75253_r2_d2.py`](program:boost_75253_r2_d2.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `` |
| B | `Motor` | `` |
| C | `ColorDistanceSensor` | `sensor` |
| D | `Motor` | `actuator` |

Start with the MAIN PROGRAM section. Change one travel distance while keeping the tipping and support sequence unchanged. Explain why the body must tilt before travelling.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

### Code

This is an example program to help you get R2-D2 moving. If you are just getting
started with coding, you don't need to understand all of it. Just scroll down
to the `MAIN PROGRAM` section and start there.


[Open `boost_75253_r2_d2.py`](program:boost_75253_r2_d2.py)


### Further exploration

Here's a few ideas and challenges for further exploration:

- Modify the main program to call `stare_and_turn(360 * 2)` to see R2-D2 turn
  his body without turning his head.
- Write your own function to combine a sequence of actions. Then use it as
  part of a more complex program.

  ```python
  def my_function():
      # Write your commands here!
  ```

- Create an obstacle course for R2-D2 and write a program to navigate safely
  around the obstructions.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/boost/droid-commander/r2-d2/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Start with the MAIN PROGRAM section. Change one travel distance while keeping the tipping and support sequence unchanged. Explain why the body must tilt before travelling.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/boost/droid-commander/r2-d2/index.md). The Pybricks Team. [MIT](LICENSE.txt).

