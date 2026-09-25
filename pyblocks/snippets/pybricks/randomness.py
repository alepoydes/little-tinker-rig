"""Random choices

Random choices supported by larger Pybricks hubs."""

@inline_block(level="intermediate", icon="▶", color="action")
def random_integer(low: "number" = 1, high: "number" = 6) -> "number":
    """Choose a random integer, including both limits.

    Supported on Inventor, SPIKE Prime and Technic hubs.
    BOOST Move Hub firmware does not include urandom."""
    from urandom import randint

    return randint(low, high)
