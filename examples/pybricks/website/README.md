# Programs from Pybricks project pages

Open these programs through **File → Examples → pybricks → website**. Set-specific
filenames include the LEGO set number. Tutorials are reusable across builds;
the menu examples need a Prime/Inventor hub. Select **All** to find every block.

The catalog includes all downloadable Python programs from the audited project
pages that target the supported hub families, plus both inline hub-menu programs.
The existing [42109 Xbox program](../technic_42109_xbox.py) is linked rather than
copied. This is an inventory of the project pages retrieved on 2026-09-26, not a
claim about future website additions or every code fragment in API documentation.
Sources and exclusions: [inventory](catalog.json). Attribution: [notice](NOTICE.md).

## Programs and requirements

Firmware versions are minimum requirements for the APIs used; compilation alone
cannot confirm that the installed hub firmware contains those APIs. Xbox programs
need a compatible Bluetooth controller. Car calibration needs mechanical stops.
The interactive simulator does not implement Xbox pairing, cooperative Pybricks
tasks, gyro balancing, inter-hub radio or camera processing.

| Program | Sets | Level | Firmware | Extra requirements |
|---|---|---|---|---|
| [tutorials/allow_missing_motors.py](tutorials/allow_missing_motors.py) · [source](https://pybricks.com/project/disable-motor-detect/) | Reusable tutorial | expert | 3.5+ | Devices connected as shown in the program |
| [inventor_51515_spike_45678_ball_balancer.py](inventor_51515_spike_45678_ball_balancer.py) · [source](https://pybricks.com/project/lego-mindstorms-ball-balancer/) | 51515, 45678 | expert | 3.5+ | Ball and the exact published mechanism; SPIKE version also uses expansion elements |
| [tutorials/block_comment.py](tutorials/block_comment.py) · [source](https://pybricks.com/project/pybricks-3-5-released/) | Reusable tutorial | advanced | 3.5+ | Devices connected as shown in the program |
| [tutorials/block_drivebase_reset.py](tutorials/block_drivebase_reset.py) · [source](https://pybricks.com/project/pybricks-3-5-released/) | Reusable tutorial | advanced | 3.5+ | Devices connected as shown in the program |
| [tutorials/block_keyboard.py](tutorials/block_keyboard.py) · [source](https://pybricks.com/project/pybricks-3-5-released/) | Reusable tutorial | advanced | 3.5+ | Host console forwarding keyboard input to hub stdin; Studio Console currently displays output only |
| [tutorials/block_rumble.py](tutorials/block_rumble.py) · [source](https://pybricks.com/project/pybricks-3-5-released/) | Reusable tutorial | advanced | 3.5+ | Compatible Bluetooth Xbox controller; motor A |
| [tutorials/check_battery_box.py](tutorials/check_battery_box.py) · [source](https://pybricks.com/project/disable-motor-detect/) | Reusable tutorial | advanced | 3.5+ | Devices connected as shown in the program |
| [tutorials/check_motor.py](tutorials/check_motor.py) · [source](https://pybricks.com/project/disable-motor-detect/) | Reusable tutorial | advanced | 3.5+ | Devices connected as shown in the program |
| [tutorials/check_override.py](tutorials/check_override.py) · [source](https://pybricks.com/project/disable-motor-detect/) | Reusable tutorial | advanced | 3.5+ | Devices connected as shown in the program |
| [tutorials/hello_world.py](tutorials/hello_world.py) · [source](https://pybricks.com/project/spike-hub-menu/) | 45678, 51515 | advanced | 3.5+ | Devices connected as shown in the program |
| [tutorials/light.py](tutorials/light.py) · [source](https://pybricks.com/project/spike-hub-menu/) | 45678, 51515 | advanced | 3.5+ | Prime/Inventor hub |
| [tutorials/sensor_start.py](tutorials/sensor_start.py) · [source](https://pybricks.com/project/spike-hub-menu/) | Reusable tutorial | advanced | 3.5+ | BOOST ColorDistanceSensor on A and a DC motor on B, or menu motor on A |
| [technic_42099_remote.py](technic_42099_remote.py) · [source](https://pybricks.com/project/technic-42099-powered-up-remote/) | 42099 | advanced | 3.5+ | LEGO Powered Up remote 88010 |
| [technic_42099_xbox.py](technic_42099_xbox.py) · [source](https://pybricks.com/project/technic-42099-xbox/) | 42099 | advanced | 3.5+ | Bluetooth Xbox controller |
| [technic_42109_remote.py](technic_42109_remote.py) · [source](https://pybricks.com/project/technic-42109-powered-up-remote/) | 42109 | advanced | 3.5+ | LEGO Powered Up remote 88010 |
| [technic_42124_remote.py](technic_42124_remote.py) · [source](https://pybricks.com/project/technic-42124-powered-up-remote/) | 42124 | advanced | 3.5+ | LEGO Powered Up remote 88010 |
| [technic_42124_xbox.py](technic_42124_xbox.py) · [source](https://pybricks.com/project/technic-42124-xbox/) | 42124 | advanced | 3.5+ | Bluetooth Xbox controller |
| [technic_42129_remote.py](technic_42129_remote.py) · [source](https://pybricks.com/project/technic-42129-powered-up-remote/) | 42129 | advanced | 3.5+ | LEGO Powered Up remote 88010 |
| [technic_42129_xbox.py](technic_42129_xbox.py) · [source](https://pybricks.com/project/technic-42129-xbox/) | 42129 | advanced | 3.5+ | Bluetooth Xbox controller |
| [technic_42131_remote.py](technic_42131_remote.py) · [source](https://pybricks.com/project/technic-42131-powered-up-remote/) | 42131 | expert | 3.5+ | LEGO Powered Up remote 88010 |
| [technic_42131_xbox.py](technic_42131_xbox.py) · [source](https://pybricks.com/project/technic-42131-xbox/) | 42131 | expert | 3.5+ | Bluetooth Xbox controller |
| [technic_42146_base_remote.py](technic_42146_base_remote.py) · [source](https://pybricks.com/project/technic-42146-powered-up-remote/) | 42146 | expert | 4.0+ | LEGO Powered Up remote 88010; Two Technic hubs; channel 5; run the crane program on the second hub |
| [technic_42146_base_xbox.py](technic_42146_base_xbox.py) · [source](https://pybricks.com/project/technic-42146-xbox/) | 42146 | expert | 4.0+ | Bluetooth Xbox controller; Two Technic hubs; channel 5; run the crane program on the second hub |
| [technic_42146_crane.py](technic_42146_crane.py) · [source](https://pybricks.com/project/technic-42146-powered-up-remote/) | 42146 | expert | 4.0+ | Two Technic hubs; channel 5; run the crane program on the second hub |
| [technic_42160_remote.py](technic_42160_remote.py) · [source](https://pybricks.com/project/technic-42160-powered-up-remote/) | 42160 | advanced | 3.5+ | LEGO Powered Up remote 88010 |
| [technic_42160_xbox.py](technic_42160_xbox.py) · [source](https://pybricks.com/project/technic-42160-xbox/) | 42160 | advanced | 3.5+ | Bluetooth Xbox controller |
| [tutorials/sound.py](tutorials/sound.py) · [source](https://pybricks.com/project/spike-hub-menu/) | 45678, 51515 | advanced | 3.5+ | Prime/Inventor hub |
| [spike_45678_arm_camera.py](spike_45678_arm_camera.py) · [source](https://pybricks.com/project/robot-arm-camera-tracker/) | 45678 | expert | 4.1+ | Pybricks Code camera/vision host and the published model; Studio does not provide AppData camera processing |
| [spike_45678_groceries.py](spike_45678_groceries.py) · [source](https://pybricks.com/project/machine-learning-groceries/) | 45678 | expert | 4.1+ | Pybricks Code camera/vision host and the published model; Studio does not provide AppData camera processing |
| [tutorials/spike_45678_menu.py](tutorials/spike_45678_menu.py) · [source](https://pybricks.com/project/spike-hub-menu/) | 45678, 51515 | advanced | 3.5+ | Prime/Inventor hub |
| [tutorials/spike_45678_choose_program.py](tutorials/spike_45678_choose_program.py) · [source](https://pybricks.com/project/spike-hub-menu/) | 45678, 51515 | expert | 3.5+ | BOOST ColorDistanceSensor on A and a DC motor on B, or menu motor on A; Prime/Inventor hub |

## Multi-file and multi-hub programs

Keep the `tutorials` directory together: menu programs import their missions,
and optional-motor programs import `allow_missing_motors`. Upload includes these
local dependencies automatically. Optional-motor examples intentionally suppress
missing-device errors; use the normal motor blocks when a disconnected cable
should be reported.

For 42146, run `technic_42146_crane.py` on the crane hub and either base program
on the base hub. Both use channel 5. The crane coasts its motors when incoming
radio data is absent. The two programs are separate uploads, not Python modules
imported by each other. The Xbox and LEGO remote variants have different turntable
motor directions; preserve the setup from the chosen program.

The camera arm and grocery examples use `AppData` from a compatible Pybricks Code
vision host. Studio can edit and compile their hub source but does not supply
camera detections. They are not standalone Studio camera demonstrations.

## Excluded downloads

- [block_stop_button.py](https://pybricks.com/assets/programs/block_stop_button.py): Requires the unsupported SPIKE Essential hub.
- [duplo.py](https://pybricks.com/assets/programs/duplo.py): Requires the external Duplo train and LWP3 integration, outside the supported robot models.
- [duplo_example_basic.py](https://pybricks.com/assets/programs/duplo_example_basic.py): Requires the external Duplo train and LWP3 integration, outside the supported robot models.
- [duplo_example_dial.py](https://pybricks.com/assets/programs/duplo_example_dial.py): Requires the external Duplo train and LWP3 integration, outside the supported robot models.
- [duplo_example_essential.py](https://pybricks.com/assets/programs/duplo_example_essential.py): Requires the unsupported SPIKE Essential hub.
- [tic_tac_toe.py](https://pybricks.com/assets/programs/tic_tac_toe.py): Requires the unsupported SPIKE Essential hub.

The EV3 archive, City/Duplo models, SPIKE Essential builds, desktop editor setup
articles and the external MicroPython BLE package are outside the supported
hub-program import. Articles without a Python program introduce no catalog file.

## Reproducible audit

Download the sources named in the inventory into one directory; keep their URL
basenames. The two inline menu sources use the `source_file` names recorded in
[the main catalog](../catalog.json). Their hashes cover the extracted Python
text, before formatting or attribution is added.

```sh
uv run python tools/adapt_pybricks_examples.py --website /path/to/website-programs
```

The audit checks original hashes and adapted executable trees. Regression checks
also compile both MPY formats, rebuild recognized blocks, exercise Xbox input
sampling, and check crane motor coasting when messages disappear. These checks
use scripted device boundaries and do not validate physical robot mechanics.
