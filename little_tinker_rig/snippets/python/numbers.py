"""Numbers

Useful operations beyond the editable arithmetic operator blocks."""

__category__ = "values"


@inline_block(level="advanced", icon="▶", color="action")
def absolute(value: "number" = -10) -> "number":
    """Take the absolute value of a number."""
    return abs(value)


@inline_block(level="advanced", icon="▶", color="action")
def rounded(value: "number" = 3.6) -> "number":
    """Round a number to the nearest integer."""
    return round(value)


@inline_block(
    level="advanced",
    icon="＝",
    color="value",
    family="python/basics/sum_values",
    variant="Remainder",
    bindings={"value": "left", "divisor": "right"},
)
def remainder(value: "number" = 10, divisor: "number" = 3) -> "number":
    """Find the remainder after division.

    Use value % 2 == 0 to test whether an integer is even. The divisor cannot be zero.
    """
    return value % divisor


@inline_block(level="advanced", icon="▶", color="action", variant="Minimum")
def minimum(left: "number" = 0, right: "number" = 100) -> "number":
    """Choose the smallest or largest value.

    Choose the smaller value."""
    return min(left, right)


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    family="python/numbers/minimum",
    variant="Maximum",
)
def maximum(left: "number" = 0, right: "number" = 100) -> "number":
    """Choose the larger value."""
    return max(left, right)
