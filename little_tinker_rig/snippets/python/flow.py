"""Iteration and exceptions

Control flow beyond counted loops and simple decisions."""

__category__ = "program"


@inline_block(
    level="intermediate", icon="◇", color="control", context="loop", title="Break loop"
)
def break_loop():
    """Leave the nearest loop.

    Insert inside a for or while loop, often inside an if condition."""
    while True:
        break


@inline_block(
    level="advanced", icon="⟳", color="loop", names=("name",), title="For each item"
)
def for_each(name=item, items=values):
    """Repeat actions for each item in a collection.

    The name takes each value in order. Replace pass with the actions to perform."""
    for name in items:
        pass


@inline_block(
    level="advanced", icon="◇", color="control", context="loop", title="Next iteration"
)
def continue_loop():
    """Skip to the next iteration of the nearest loop."""
    while True:
        continue


@inline_block(
    level="advanced", icon="＝", color="value", category="values", title="Choose value"
)
def choose_value(test: "bool" = True, yes=1, no=0):
    """Choose a value using a condition.

    Only the chosen expression is evaluated."""
    return yes if test else no


@inline_block(level="expert", icon="◇", color="control", title="Handle exception")
def handle_error(error_type=ValueError):
    """Handle a specific Python exception.

    Put the operation in try and recovery actions in except.
    Choose the exception you expect instead of hiding every error."""
    try:
        pass
    except error_type:
        pass


@inline_block(level="expert", icon="◇", color="control", title="Always clean up")
def cleanup():
    """Run cleanup even if an operation fails.

    Put actions in try and cleanup, such as stopping a motor, in finally.
    Forced program termination may prevent cleanup from running."""
    try:
        pass
    finally:
        pass


@inline_block(level="expert", icon="◇", color="control", title="Raise error")
def raise_error(message="Invalid value"):
    """Raise a ValueError with an explanation."""
    raise ValueError(message)


@inline_block(level="expert", icon="◇", color="control", title="Assert condition")
def check(test: "bool" = True, message="Check failed"):
    """Assert a condition while debugging.

    Use for program assumptions, not hardware protection or required validation."""
    assert test, message
