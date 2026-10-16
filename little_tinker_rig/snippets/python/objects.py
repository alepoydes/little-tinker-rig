"""Classes and generators

Expert Python structure for reusable robot models and cooperative control."""

__category__ = "data"


@inline_block(
    level="expert",
    icon="ƒ",
    color="definition",
    names=("Robot",),
    category="functions",
    title="Define class",
)
def define_class():
    """Define a class for a robot or a shared state object.

    Add methods using the function block; their first parameter is self.
    Class bodies remain ordinary editable Python."""

    class Robot:
        pass


@inline_block(
    level="expert",
    icon="◇",
    color="control",
    category="program",
    variant="Unnamed resource",
    title="Use context",
)
def use_context(manager=resource):
    """Enter a context and automatically run its cleanup when leaving.

    A robot context can stop motors even when an exception interrupts its body."""
    with manager:
        pass


@inline_block(
    level="expert",
    icon="◇",
    color="control",
    names=("name",),
    category="program",
    family="python/objects/use_context",
    variant="Named resource",
    title="Use context",
)
def use_named_context(manager=resource, name=robot):
    """Enter a context, name its resource, and clean up when leaving."""
    with manager as name:
        pass


@inline_block(
    level="expert",
    icon="◇",
    color="control",
    kind="statement",
    category="functions",
    variant="Yield a value",
    title="Yield value",
)
def yield_value(value=None):
    """Pause and resume a generator.

    Yield a value from a generator, resuming here on its next iteration."""
    yield value


@inline_block(
    level="expert",
    icon="◇",
    color="control",
    kind="statement",
    category="functions",
    family="python/objects/yield_value",
    variant="Yield without a value",
    title="Yield value",
)
def yield_control():
    """Pause a generator without returning a value."""
    yield


@inline_block(level="expert", icon="＝", color="value", title="Next value")
def next_value(iterator=steps):
    """Advance a generator once; raises StopIteration at its end."""
    return next(iterator)


@inline_block(
    level="advanced",
    icon="＝",
    color="value",
    variant="All values",
    title="All / any values",
)
def all_values(values=(True, True)) -> "bool":
    """Test values in a collection.

    Check that every value is true; stop at the first false value."""
    return all(values)


@inline_block(
    level="advanced",
    icon="＝",
    color="value",
    family="python/objects/all_values",
    variant="Any value",
    title="All / any values",
)
def any_value(values=(False, True)) -> "bool":
    """Check whether any value is true; stop at the first true value."""
    return any(values)


@inline_block(level="expert", icon="＝", color="value", title="Map iterator")
def map_iterator(function=abs, values=(-1, 0, 1)):
    """Apply a function lazily as each item is consumed."""
    return map(function, values)


@inline_block(level="expert", icon="＝", color="value", title="Zip iterators")
def zip_iterators(left=steps, right=times):
    """Advance two iterators together until the shorter one ends."""
    return zip(left, right)  # noqa: B905 - MicroPython has no strict keyword.


@inline_block(level="advanced", icon="＝", color="value", title="Sum items")
def sum_items(values=(1, 2, 3)) -> "number":
    """Add all values from an iterable."""
    return sum(values)


@inline_block(level="advanced", icon="＝", color="value", title="Reverse iteration")
def reversed_items(values=(1, 2, 3)):
    """Iterate through a sequence in reverse order."""
    return reversed(values)


@inline_block(level="advanced", icon="＝", color="value", title="Dictionary entries")
def dictionary_items(mapping=lookup):
    """Iterate over dictionary keys and values together."""
    return mapping.items()


@inline_block(
    level="advanced",
    icon="＝",
    color="value",
    category="values",
    title="Character code",
)
def character_code(character="a") -> "int":
    """Read the numeric code of one character."""
    return ord(character)


@inline_block(
    level="expert",
    icon="＝",
    color="value",
    category="functions",
    title="Check subclass",
)
def is_subclass(derived=ValueError, base=Exception) -> "bool":
    """Check an exception or class hierarchy."""
    return issubclass(derived, base)


@inline_block(
    level="expert",
    icon="＝",
    color="value",
    category="values",
    title="Integer constant",
)
def constant(value: "int" = 1) -> "int":
    """Declare a MicroPython integer constant."""
    from micropython import const

    return const(value)
