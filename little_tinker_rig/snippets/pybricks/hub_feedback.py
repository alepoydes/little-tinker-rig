"""Sound and light options

Explicit device operations for studying complete robot programs."""

__category__ = "output"


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/hubs/beep",
    variant="Default tone",
)
def hub_speaker_beep(hub: "PrimeHub" = hub):
    """Play a tone on the hub speaker."""
    hub.speaker.beep()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/hubs/beep",
    variant="Frequency",
)
def hub_speaker_beep_frequency(hub: "PrimeHub" = hub, frequency: "number[Hz]" = 500):
    """Play a tone on the hub speaker. Options: frequency."""
    hub.speaker.beep(frequency)


@inline_block(level="expert", icon="▶", color="action")
def hub_speaker_volume_volume(hub: "PrimeHub" = hub, volume: "number[%]" = 50):
    """Read or set the speaker volume. Options: volume."""
    hub.speaker.volume(volume)


@inline_block(level="expert", icon="▶", color="action")
def hub_speaker_volume(hub: "PrimeHub" = hub) -> "number[%]":
    """Read or set the speaker volume."""
    return hub.speaker.volume()


@inline_block(level="expert", icon="▶", color="action")
def hub_light_blink_color_durations(
    hub: "PrimeHub | TechnicHub | MoveHub | Remote" = hub,
    color: "Color" = Color.GREEN,
    durations=[200, 150],
):
    """Blink the status light with a list of on and off durations. Options: color, durations."""
    from pybricks.parameters import Color

    hub.light.blink(color, durations)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/hub_feedback/animate_light",
    variant="Frames and interval",
    bindings={"frames": "colors"},
    advanced=("interval",),
)
def hub_light_animate_frames_interval(
    hub: "PrimeHub | TechnicHub | MoveHub | Remote" = hub,
    frames=frames,
    interval: "number[ms]" = 100,
):
    """Animate the status light through a sequence of colors. Options: frames, interval."""
    hub.light.animate(frames, interval)


@inline_block(level="expert", icon="▶", color="action")
def hub_speaker_play_notes_notes_tempo(
    hub: "PrimeHub" = hub, notes=["C4/4"], tempo: "number" = 120
):
    """Play musical notes at a chosen tempo. Options: notes, tempo."""
    hub.speaker.play_notes(notes, tempo)


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    variant="Color sequence",
    advanced=("interval",),
)
def animate_light(
    hub: "PrimeHub | TechnicHub | MoveHub" = hub,
    colors=(Color.RED, Color.GREEN),
    interval: "number[ms]" = 100,
):
    """Cycle the status light through colors at a fixed interval."""
    from pybricks.parameters import Color

    hub.light.animate(colors, interval=interval)
