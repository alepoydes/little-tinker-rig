# 42100 · Liebherr R 9800

<a name="prepare"></a>

## Build and identify both hubs

Build the original LEGO 42100 excavator. Open **Assembly** to follow the included
LDraw steps, inspect each section and rotate the construction. Their numbering
differs from the LEGO instructions. The digital model omits decorative stickers.

- [LEGO building instructions, PDF 1](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6324103.pdf)
- [LEGO building instructions, PDF 2](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6324716.pdf)
- [LEGO set and available instructions](https://www.lego.com/en-us/service/building-instructions/42100)
- [Digital model by Philippe Hurbain (Philo)](https://forums.ldraw.org/thread-23139.html),
  [CC BY 2.0](robot/CAreadme.txt). Original robot design: LEGO Group.

You need both Technic hubs, Pybricks 4 or later, and a compatible Bluetooth Xbox
controller. Name the hubs differently so you can select the correct one when
uploading. Keep the original gearing and verify the port assignments below.

| Hub | A | B | C | D |
|---|---|---|---|---|
| Lower, in the tracked base | Left track | Right track | Unused | Turntable |
| Upper, in the superstructure | Boom | Arm | Bucket tilt | Bucket opening |

The 3D view illustrates construction; it does not simulate the mechanism or prove
motor travel limits. Mark this stage complete after the physical build and wiring
check. Model files, explanations and programs are included in the project; the
shared parts library is cached separately. Export the project with resources for
an offline copy on another computer. LEGO PDFs remain external links.

<a name="upper"></a>

## Upload the upper-hub program

[Open `technic_42100_upper.py`](program:technic_42100_upper.py).
Connect to the **upper hub** and use **Upload**. This file receives commands on
radio channel 100; it does not read Xbox directly. Start its stored program with
all controller inputs released. Yellow means waiting, green means fresh commands.
It can wait while you prepare the lower hub.

The receiver brakes on missing or invalid commands, or when their sequence stops
changing for 500 ms. It checks every 50 ms. This timeout is not an instantaneous
stop. Each hub's physical button stops its own program.

<a name="lower"></a>

## Upload the lower-hub program and drive

[Open `technic_42100_base_xbox.py`](program:technic_42100_base_xbox.py).
Connect to the **lower hub** and use **Upload**. These files run on different hubs;
they are not imports of one another. Turn on Xbox and, for first pairing, hold
its pairing button until the light flashes rapidly. Start the lower hub's stored
program. It is blue while connecting; the Technic hub disconnects from Studio to
use Xbox. See the [Pybricks pairing guide](https://docs.pybricks.com/en/latest/iodevices/xboxcontroller.html).

Hold **X** for the first movement checks. Try one mechanism at a time.

| Xbox input | Movement |
|---|---|
| LT / RT | Left / right track forward |
| LB / RB | Left / right track backward |
| D-pad left / right | Turn the superstructure |
| Left stick vertical | Boom |
| Right stick vertical | Arm |
| Right stick horizontal | Bucket tilt |
| A / B | Open / close bucket |
| Hold X | Reduce movement speeds to 40% |
| Y | Stop the lower program; upper motors stop on timeout |

Release an input to brake its motor. Stop before a mechanism reaches its end of
travel: these programs do not automatically home or limit actuator positions.
Stopping only the upper hub does not stop the base. Stop the lower program before
reconnecting Studio to edit it.

<a name="experiment"></a>

## Compare movement speeds

Find `slow_percent` in the lower program. Predict how a smaller value changes
movement while X is held, then try it. Keep the motor directions and radio packet
layout unchanged. Both hubs must use the same radio channel. Explain why the upper
hub needs a timeout even when the lower hub sends a stop command.

Save the project to retain both programs and completion marks.

## Credits

The [community demonstration by gibona](https://github.com/orgs/pybricks/discussions/1738)
provided the control and port layout. The included programs are existing PyBlocks
implementations under the [MIT license](LICENSE.txt), with current radio APIs,
slow/stop controls and a sequence timeout. They do not reproduce the unlicensed
upstream programs. The LDraw model has its separate CC BY 2.0 license and retains
its authorship. Geometry and software have been checked digitally; the physical
excavator and end stops have not been tested here.
