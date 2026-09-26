"""Exercise community adaptations at hardware boundaries, without a GUI."""

import asyncio
from types import SimpleNamespace

import pytest
from test_pybricks_examples import EXAMPLES, EndInputs, virtual_activity

COMMUNITY = EXAMPLES / "community"
PREFIX = "spike_45678_51515_"


def run_controller(name, frames, *, disconnect=False):
    """Script sampled inputs; use virtual motors, except timed background motion."""
    path = COMMUNITY / (name + ".py")
    with virtual_activity(name) as (world, _):
        from pybricks import iodevices, pupdevices, tools
        from pybricks.parameters import Button

        current, elapsed, counts = [None], [0], [0, 0, 0]
        inputs = iter(frames)
        duties, snapshots, movements = {}, [], []
        base_motor, original_wait = pupdevices.Motor, tools.wait

        class Motor(base_motor):
            def dc(self, duty):
                duties[self.port] = duty
                super().dc(duty)  # Rejects values outside [-100, 100].

            def brake(self):
                duties[self.port] = 0
                super().brake()

            def run_time(self, speed, duration, *, wait):
                # No real background thread: the program's timer issues its
                # return command. Assert its deadline below.
                assert wait is False
                movements.append((elapsed[0], self.port, "time", duration))
                self.run(speed)

            def run_target(self, speed, angle, **kwargs):
                movements.append((elapsed[0], self.port, "target", angle))
                super().run_target(speed, angle, **kwargs)

        def buttons():
            current[0] = next(inputs, None)
            if current[0] is None:
                if disconnect:
                    raise OSError("Controller disconnected")
                return {Button.CENTER if "remote" in name else Button.B}
            counts[0] += 1
            return {Button[b] for b in current[0][0]}

        def sample(index):
            counts[index] += 1
            return current[0][index]

        def wait(milliseconds):
            snapshots.append(duties.copy())
            elapsed[0] += milliseconds
            original_wait(milliseconds)

        controller = SimpleNamespace(
            buttons=SimpleNamespace(pressed=buttons),
            triggers=lambda: sample(1),
            joystick_left=lambda: sample(2),
        )
        pupdevices.Motor = Motor
        pupdevices.Remote = iodevices.XboxController = lambda: controller
        tools.wait = wait
        tools.StopWatch = lambda: SimpleNamespace(time=lambda: elapsed[0])
        if disconnect:
            with pytest.raises(OSError, match="Controller disconnected"):
                exec(path.read_text(), {})
        else:
            exec(path.read_text(), {})
        assert all(port["speed"] == 0 for port in world.ports.values())
        assert len(snapshots) == counts[0]
        if "xbox" in name:
            assert counts == [len(frames)] * 3
        return snapshots, movements


@pytest.mark.parametrize("disconnect", [False, True])
@pytest.mark.parametrize("name", ["xbox_boxer", "xbox_drive_arm", "xbox_car_lift"])
def test_xbox_mixing_uses_percentages_and_stops(name, disconnect):
    frames = [
        ((), (0, 100), (0, 0)),
        ((), (0, 100), (100, 0)),
        ((), (100, 0), (-100, 0)),
        ((), (100, 100), (0, 0)),
    ]
    snapshots, _ = run_controller(PREFIX + name, frames, disconnect=disconnect)
    ports = {"xbox_boxer": "AB", "xbox_drive_arm": "CD", "xbox_car_lift": "D"}[name]
    limit = 80 if name == "xbox_drive_arm" else 100
    assert all(snapshots[0][p] == limit for p in ports)
    assert all(abs(s[p]) <= limit for s in snapshots for p in ports)
    assert all(snapshots[3][p] == 0 for p in ports)
    if name != "xbox_car_lift":
        # Saturation must preserve the intended left/right ratio.
        steering = 80 if name == "xbox_drive_arm" else 50
        assert snapshots[1][ports[0]] / snapshots[1][ports[1]] == pytest.approx(
            (100 - steering) / (100 + steering)
        )


def test_car_mode_switch_is_once_per_press_and_stops_inactive_motors():
    snapshots, _ = run_controller(
        PREFIX + "xbox_car_lift",
        [
            ((), (0, 100), (0, 100)),
            (("Y",), (0, 100), (0, 100)),
            (("Y",), (0, 100), (0, -100)),
            ((), (0, 100), (0, 0)),
            (("Y",), (100, 0), (0, 100)),
        ],
    )
    assert [(s["D"], s["E"]) for s in snapshots] == [
        (100, 0),
        (0, 40),
        (0, -40),
        (0, 0),
        (-100, 0),
    ]


def test_boxer_returns_arms_without_blocking_or_repeating_held_buttons():
    _, moves = run_controller(
        PREFIX + "xbox_boxer",
        [(("LB", "RB"), (0, 100), (0, 0))] * 12
        + [((), (0, 0), (0, 0))]
        + [(("A",), (0, 0), (0, 0))] * 12,
    )
    for port in "CD":
        assert [m for m in moves if m[1] == port] == [
            (0, port, "time", 500),
            (500, port, "target", 0),
            (650, port, "target", 90),
            (1150, port, "target", 0),
        ]


@pytest.mark.parametrize("part", ["base", "upper"])
@pytest.mark.parametrize("disconnect", [False, True])
def test_excavator_remotes_switch_motor_groups_and_cancel_opposing_buttons(
    part, disconnect
):
    snapshots, _ = run_controller(
        f"technic_42100_{part}_remote",
        [
            (("LEFT_PLUS", "RIGHT_MINUS"), (), ()),
            (("RIGHT", "LEFT_PLUS", "RIGHT_PLUS"), (), ()),
            (("LEFT_PLUS", "LEFT_MINUS", "RIGHT_PLUS", "RIGHT_MINUS"), (), ()),
        ],
        disconnect=disconnect,
    )
    assert snapshots[0]["A"] == 40 and snapshots[0]["B"] == -40
    assert snapshots[1]["A"] == snapshots[1]["B"] == 0
    assert snapshots[1]["D"] == 40
    if part == "upper":
        assert snapshots[0]["C"] == snapshots[0]["D"] == 0
        assert snapshots[1]["C"] == 40
    assert all(duty == 0 for duty in snapshots[2].values())


@pytest.mark.parametrize(
    "name",
    [
        "obstacle_avoidance",
        "follow_object",
        "follow_wall",
        "stop_at_red",
        "gyro_straight",
    ],
)
def test_sensor_lessons_handle_thresholds_and_missing_measurements(name):
    path = COMMUNITY / (PREFIX + name + ".py")
    with virtual_activity(path.stem):
        from pybricks import hubs, pupdevices, robotics
        from pybricks.parameters import Color

        commands = []
        distances = iter([50, 200, 300, 600, 1999, 2000, 300])
        colors = iter([Color.BLUE, Color.WHITE, Color.RED])
        readiness = iter([False, False, True])

        def distance():
            try:
                return next(distances)
            except StopIteration:
                raise EndInputs from None

        pupdevices.UltrasonicSensor = lambda port: SimpleNamespace(distance=distance)
        pupdevices.ColorSensor = lambda port: SimpleNamespace(
            color=lambda: next(colors)
        )

        # Script mechanical completion and IMU readiness; no claim of gyro physics.
        def drive_base(left, right, wheel, track):
            assert (left.port, right.port, wheel, track) == ("A", "B", 56, 112)
            return SimpleNamespace(
                **{
                    method: (
                        lambda *args, method=method: commands.append((method, args))
                    )
                    for method in ("drive", "straight", "turn", "brake", "use_gyro")
                }
            )

        robotics.DriveBase = drive_base
        original_hub = hubs.PrimeHub

        def hub():
            result = original_hub()
            result.imu.ready = lambda: next(readiness)
            result.display.text = lambda text: None
            return result

        hubs.PrimeHub = hub
        if name in {"stop_at_red", "gyro_straight"}:
            exec(path.read_text(), {})
        else:
            with pytest.raises(EndInputs):
                exec(path.read_text(), {})
        assert commands[-1] == ("brake", ())
        motions = [args for method, args in commands if method == "drive"]
        if name == "follow_object":
            assert motions == [(-125, 0), (-50, 0), (0, 0), (150, 0), (150, 0), (0, 0)]
            assert commands[-3] == ("brake", ())  # Missing object, then recovery.
        elif name == "follow_wall":
            assert motions == [
                (150, -45),
                (150, 0),
                (150, 30),
                (150, 90),
                (150, 90),
                (150, 30),
            ]
            assert commands[-3] == ("brake", ())
        elif name == "obstacle_avoidance":
            assert commands[:4] == [("straight", (-100,)), ("turn", (90,))] * 2
            assert motions == [(150, 0)] * 5
        elif name == "gyro_straight":
            assert next(readiness, None) is None
            assert commands[:-1] == [("use_gyro", (True,)), ("straight", (1000,))]
        else:
            assert motions == [(200, 0)]
            assert next(colors, None) is None


@pytest.mark.parametrize("name", ["parallel_motors", "motor_timeout", "obstacle_race"])
@pytest.mark.parametrize("failure", [False, True])
def test_async_lessons_await_io_and_stop_cancelled_motion(name, failure):
    path = COMMUNITY / (PREFIX + name + ".py")
    with virtual_activity(path.stem):
        from pybricks import pupdevices, tools

        calls, stopped, active = [], set(), set()

        class Motor:
            def __init__(self, port):
                self.port = port.name

            async def run_angle(self, speed, angle):
                calls.append((self.port, speed, angle))
                active.add(self.port)
                await asyncio.sleep(0)
                if failure:
                    raise OSError("Motor error")
                if name == "motor_timeout":
                    await asyncio.Future()  # Timeout must cancel this operation.
                active.remove(self.port)

            def run(self, speed):
                calls.append((self.port, speed))
                active.add(self.port)

            def stop(self):
                stopped.add(self.port)
                active.discard(self.port)

        async def distance():
            await asyncio.sleep(0)
            if failure:
                raise OSError("Sensor error")
            return 50

        async def wait(milliseconds):
            if milliseconds == 10000:
                await asyncio.Future()
            await asyncio.sleep(0)

        async def multitask(*coroutines, race=False):
            # Model Pybricks' public cancellation contract with asyncio tasks.
            tasks = [asyncio.create_task(c) for c in coroutines]
            try:
                if race:
                    done, _ = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        task.result()
                else:
                    await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        pupdevices.Motor = Motor
        pupdevices.UltrasonicSensor = lambda port: SimpleNamespace(distance=distance)
        tools.wait, tools.multitask, tools.run_task = wait, multitask, asyncio.run
        if failure:
            with pytest.raises(OSError):
                exec(path.read_text(), {})
        else:
            exec(path.read_text(), {})
        if name == "parallel_motors":
            assert calls == [("A", 500, 360), ("B", 300, 720)]
            if not failure:
                assert not active
        else:
            assert stopped == {"A"} and not active
