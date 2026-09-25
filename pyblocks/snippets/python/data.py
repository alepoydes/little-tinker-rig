"""Lists, text and dictionaries

Lists, strings and mappings as ordinary Python data."""

@inline_block(level="advanced", icon="▣", color="state", names=("name",))
def make_list(name=values, items=(10, 20, 30)):
    """Create a list of values.

    Edit the comma-separated items in Python or replace the items expression.
    Use append to grow the list one value at a time."""
    name: "list" = list(items)


@inline_block(level="advanced", icon="▶", color="action")
def append(items: "list" = values, value=0):
    """Append a value to a list."""
    items.append(value)


@inline_block(level="advanced", icon="＝", color="value")
def item(items=values, index=0):
    """Read an item by index or key.

    List indices start at zero; -1 is the last item.
    For a dictionary, use a key instead of a numeric index."""
    return items[index]


@inline_block(level="advanced", icon="▣", color="state")
def set_item(items=values, index=0, value=0):
    """Replace an item by index or key.

    A list index must already exist. A dictionary key may be new."""
    items[index] = value


@inline_block(level="advanced", icon="▶", color="action")
def length(items=values) -> "number":
    """Count the items in a collection or text."""
    return len(items)


@inline_block(level="intermediate", icon="▶", color="action")
def text(value=0) -> "str":
    """Convert a value to text."""
    return str(value)


@inline_block(level="advanced", icon="▣", color="state", names=("name",))
def make_dictionary(name=lookup, key="name", value="robot"):
    """Create a dictionary with a key and value.

    Add entries with the item-assignment block, or edit the dictionary in Python."""
    name = {key: value}


@inline_block(level="advanced", icon="＝", color="value")
def slice_items(items=values, start: "number" = 0, stop: "number" = 2):
    """Take a slice of a sequence.

    The start is included and the stop is excluded. The original is unchanged."""
    return items[start:stop]


@inline_block(level="advanced", icon="＝", color="value")
def contains(value=0, items=values) -> "bool":
    """Check whether a collection contains a value.

    For dictionaries, this checks keys. For text, it checks substrings."""
    return value in items


@inline_block(level="advanced", icon="＝", color="value")
def map_values(function=abs, items=(-1, 0, 1)) -> "list":
    """Build a list by applying a function to every item.

    Choose a built-in or your own function. Edit the comprehension in Python
    when you need filtering or a more complex expression."""
    return [function(item) for item in items]
