# 42131 · CAT D11 bulldozer

<a name="prepare"></a>

## Prepare the model

Operate the tracks and attachments with the remote.

Use LEGO **42131** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=N7OmW-7u8fA)
- [Building instructions](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6403271.pdf)
- [Building instructions](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6403276.pdf)
- [Video](https://www.youtube.com/watch?v=gy3nFvojZ2o)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42131-cat-bulldozer/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try bulldozer

[Open `technic_42131_bulldozer.py`](program:technic_42131_bulldozer.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `left_motor` |
| B | `Motor` | `right_motor` |
| C | `Motor` | `function_motor` |
| D | `Motor` | `switch_motor` |

Read the button mappings and gearbox positions before running. Try each attachment separately, then change one operating speed and compare the response.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

### Program

This program lets you drive and operate the Cat® D11 Bulldozer using the
Powered Up remote control. No smartphone required!

When the program begins, it resets the function selector to the zero position,
corresponding to the blade up and down movement. You can select any function
by pressing the *green button* along with one of the gray buttons. This will
change the remote light and switch the function selector as follows:

* Left ＋ (blue): Moves the blade up and down.
* Left − (red): Tilts the blade back and forth.
* Right ＋ (yellow): Moves the ladder up and down.
* Right − (green): Moves the ripper up and down.

Once the function is selected, use the red buttons to control the motor that
powers the selected function.

Use the gray buttons to control the tracks. You can change
the ``DRIVE_ACCELERATION`` value in the code to a lower value to make the
vehicle start and stop driving more gradually. You can also change the speed
by reducing the ``DRIVE_SPEED`` value.



[Open `technic_42131_bulldozer.py`](program:technic_42131_bulldozer.py)
### Credits

This program was inspired by Pybricks user AVCampos' program first shared on
[Eurobricks](https://www.eurobricks.com/forum/index.php?/forums/topic/182012-42131-cat-d11-bulldozer/&page=46&tab=comments#comment-3455837). Be sure
to check out his code and [video](https://www.youtube.com/watch?v=gy3nFvojZ2o)
for additional inspiration.

And thanks to Jim van Gulik who lent his bulldozer to the Pybricks team to
make this program and video.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42131-cat-bulldozer/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Read the button mappings and gearbox positions before running. Try each attachment separately, then change one operating speed and compare the response.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42131-cat-bulldozer/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

