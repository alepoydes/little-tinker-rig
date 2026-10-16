"""Display options

Explicit device operations for studying complete robot programs."""

__category__ = "output"


@inline_block(level="expert", icon="▶", color="action")
def hub_display_orientation_up(hub: "PrimeHub" = hub, up: "Side" = Side.TOP):
    """Rotate the display for the way the hub is mounted. Options: up."""
    from pybricks.parameters import Side

    hub.display.orientation(up)


@inline_block(level="expert", icon="▶", color="action", advanced=("interval",))
def hub_display_animate_frames_interval(
    hub: "PrimeHub" = hub, frames=frames, interval: "number[ms]" = 100
):
    """Animate brightness frames at a fixed interval. Options: frames, interval."""
    hub.display.animate(frames, interval)


@inline_block(level="expert", icon="▶", color="action")
def hub_display_pixel_row_column_brightness(
    hub: "PrimeHub" = hub,
    row: "int" = 0,
    column: "int" = 0,
    brightness: "number[%]" = 100,
):
    """Set the brightness of one display pixel. Options: row, column, brightness."""
    hub.display.pixel(row, column, brightness)


@inline_block(level="expert", icon="▶", color="action")
def hub_display_char_character(hub: "PrimeHub" = hub, character: "str" = "!"):
    """Display a single character. Options: character."""
    hub.display.char(character)


@inline_block(level="expert", icon="▶", color="action", variant="Default timing")
def hub_display_text_text(hub: "PrimeHub" = hub, text: "str" = "Hello"):
    """Scroll text on the hub display."""
    hub.display.text(text)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/hub_display/hub_display_text_text",
    variant="Character timing",
    advanced=("on", "off"),
)
def hub_display_text_text_on_off(
    hub: "PrimeHub" = hub,
    text: "str" = "Hello",
    on: "number[ms]" = 500,
    off: "number[ms]" = 50,
):
    """Scroll text across the hub display. Options: text, on, off."""
    hub.display.text(text, on, off)
