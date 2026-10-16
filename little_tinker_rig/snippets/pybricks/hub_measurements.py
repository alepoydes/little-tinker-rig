"""Hub measurements and settings

Explicit device operations for studying complete robot programs."""

__category__ = "devices"


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    category="input",
    title="Acceleration vector",
    group=("Orientation and motion",),
)
def hub_imu_acceleration(hub: "PrimeHub | TechnicHub | MoveHub" = hub) -> "tuple":
    """Read the accelerometer vector."""
    return hub.imu.acceleration()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    variant="Default mounting",
    title="Hub value",
    group=("Hub system",),
)
def primehub() -> "PrimeHub":
    """Create a Prime or Inventor hub value.

    Create the Prime hub in its mounted orientation."""
    from pybricks.hubs import PrimeHub

    return PrimeHub()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    category="input",
    title="Rotation rate on axis",
    group=("Orientation and motion",),
)
def hub_imu_angular_velocity_axis(
    hub: "PrimeHub | TechnicHub | MoveHub" = hub, axis=Axis.Z
) -> "number[deg/s]":
    """Read gyroscope rotation rate. Options: axis."""
    from pybricks.parameters import Axis

    return hub.imu.angular_velocity(axis)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/hub_measurements/primehub",
    variant="Front direction",
    title="Hub value",
)
def primehub_front_side(front_side=Axis.X) -> "PrimeHub":
    """Create the Prime hub in its mounted orientation. Options: front_side."""
    from pybricks.hubs import PrimeHub
    from pybricks.parameters import Axis

    return PrimeHub(front_side=front_side)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/hub_measurements/primehub",
    variant="Top and front directions",
    title="Hub value",
)
def primehub_top_side_front_side(top_side=Axis.Z, front_side=Axis.X) -> "PrimeHub":
    """Create the Prime hub in its mounted orientation. Options: top_side, front_side."""
    from pybricks.hubs import PrimeHub
    from pybricks.parameters import Axis

    return PrimeHub(top_side=top_side, front_side=front_side)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    category="input",
    title="Upward side",
    group=("Orientation and motion",),
)
def hub_imu_up(hub: "PrimeHub | TechnicHub | MoveHub" = hub) -> "Side":
    """Read which side of the hub faces up."""
    return hub.imu.up()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    category="input",
    title="Pitch and roll",
    group=("Orientation and motion",),
)
def hub_imu_tilt(hub: "PrimeHub | TechnicHub | MoveHub" = hub) -> "tuple":
    """Read the pitch and roll angles."""
    return hub.imu.tilt()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    category="input",
    title="Rotation rate vector",
    group=("Orientation and motion",),
)
def hub_imu_angular_velocity(hub: "PrimeHub | TechnicHub | MoveHub" = hub) -> "tuple":
    """Read gyroscope rotation rate."""
    return hub.imu.angular_velocity()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Battery current",
    group=("Hub system",),
)
def hub_battery_current(hub: "PrimeHub | TechnicHub | MoveHub" = hub) -> "int":
    """Read the battery current in milliamps."""
    return hub.battery.current()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Charger connected",
    group=("Hub system",),
)
def hub_charger_connected(hub: "PrimeHub" = hub) -> "bool":
    """Check whether a USB charger is connected."""
    return hub.charger.connected()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Charging current",
    group=("Hub system",),
)
def hub_charger_current(hub: "PrimeHub" = hub) -> "int":
    """Read the charging current in milliamps."""
    return hub.charger.current()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Charger status",
    group=("Hub system",),
)
def hub_charger_status(hub: "PrimeHub" = hub) -> "int":
    """Read charger status: 0 idle, 1 charging, 2 full, 3 fault."""
    return hub.charger.status()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Set stop buttons",
    group=("Hub system",),
)
def hub_system_set_stop_button_buttons(
    hub: "PrimeHub | TechnicHub | MoveHub" = hub, buttons=Button.CENTER
):
    """Set the button combination that stops the program. Options: buttons."""
    from pybricks.parameters import Button

    hub.system.set_stop_button(buttons)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Hub Bluetooth name",
    group=("Hub system",),
)
def hub_system_name(hub: "PrimeHub | TechnicHub | MoveHub" = hub) -> "str":
    """Read the hub Bluetooth name."""
    return hub.system.name()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Shut down hub",
    group=("Hub system",),
)
def hub_system_shutdown(hub: "PrimeHub | TechnicHub | MoveHub" = hub):
    """Stop the program and turn the hub off."""
    hub.system.shutdown()


@inline_block(
    level="expert",
    icon="＝",
    color="value",
    category="input",
    title="Gyro ready",
    group=("Orientation and motion",),
)
def imu_ready(hub: "PrimeHub | TechnicHub" = hub) -> "bool":
    """Check that the gyro has finished calibrating before balancing."""
    return hub.imu.ready()


@inline_block(
    level="expert",
    icon="＝",
    color="value",
    category="input",
    title="Gyro rotation",
    group=("Orientation and motion",),
)
def imu_rotation(hub: "PrimeHub | TechnicHub" = hub, axis=Axis.X) -> "number[deg]":
    """Read accumulated gyro rotation around an axis or vector."""
    from pybricks.parameters import Axis

    return hub.imu.rotation(axis)


@inline_block(
    level="expert", icon="＝", color="value", category="values", title="Axis vector"
)
def axis_vector(x: "number" = 1, y: "number" = 0, z: "number" = 0):
    """Make a three-dimensional vector for the hub's mounting or measurement axis."""
    from pybricks.tools import vector

    return vector(x, y, z)


@inline_block(
    level="advanced",
    icon="◇",
    color="control",
    category="input",
    title="Choose program",
    group=("Buttons and controllers",),
)
def choose_program(first="H", second="S", third="L"):
    """Choose a symbol with the Prime/Inventor hub buttons and display."""
    from pybricks.tools import hub_menu

    return hub_menu(first, second, third)
