# Authoring snippet libraries

A collection is a directory of Python modules plus `collection.toml`. Functions
are parsed as static templates; they are never imported or executed by the editor.
The function signature defines parameters/default expressions, the docstring is
help, and the body is the inserted source. A single return expression defines an
expression template. Imports are gathered into the managed import section.

```toml
[collection]
id = "my_robot"
version = "1.0.0"
```

```python
def move_for(motor: "Motor" = motor, speed: "deg/s" = 300, duration: "ms" = 500):
    """Run a motor for a time and brake it."""
    from pybricks.tools import wait

    motor.run(speed)
    wait(duration)
    motor.brake()
```

Defaults are source expressions. `motor=motor` is a placeholder reference, not
an object created by the template module; this file must not be executed. Provide
defaults so dragging requires no dialog. New declared names receive a free suffix
when needed; existing visible device names are suggested from typed parameters.
String annotations describe units or device types without changing numeric values.

Connect a library with `pyblocks --collection ./my_robot qt main.py`. A snippet's
identity is `collection/module/function`; current identities must be unique.
Recognition compares AST structure and binds parameter occurrences, not source
markers. Repeated parameters are substituted as repeated Python expressions;
an expression with side effects can therefore run more than once.

Locally defined names are renamed hygienically to avoid collisions. This uses
lexical scopes, not text substitution. Functions, comprehensions and shadowing
are distinguished. Unsupported patterns such as recursive templates, classes,
global/nonlocal declarations and variadic signatures are rejected explicitly.

Recognition favors specific algorithms over generic one-statement templates.
The editor can expand a recognized block for ordinary structural editing. Changes
that no longer match a template remain ordinary Python.

Historical versions live in directories referenced by manifest `[[history]]`
entries with `version` and `path`. Paths must remain inside the collection.
Historical forms are recognized alongside current forms; Ctrl+U updates a selected
old form while preserving compatible parameters. Incompatible signatures or a
major version change prevent automatic upgrades. Workspace `pins` can require an
installed collection version.

Managed imports are marked explicitly. Existing unmanaged imports remain user
code. References in ordinary code and Scratch keep managed dependencies alive.
Do not rely on comments or editor metadata as part of a template's identity.

Translate snippet docstrings through the same gettext catalog as the interface;
see [development](development.md#translations).

## Types and bundled blocks

An expression return annotation (`-> "bool"`, `-> "mm"`) gives its suggestion
type. Annotations are read statically. Numeric units belong to the numeric type;
no automatic unit conversion is performed. Known receiver types distinguish
`motor.brake()` from `drive.brake()`. Unknown dynamic values remain ordinary Python.

Bundled blocks cover motor creation and direction, speed, angle and timed moves,
motor readings; DriveBase; color, reflection, ultrasonic distance, force and BOOST
color/distance sensors; waits and stopwatches; variables, comparisons, logic and
loops. Ports are expressions such as `Port.A`, without quotes. A whole device
definition is recognized as one block. Scratch uses these templates without
adding imports.

BOOST distance is a relative percentage; ultrasonic distance uses millimeters.
See the [BOOST sensor API](https://docs.pybricks.com/en/latest/pupdevices/colordistancesensor.html)
and [UltrasonicSensor API](https://docs.pybricks.com/en/latest/pupdevices/ultrasonicsensor.html).


## Groups and reference pages

A module defines a group: `collection/motors.py` contributes `collection/motors`.
Use a separate module for each coherent topic. The library and help share these
groups; historical templates are excluded from the visible collection. Built-in
groups have translated captions, and additional collections keep their module
identity as the heading. All blocks in a group appear on one reference page.
English docstrings are the original descriptions; the interface catalog supplies
translations. F1 opens the selected block's stable section within its group.

## Difficulty levels

The collection manifest assigns each block one level. Unlisted blocks default
to `standard`; allowed levels are `beginner`, `standard`, and `expert`. Unknown
block identities and levels are rejected. `all` is only a library filter value.
Library cards and generated help use this same metadata. This is the level at
which a block is introduced: the filters are cumulative. Keep Beginner small;
follow the [learning paths](learning.md) when classifying new blocks.

```toml
[levels]
"motors/move_for" = "beginner"
```

A template annotated `-> "statement"` keeps its `return` as a statement instead of
turning it into an expression template. This supports the return block, which is
valid in a function body or as a detached Scratch fragment. A `-> "loop"` template
contains one `while` wrapper: only its body is inserted. This lets `break` and
`continue` templates remain compilable Python while insertion validates the
destination's loop context. Other return
annotations keep their existing expression/type meaning. Variable-length editing
comes from the expanded Python call, definition or Boolean expression; template
functions themselves still declare a fixed set of placeholders.

Parameter hints can list simple alternatives, such as
`"ColorSensor | ColorDistanceSensor"`. Recognition, name suggestions and method
result hints use the same alternatives without executing annotations. Use this
for operations shared by devices; keep distinct units separate (BOOST distance
is a percentage, ultrasonic distance is in millimeters).
