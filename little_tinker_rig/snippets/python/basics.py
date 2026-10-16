"""Python basics

Small Python building blocks. Functions are static templates."""

__category__ = "program"


@inline_block(level="beginner", icon="▶", color="action")
def display(value="Hello!"):
    """Display a value in the console.

    The value can be quoted text, a number, or a variable name.
    Use the console to see what happens in your program."""
    print(value)


@inline_block(
    level="intermediate", icon="▣", color="state", names=("name",), category="data"
)
def assign(name=value, value=0):
    """Remember a value under a name.

    Write the name without quotes, for example speed or distance.
    Use this name in later blocks."""
    name = value


@inline_block(
    level="beginner",
    icon="⟳",
    color="loop",
    names=("i",),
    variant="Count",
    bindings={"count": "stop"},
)
def repeat(count: "number" = 10):
    """Repeat actions a given number of times.

    Replace pass with blocks dragged into the loop.
    The counter i starts at zero."""
    for i in range(count):
        pass


@inline_block(level="intermediate", icon="◇", color="control", variant="If")
def condition(test: "bool" = True):
    """Run actions when a condition is true."""
    if test:
        pass


@inline_block(
    level="intermediate",
    icon="⟳",
    color="loop",
    family="python/basics/while_condition",
    variant="Forever",
)
def forever():
    """Repeat actions until the program stops.

    Add a wait to robot control loops so the hub has time for other work."""
    while True:
        pass


@inline_block(
    level="intermediate",
    icon="＝",
    color="value",
    category="values",
    variant="Less than",
    bindings={"value": "left", "threshold": "right"},
)
def compare(value: "number" = 0, threshold: "number" = 0) -> "bool":
    """Check whether a value is below a threshold."""
    return value < threshold


@inline_block(
    level="intermediate",
    icon="◇",
    color="control",
    family="python/basics/condition",
    variant="If / else",
)
def condition_else(test: "bool" = True):
    """Choose between two actions using a condition."""
    if test:
        pass
    else:
        pass


@inline_block(
    level="intermediate", icon="⟳", color="loop", variant="While a condition holds"
)
def while_condition(test: "bool" = True):
    """Repeat actions while the condition is true."""
    while test:
        pass


@inline_block(
    level="intermediate", icon="▣", color="state", names=("name",), category="data"
)
def add_to(name=value, amount: "number" = 1):
    """Increase a variable value."""
    name += amount


@inline_block(
    level="intermediate",
    icon="＝",
    color="value",
    category="values",
    family="python/basics/compare",
    variant="Equal to",
)
def equal(left=0, right=0) -> "bool":
    """Check whether two values are equal."""
    return left == right


@inline_block(
    level="intermediate", icon="＝", color="value", category="values", variant="And"
)
def both(left: "bool" = True, right: "bool" = True) -> "bool":
    """Check that both conditions are true."""
    return left and right


@inline_block(
    level="intermediate",
    icon="＝",
    color="value",
    category="values",
    family="python/basics/both",
    variant="Or",
)
def either(left: "bool" = True, right: "bool" = False) -> "bool":
    """Check that at least one condition is true."""
    return left or right


@inline_block(level="intermediate", icon="＝", color="value", category="values")
def opposite(test: "bool" = True) -> "bool":
    """Negate a condition."""
    return not test


@inline_block(
    level="intermediate",
    icon="⟳",
    color="loop",
    names=("i",),
    family="python/basics/repeat",
    variant="Start, stop and step",
)
def count_range(start: "number" = 0, stop: "number" = 10, step: "number" = 1):
    """Repeat over a range with a start, exclusive stop and step.

    The stop is not included. The step must not be zero."""
    for i in range(start, stop, step):
        pass


@inline_block(
    level="intermediate",
    icon="ƒ",
    color="definition",
    names=("action",),
    category="functions",
)
def define_function():
    """Define your own function.

    Edit its name and add parameters. Drag actions into its body."""

    def action():
        pass


@inline_block(level="intermediate", icon="▶", color="action", category="functions")
def call_function(function=action):
    """Call a function.

    Choose a function and add or remove its arguments."""
    function()


@inline_block(
    level="intermediate",
    icon="◇",
    color="control",
    kind="statement",
    category="functions",
)
def return_value(value=0):
    """Return a value from the current function."""
    return value


@inline_block(
    level="intermediate", icon="＝", color="value", category="values", variant="Add"
)
def sum_values(left=0, right=0):
    """Add two values."""
    return left + right


@inline_block(
    level="intermediate",
    icon="＝",
    color="value",
    category="values",
    family="python/basics/sum_values",
    variant="Subtract",
)
def difference(left=0, right=0):
    """Subtract one value from another."""
    return left - right


@inline_block(
    level="intermediate",
    icon="＝",
    color="value",
    category="values",
    family="python/basics/sum_values",
    variant="Multiply",
)
def product(left=1, right=1):
    """Multiply two values."""
    return left * right


@inline_block(
    level="intermediate",
    icon="＝",
    color="value",
    category="values",
    family="python/basics/sum_values",
    variant="Divide",
)
def quotient(left=1, right=1):
    """Divide one value by another."""
    return left / right


@inline_block(level="advanced", icon="ƒ", color="value", category="functions")
def call_value(function=action):
    """Call a function or class and use its result.

    Choose the callable and edit its argument list. This also creates an instance
    of a custom robot class or calls a method that returns a value."""
    return function()
