# Community robot examples

Open these files from **File → Examples → pybricks → community**. Programs target
Pybricks **4.0+** and use standard palette blocks. Set numbers identify the source
of the hub and devices; the SPIKE/Inventor examples require a **custom build**,
not any arbitrary model assembled from that box. Suggested levels describe the
code being studied. Select **All** to expose every component in the palette.

Each new import links its pinned original in the first comments. The
[catalog](../catalog.json) records source hashes, equipment, levels and changes;
[the source review](SOURCES.md) includes authors, licenses and deferred candidates.
No example in this folder has been physically validated in PyBlocks.

## Sensor and concurrency lessons

These eight lessons adapt [The GummyBears Robotics tutorials](https://github.com/The-GummyBears-Robotics/PybricksPythonTut).
The driving lessons use a SPIKE Prime **45678** or Robot Inventor **51515** hub,
left motor **A counterclockwise**, right motor **B clockwise**, **56 mm wheels**
and **112 mm axle track**. Change the dimensions to match the build. A sonar on
**C** faces forward for avoidance/following, and **right** for wall following.
The color-stop lesson instead needs a downward color sensor on **C** near the mat.
Keep the hub level and still at the start of the gyro lesson.

Follow-object uses a 300 mm target and limits speed to ±150 mm/s. Follow-wall
uses a 200 mm target and limits steering to ±90°/s. Both brake when the sensor
returns 2000 mm (no valid measurement), then resume when measurements recover.
Avoidance treats that value as a clear path, preserving its original behavior.
The red-line lesson brakes on red rather than coasting. Driving loops brake on
exit; the gyro lesson waits for IMU readiness before its 1000 mm movement.

The concurrency lessons need free-moving motors **A/B** (parallel), **A** (timeout),
or **A plus sonar C** (obstacle race). The last is a one-motor task demonstration,
not a complete two-wheel driving robot. The timeout races 1080° of rotation with
one second; the obstacle race stops after ten seconds or at a distance ≤100 mm
while blinking. Cancelled/failed races explicitly stop the motor. Async sensor
reads use `await`, as required inside Pybricks coroutines.

## Custom Xbox robots

These adapt [Yavuz Selim Kolbasar's programs](https://github.com/yavuzselimkolbasar/Pybricks-Lego-Spike)
for SPIKE Prime **45678** and Robot Inventor **51515**, with a compatible Bluetooth
Xbox controller. Pair it before driving; **B exits and brakes every motor** in
these three programs. Controller loss propagates the error after motor cleanup.
RT moves forward, LT backward, and opposite trigger values cancel. Controls are
sampled once per 50 ms cycle. Wheel mixing stays within the declared power limit.

| Program | Connections | Controls and startup |
|---|---|---|
| `xbox_drive_arm` | Left C clockwise, right D counterclockwise, arm E clockwise | Left stick steers; A lowers arm to −90°, release raises it to 0°. Start with the arm raised. Retains the original 80% steering deadzone; `deadzone` can be reduced. Wheel power limit: 80%. |
| `xbox_car_lift` | Steering B, drive D, lift E, all clockwise | Center wheels before starting. Left stick steers up to ±90°. Y switches car/lift mode once per press; in lift mode its vertical axis powers the lift up to ±40%. Inactive mechanisms brake. |
| `xbox_boxer` | Left A counterclockwise, right B, left arm C, right arm D clockwise | Start with arms at rest. LB/RB punch, A raises both arms for defense; each press triggers once, with a return command after 500 ms. Driving remains responsive during arm movement. Four motors are required: SPIKE 45678 needs an extra motor. |

These are control programs for custom chassis, without supplied building
instructions. Arm and steering angles are motor-shaft angles. Manual startup
positioning establishes zero; there is no automatic endpoint calibration. Keep
mechanical travel within the configured targets. The boxer retains the original
500 ms defense interval, which may not complete a full 90° stroke at 100°/s.

## LEGO Technic 42100 with two LEGO remotes

`technic_42100_base_remote.py` and `technic_42100_upper_remote.py` adapt
[Tcm0's experimental layout](https://github.com/Tcm0/PybricksRemoteLayouts).
Load one onto each hub and pair **a separate Powered Up remote 88010 with each**.
Pair them one at a time. These two files operate independently and do not use radio
messages; they are an alternative to the Xbox pair below, not companion programs.

The lower hub uses A/B for tracks and D for the turntable. The upper hub uses
A/B for boom/arm and C/D for bucket tilt/opening. Left red button selects the A/B
pair. Right red button selects D on the base (right ± keys), or C/D upstairs
(left/right ± keys). Opposing keys cancel. The inactive group brakes immediately.
The green center button exits **only its own hub's** program; stop both remotes to
stop the whole model. Connection loss brakes that remote's hub.

Initial duty is **40%** instead of the original 100%; adjust `power` deliberately.
The upstream default clockwise directions are retained. **The author marks this
layout experimental and untested on 42100.** Verify each motor's direction and
travel on the assembled model before driving. There is no endpoint detection.

## Added program inventory

All rows retain their original MIT notices under [licenses](SOURCES.md#licenses).
The existing Xbox 42100 pair is documented below.

| File / original | Level | Hardware |
|---|---|---|
| [spike_45678_51515_obstacle_avoidance.py](spike_45678_51515_obstacle_avoidance.py) · [original](https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/7-sensors/distance-avoid.py) | intermediate | Forward sonar C; differential drive motors A/B, 56 mm wheels, 112 mm axle track |
| [spike_45678_51515_follow_object.py](spike_45678_51515_follow_object.py) · [original](https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/7-sensors/distance-follow.py) | advanced | Forward sonar C; differential drive motors A/B, 56 mm wheels, 112 mm axle track |
| [spike_45678_51515_follow_wall.py](spike_45678_51515_follow_wall.py) · [original](https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/7-sensors/distance-wallfollow.py) | advanced | RIGHT-facing sonar C; differential drive motors A/B, 56 mm wheels, 112 mm axle track |
| [spike_45678_51515_stop_at_red.py](spike_45678_51515_stop_at_red.py) · [original](https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/7-sensors/color-stopatcolor.py) | intermediate | Downward color sensor C; differential drive motors A/B, 56 mm wheels, 112 mm axle track |
| [spike_45678_51515_gyro_straight.py](spike_45678_51515_gyro_straight.py) · [original](https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/7-sensors/imu-drivingbase1.py) | intermediate | Differential drive motors A/B, 56 mm wheels, 112 mm axle track; level, stationary hub at startup |
| [spike_45678_51515_parallel_motors.py](spike_45678_51515_parallel_motors.py) · [original](https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/10-multitask/twomotors.py) | expert | Two free-running motors A/B |
| [spike_45678_51515_motor_timeout.py](spike_45678_51515_motor_timeout.py) · [original](https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/10-multitask/timeout.py) | expert | Free-running motor A |
| [spike_45678_51515_obstacle_race.py](spike_45678_51515_obstacle_race.py) · [original](https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/10-multitask/multitaskuntilonewin.py) | expert | Motor A and forward ultrasonic sensor C; this is a one-motor demonstration, not a two-wheel driving base |
| [spike_45678_51515_xbox_drive_arm.py](spike_45678_51515_xbox_drive_arm.py) · [original](https://github.com/yavuzselimkolbasar/Pybricks-Lego-Spike/blob/79199995d335f8eaeaf262079960376dbf2c5b97/DrivingBaseXboxController.py) | advanced | Custom differential chassis: left C clockwise, right D counterclockwise, arm E; Bluetooth Xbox controller |
| [spike_45678_51515_xbox_car_lift.py](spike_45678_51515_xbox_car_lift.py) · [original](https://github.com/yavuzselimkolbasar/Pybricks-Lego-Spike/blob/79199995d335f8eaeaf262079960376dbf2c5b97/Remote-Car.py) | advanced | Custom steering chassis: steering B, drive D, lift E clockwise; Bluetooth Xbox controller |
| [spike_45678_51515_xbox_boxer.py](spike_45678_51515_xbox_boxer.py) · [original](https://github.com/yavuzselimkolbasar/Pybricks-Lego-Spike/blob/79199995d335f8eaeaf262079960376dbf2c5b97/Boxing.py) | advanced | Custom four-motor boxer: left A counterclockwise, right B, left arm C, right arm D clockwise; Bluetooth Xbox controller; SPIKE 45678 needs one additional motor |
| [technic_42100_base_remote.py](technic_42100_base_remote.py) · [original](https://github.com/Tcm0/PybricksRemoteLayouts/blob/7e2580ec5e525cb017ffa10348abee71fceac800/42100%20LOWER%20HUB%20EXPERIMENTAL.py) | advanced | Assembled LEGO 42100: lower hub motors A/B/D and its own LEGO Powered Up remote 88010 |
| [technic_42100_upper_remote.py](technic_42100_upper_remote.py) · [original](https://github.com/Tcm0/PybricksRemoteLayouts/blob/7e2580ec5e525cb017ffa10348abee71fceac800/42100%20UPPER%20HUB%20EXPERIMENTAL.py) | advanced | Assembled LEGO 42100: upper hub motors A/B/C/D and a second LEGO Powered Up remote 88010 |

## Validation

The complete catalog is rebuilt from standard blocks and compiled to MPY ABI 5
and 6. Device calls are checked without generic catch-all templates. Community
runtime checks cover percent limits, trigger order, mode changes, button edges,
arm return timing, remote loss, sensor thresholds/no-measurement values, IMU
readiness and async cancellation/error cleanup. Motor behavior uses the virtual
hub; sensor/controller inputs and async scheduling are scripted. Gyro physics,
Bluetooth pairing and custom mechanisms still require real hardware checks.
The interactive simulator does not implement all hardware or coroutine features.

Audit downloaded originals without running them:

```bash
uv run python tools/adapt_pybricks_examples.py --community /path/to/sources
```

Place originals at each catalog entry's `source_file` under that directory
(or the raw URL basename when that field is absent). Hashes verify the pinned
input. Automatic adaptations also compare executable syntax; manual corrections
are checked by the runtime scenarios above. Never infer API or mechanical
correctness from successful bytecode compilation alone.

## LEGO Technic 42100 Liebherr R 9800 with Xbox

These two programs use Pybricks **4.0 or later**, the assembled 42100 with both
Technic hubs, and a compatible Bluetooth Xbox controller (for example 1708,
1797 or 1914). They use the existing motor, Xbox, radio and Python blocks;
select **All** in the library to study the complete program. No extra hub
library or host application is needed while driving.

| File | Load onto | Motors |
|---|---|---|
| [technic_42100_base_xbox.py](technic_42100_base_xbox.py) | Lower hub, in the tracked base | A: left track; B: right track; D: turntable; C unused |
| [technic_42100_upper.py](technic_42100_upper.py) | Upper hub, in the superstructure | A: boom; B: arm; C: bucket tilt; D: bucket opening |

### Upload and start

1. Install Pybricks 4+ on **both** hubs and keep the original model's motor wiring.
2. Open each file under **File → Examples → pybricks → community** and use
   **Upload** on its corresponding hub. These are separate programs, not imports
   of one another. Give the hubs distinct names to avoid mixing them up.
3. Turn on Xbox. For first pairing, hold its pairing button until its light
   flashes rapidly. Start the lower hub's stored program; it is blue while
   connecting. The Technic hub disconnects from the computer to use Xbox.
4. Start the upper hub's stored program with the controls released. Yellow means
   waiting for fresh commands; green means receiving them. The lower hub is green
   normally and yellow while **X** is held for slow movement. The upper program
   can also start first and wait for the lower hub.
5. Hold **X** during the first movement checks. Check one mechanism at a time.

| Xbox input | Movement |
|---|---|
| LT / RT | Left / right track forward, proportional to trigger travel |
| LB / RB | Left / right track backward |
| D-pad left / right | Turn the superstructure |
| Left stick vertical | Boom (upper A) |
| Right stick vertical | Arm (upper B) |
| Right stick horizontal | Bucket tilt (upper C) |
| A / B | Open / close bucket (upper D) |
| Hold X | Reduce every movement to 40% speed |
| Y | End the lower program; the upper hub stops on command timeout |

Release an input to brake its motor. Pressing both directions of the same
movement brakes it too. Either hub's green button stops its own program;
stopping the lower hub also makes the upper hub stop after its timeout.
Stopping only the upper hub does not stop the base. Stop the lower program before
reconnecting Studio to edit it. See the [Pybricks pairing instructions](https://docs.pybricks.com/en/latest/iodevices/xboxcontroller.html).

### Timing and tuning

Both loops wait 50 ms. Radio messages use channel **100** and contain
`(42100, sequence, boom, arm, tilt, opening)`, with four signed integer percentages.
The sequence advances modulo 256 even when controls do not change. The upper hub
brakes on missing/invalid data or after **500 ms without a changed sequence**,
checked every 50 ms. This also catches a transmitter repeating its last packet.
A fresh sequence resumes control. Y and Xbox disconnection stop the local motors
and stop broadcasting; stopping the upper motors therefore takes up to the
watchdog interval plus one polling interval. Radio delivery is not instantaneous.

`track_speed`, `turn_speed` and `maximum_speeds` are motor shaft speeds before
gearing, in degrees/second. Defaults are 600 for tracks/boom, 300 for rotation and
bucket opening, and 450 for arm/tilt. `slow_percent` adjusts X mode. These are
initial tuning values, not physically verified limits. There is no automatic
homing, endpoint detection or Cartesian bucket positioning: release the control
at the end of a mechanism's travel. For two excavators nearby, choose distinct
radio channels and change both files of each pair together.

### Sources and validation

The port directions and control layout come from
[gibona's 42100 demonstration](https://github.com/orgs/pybricks/discussions/1738).
Its [lower](https://github.com/gibona/pybricks/blob/74a66fc2c2de2ce7707f15d388f85bd7243c64fa/technic42100bottom.py)
and [upper](https://github.com/gibona/pybricks/blob/74a66fc2c2de2ce7707f15d388f85bd7243c64fa/technic42100top.py)
programs are pinned as references in the [catalog](../catalog.json), including
their original SHA-256 hashes. Upper mechanism names follow the
[nGeneRobotLab port table](https://ngene.org/nGeneRobotLab.html).

These files are new PyBlocks implementations of that control scheme under the
project's [MIT license](../../../LICENSE.txt), with current `BLERadio`, slower
motor settings, one sample per input per cycle, opposing-input cancellation,
slow/stop buttons, cleanup and sequence timeout. They do not reproduce the
upstream block metadata or source text. The reference repository did not declare
a license when checked; its files are not included or relicensed here.

Tests check motor commands on virtual Technic motors with scripted Xbox/radio
inputs, timeout/recovery, invalid packets, controller loss, stopping, block
rebuilding and MPY ABI 5/6 compilation. Interactive Studio simulation does not
provide Xbox pairing or hub-to-hub radio. Mechanical motion, end stops, radio
performance and the physical model have not been validated.

User instructions are also available in [English](../../../doc/en/examples.md)
and [Russian](../../../doc/ru/examples.md).
