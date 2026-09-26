# Community source review

Reviewed on **2026-09-26**. This is a curated selection of runnable programs for
SPIKE Prime, Robot Inventor and Technic, not an exhaustive community archive.
BOOST remains covered by the existing official imports. EV3 is outside scope.

Discovery started with the Pybricks
[Show and Tell discussions](https://github.com/orgs/pybricks/discussions/categories/show-and-tell)
and [community project list](https://github.com/orgs/pybricks/discussions/157),
then followed authors' repositories. The [program inventory](README.md#added-program-inventory)
links every included original. Revisions and original byte hashes are recorded
in [catalog.json](../catalog.json), including references for the earlier Xbox
42100 implementation. No community runtime package is required on the hub.

## Included in this selection

| Repository / revision | Included | Adaptation |
|---|---|---|
| [The GummyBears Robotics tutorials](https://github.com/The-GummyBears-Robotics/PybricksPythonTut/tree/5d199cfea9246176dc37a153250233f40f3d082c) | Eight lessons: avoidance, object/wall following, red stop, gyro straight, parallel motors, timeout, obstacle race | Preserve teaching goals and parameters; add bounded following, missing-measurement handling, readiness and cleanup; await sensor reads inside async tasks. Parallel motors changes only formatting. |
| [Yavuz Selim Kolbasar's SPIKE robots](https://github.com/yavuzselimkolbasar/Pybricks-Lego-Spike/tree/79199995d335f8eaeaf262079960376dbf2c5b97) | All three programs: boxer, differential drive with arm, steering car with lift | Fix percent scaling and trigger order, normalize mixed wheel commands, sample once per cycle, stop inactive actuators and brake on exit. Edge-trigger modes/gestures and nonblocking arm returns. Retain controls and document changed behavior. |
| [Tcm0's remote layouts](https://github.com/Tcm0/PybricksRemoteLayouts/tree/7e2580ec5e525cb017ffa10348abee71fceac800) | Two experimental 42100 entry points for separate LEGO remotes | Explicit imports, 40% initial duty, opposite-button cancellation, inactive-group braking, local stop and cleanup. Preserve the author's experimental status and original default directions. |

Set numbers name compatible parts sources. They do not imply that these custom
SPIKE/Inventor chassis have official building instructions. Equipment, mounting,
motor directions and startup positioning are in the [guide](README.md).

## Reviewed but not added

| Source | Reason |
|---|---|
| Remaining GummyBears tutorial files | Many introduce single API operations already covered by our palette and examples; sensor directories also repeat lessons. This selection prioritizes complete small activities. It does not claim to import the full course. |
| Other Tcm0 layouts | 42099, 42109, 42124, 42129, 42140 and 42160 already have set-specific control examples. The 10277 train uses a City hub, outside the current target families. |
| [repkovsky/technic](https://github.com/repkovsky/technic/tree/892e8473475e1c4e76f2ba19f8c1c4cc9fe64b68) | The 42114 hauler algorithm is already represented by `technic_42114_hauler.py` through the official repository. |
| [MEL1H's expanded 42140 controls](https://github.com/MEL1H/Pybricks-42140-App-Controlled-Transformation-Vehicle), [discussion](https://github.com/orgs/pybricks/discussions/2170) | Useful Xbox/remote, cruise and flip-control candidate. The large controller needs a separate review of cruise-loop input/flip/stop handling and low-battery state; it is not included as a verified drop-in program. |
| [LavaWolf911/SpikePrime-Xbox-Integration](https://github.com/LavaWolf911/SpikePrime-Xbox-Integration/tree/f17247b7374e57dc750aae02054848f9a26acd5a) | Basic drive/claw controls overlap this selection. The extended demo additionally needs fixes to mixed duty limits and optional wrist state before import. |
| [geekcubed/PyBricksBoost](https://github.com/geekcubed/PyBricksBoost/tree/6802aa1ac955bcd5ec10dc2bec40d6f55b06d924) | Despite its name, the available AutoRover program is an EV3 template, not a BOOST activity. |
| [LEGO-Robotics collection](https://github.com/LEGO-Robotics/LEGO-Robotics/tree/f957296852e231386835c96111cfd380701a5b0b) | Large mixed-platform collection; a reusable repository-wide license was not found. No bulk import or claim of complete program-level review. |
| [Mecanum platform](https://github.com/MonongahelaCryptidCooperative/Mecanum/tree/21a8ad753e1f396a73c173599252a5a0bd49432d) | Custom wheel build and no declared repository license found during this review. |
| [Automatic gearbox](https://github.com/orgs/pybricks/discussions/1995) | Custom mechanics and shift calibration require a dedicated build guide; not a complete set-specific example. |
| [Diwheel](https://github.com/orgs/pybricks/discussions/1991) | Published code imports a PID controller module not included in the post. |
| [Xbox broadcast diagnostics](https://github.com/orgs/pybricks/discussions/1883) | Source permits personal/noncommercial use only. Not redistributed in this MIT collection; the existing 42100 Xbox pair already demonstrates controller-to-radio commands. |

## Licenses

Unmodified upstream license texts are bundled beside the adaptations and included
in distribution license files:

- [The GummyBears Robotics — MIT, copyright 2026](licenses/gummybears.txt).
- [YavuzSelimKolbasar — MIT, copyright 2025](licenses/yavuzselimkolbasar.txt).
- [Tcm0 — MIT, copyright 2021](licenses/tcm0.txt).

The earlier Xbox 42100 pair is a new implementation of a published control scheme,
not a copy of unlicensed source; see its [separate attribution](README.md#sources-and-validation).

## API references

Adaptations use public APIs documented by Pybricks. The latest documentation at
review time identifies itself as **4.1.0b1**; these programs target the established
4.0 API subset and do not require the newer connection-management options.

- [Xbox input ranges and trigger order](https://docs.pybricks.com/en/latest/iodevices/xboxcontroller.html).
- [Ultrasonic distance and the 2000 mm sentinel](https://docs.pybricks.com/en/latest/pupdevices/ultrasonicsensor.html).
- [Asynchronous tasks and racing](https://docs.pybricks.com/en/latest/tools/index.html).

Successful compilation and scripted inputs establish code-level checks, not
Bluetooth reliability, mechanism travel limits or complete simulator support.
