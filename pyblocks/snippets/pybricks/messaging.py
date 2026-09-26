"""Hub and app messages

Pybricks 4 radio messages and external host data; not simulated by Studio."""

@inline_block(level="expert", icon="▣", color="state")
def broadcast_radio(channel: "int" = 5) -> "BLERadio":
    """Create a Bluetooth broadcaster on channel 0–255; requires Pybricks 4."""
    from pybricks.messaging import BLERadio

    return BLERadio(broadcast_channel=channel)


@inline_block(level="expert", icon="▣", color="state")
def observing_radio(channel: "int | None" = 0, channels: "list" = [5]) -> "BLERadio":
    """Create a radio that can receive the listed channels; requires Pybricks 4."""
    from pybricks.messaging import BLERadio

    return BLERadio(broadcast_channel=channel, observe_channels=channels)


@inline_block(level="expert", icon="▶", color="action")
def broadcast(radio: "BLERadio" = radio, data=(0, 0, 0)):
    """Broadcast a small value or list of values to other hubs."""
    radio.broadcast(data)


@inline_block(level="expert", icon="＝", color="value")
def observe(radio: "BLERadio" = radio, channel: "int" = 5):
    """Read the latest message, or None when the channel has no recent data."""
    return radio.observe(channel)


@inline_block(level="expert", icon="▣", color="state")
def app_data(modes: "list" = [(0, 4)]) -> "AppData":
    """Allocate host data buffers. Requires a compatible external app, such as Pybricks Code vision."""
    from pybricks.messaging import AppData

    return AppData(modes)


@inline_block(level="expert", icon="▶", color="action")
def configure_app(
    app: "AppData" = app, mode: "int" = 0, parameter: "int" = 0, value=b"\x00"
):
    """Configure an external app processor; Studio does not provide camera processing."""
    app.configure(mode, parameter, value)


@inline_block(level="expert", icon="＝", color="value")
def app_bytes(app: "AppData" = app, mode: "int" = 0) -> "bytes":
    """Read the bytes last received from the external app."""
    return app.get_bytes(mode)
