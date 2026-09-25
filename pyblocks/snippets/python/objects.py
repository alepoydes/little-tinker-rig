"""Classes and generators

Expert Python structure for reusable robot models and cooperative control."""

@inline_block(level="expert", icon="ƒ", color="definition", names=("Robot",))
def define_class():
    """Define a class for a robot or a shared state object.

    Add methods using the function block; their first parameter is self.
    Class bodies remain ordinary editable Python."""

    class Robot:
        pass


@inline_block(level="expert", icon="◇", color="control")
def use_context(manager=resource):
    """Enter a context and automatically run its cleanup when leaving.

    A robot context can stop motors even when an exception interrupts its body."""
    with manager:
        pass


@inline_block(level="expert", icon="◇", color="control", kind="statement")
def yield_value(value=None):
    """Yield a value from a generator, resuming here on its next iteration."""
    yield value


@inline_block(level="expert", icon="◇", color="control", kind="statement")
def yield_control():
    """Pause a generator without returning a value."""
    yield


@inline_block(level="expert", icon="＝", color="value")
def next_value(iterator=steps):
    """Advance a generator once; raises StopIteration at its end."""
    return next(iterator)


@inline_block(level="advanced", icon="＝", color="value")
def all_values(values=(True, True)) -> "bool":
    """Check that every value is true; stop at the first false value."""
    return all(values)


@inline_block(level="advanced", icon="＝", color="value")
def any_value(values=(False, True)) -> "bool":
    """Check whether any value is true; stop at the first true value."""
    return any(values)


@inline_block(level="expert", icon="＝", color="value")
def map_iterator(function=abs, values=(-1, 0, 1)):
    """Apply a function lazily as each item is consumed."""
    return map(function, values)


@inline_block(level="expert", icon="＝", color="value")
def zip_iterators(left=steps, right=times):
    """Advance two iterators together until the shorter one ends."""
    return zip(left, right)  # noqa: B905 - MicroPython has no strict keyword.


@inline_block(level="advanced", icon="＝", color="value")
def sum_items(values=(1, 2, 3)) -> "number":
    """Add all values from an iterable."""
    return sum(values)


@inline_block(level="advanced", icon="＝", color="value")
def reversed_items(values=(1, 2, 3)):
    """Iterate through a sequence in reverse order."""
    return reversed(values)


@inline_block(level="advanced", icon="＝", color="value")
def dictionary_items(mapping=lookup):
    """Iterate over dictionary keys and values together."""
    return mapping.items()


@inline_block(level="advanced", icon="＝", color="value")
def character_code(character="a") -> "int":
    """Read the numeric code of one character."""
    return ord(character)


@inline_block(level="expert", icon="＝", color="value")
def is_subclass(derived=ValueError, base=Exception) -> "bool":
    """Check an exception or class hierarchy."""
    return issubclass(derived, base)


@inline_block(level="expert", icon="＝", color="value")
def constant(value: "int" = 1) -> "int":
    """Declare a MicroPython integer constant."""
    from micropython import const

    return const(value)
