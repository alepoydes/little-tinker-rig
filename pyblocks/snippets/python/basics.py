"""Small Python building blocks. Functions are static templates."""


def display(value="Hello!"):
    """Display a value in the console.

    The value can be quoted text, a number, or a variable name.
    Use the console to see what happens in your program."""
    print(value)


def assign(name=value, value=0):
    """Remember a value under a name.

    Write the name without quotes, for example speed or distance.
    Use this name in later blocks."""
    name = value


def repeat(count: "number" = 10):
    """Repeat actions a given number of times.

    Replace pass with blocks dragged into the loop.
    The counter i starts at zero."""
    for i in range(count):
        pass


def condition(test: "bool" = True):
    """Run actions when a condition is true."""
    if test:
        pass


def forever():
    """Repeat actions until the program stops.

    Add a wait to robot control loops so the hub has time for other work."""
    while True:
        pass


def compare(value: "number" = 0, threshold: "number" = 0) -> "bool":
    """Check whether a value is below a threshold."""
    return value < threshold


def condition_else(test: "bool" = True):
    """Choose between two actions using a condition."""
    if test:
        pass
    else:
        pass


def while_condition(test: "bool" = True):
    """Repeat actions while the condition is true."""
    while test:
        pass


def add_to(name=value, amount: "number" = 1):
    """Increase a variable value."""
    name += amount


def equal(left=0, right=0) -> "bool":
    """Check whether two values are equal."""
    return left == right


def both(left: "bool" = True, right: "bool" = True) -> "bool":
    """Check that both conditions are true."""
    return left and right


def either(left: "bool" = True, right: "bool" = False) -> "bool":
    """Check that at least one condition is true."""
    return left or right


def opposite(test: "bool" = True) -> "bool":
    """Negate a condition."""
    return not test
