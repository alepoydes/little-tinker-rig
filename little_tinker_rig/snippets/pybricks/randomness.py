"""Random choices

Random choices supported by larger Pybricks hubs."""

__category__ = "values"


@inline_block(level="intermediate", icon="▶", color="action")
def random_integer(low: "number" = 1, high: "number" = 6) -> "number":
    """Choose a random integer, including both limits.

    Supported on Inventor, SPIKE Prime and Technic hubs.
    BOOST Move Hub firmware does not include urandom."""
    from urandom import randint

    return randint(low, high)


@inline_block(level="intermediate", icon="▶", color="value")
def random_item(items=("left", "right")):
    """Choose a random item from a nonempty sequence.

    Available on Inventor, SPIKE Prime and Technic hubs; not on BOOST."""
    from urandom import choice

    return choice(items)
