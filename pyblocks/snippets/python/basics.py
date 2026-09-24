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


def count_range(start: "number" = 0, stop: "number" = 10, step: "number" = 1):
    """Repeat over a range with a start, exclusive stop and step.

    The stop is not included. The step must not be zero."""
    for i in range(start, stop, step):
        pass


def define_function():
    """Define your own function.

    Edit its name and add parameters. Drag actions into its body."""

    def action():
        pass


def call_function(function=action):
    """Call a function.

    Choose a function and add or remove its arguments."""
    function()


def return_value(value=0) -> "statement":
    """Return a value from the current function."""
    return value


def sum_values(left=0, right=0):
    """Add two values."""
    return left + right


def difference(left=0, right=0):
    """Subtract one value from another."""
    return left - right


def product(left=1, right=1):
    """Multiply two values."""
    return left * right


def quotient(left=1, right=1):
    """Divide one value by another."""
    return left / right
