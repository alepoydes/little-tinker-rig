"""Keyboard input

Nonblocking input from the connected computer's terminal."""

__category__ = "input"


@inline_block(level="advanced", icon="⌨", color="value")
def input_byte(latest: "bool" = True, character: "bool" = True):
    """Read a byte or character without waiting; optionally discard older buffered input."""
    from pybricks.tools import read_input_byte

    return read_input_byte(latest, character)


@block(level="advanced", icon="⌨", color="value")
def read_key_code() -> "int | None":
    """Read one keyboard character code, or None when no key is available.

    Keep the hub connected and give its console keyboard focus. This is the
    nonblocking equivalent of the old experimental getchar API."""
    from uselect import poll
    from usys import stdin

    keyboard = poll()
    keyboard.register(stdin)
    if keyboard.poll(0):
        return ord(stdin.read(1))
    return None


@inline_block(level="expert", icon="⌨", color="value")
def input_poller():
    """Create a poll object for nonblocking terminal input."""
    from uselect import poll

    return poll()


@inline_block(level="expert", icon="⌨", color="action")
def watch_input(keyboard=keyboard):
    """Register standard input with a poll object."""
    from usys import stdin

    keyboard.register(stdin)


@inline_block(level="expert", icon="⌨", color="value")
def ready_input(keyboard=keyboard, timeout: "int[ms]" = 0):
    """Check for input; zero milliseconds returns immediately."""
    return keyboard.poll(timeout)


@inline_block(level="expert", icon="⌨", color="value")
def read_input(count: "int" = 1) -> "str":
    """Read characters after poll reports input ready."""
    from usys import stdin

    return stdin.read(count)
