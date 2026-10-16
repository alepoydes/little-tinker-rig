# Authoring block libraries

Use the [Block Editor](block-editor.md) to inspect built-ins, edit user definitions,
and preview a block above its source. Definitions are parsed statically: decorators,
defaults, imports and function bodies are never executed by the editor.

## Collections and groups

A collection contains Python modules and this `collection.toml`:

```toml
[collection]
id = "my_robot"
version = "1.0.0"
format = 2
```

The manifest contains collection information and optional `[[history]]` entries
with `version` and `path`. Each module defines a help group. Its docstring supplies the
group title and description; each decorated function supplies a block. A block's
identity is `collection/module/function`. Ordinary undecorated functions are
helpers and do not appear in the library. Without catalog metadata, a module also
provides its own category heading. `__category__ = "movement"`, for example, places
its cards in Motors and movement; a decorator can override this with `category`.
Related forms can name a primary identity with `family` and a translatable
`variant` label. Keep every source form as a separate ordinary Python definition.

Connect a collection with `little-tinker-rig --collection ./my_robot qt main.py`.
Historical directories must stay inside the collection. Historical definitions
remain recognizable, and explicit upgrades preserve compatible parameters and
names. A major version change requires manual review.

## Starting a collection version

Before changing a published collection, archive its saved definitions and advance
the version with **Start next version…** in Block Editor or:

```sh
uv run little-tinker-rig next-block-version ./my_blocks 1.1.0
```

The same command works for built-in collections in `little_tinker_rig/snippets/` during
release development. Versions use `MAJOR.MINOR.PATCH`. The command validates a
staged collection, archives current Python modules and `snapshot.toml` under
`history/<previous-version>/`, then updates `collection.toml`. Existing archives
are not overwritten. Drafts must be saved or discarded first. Both wheel and source
distributions include historical definitions. An unregistered history directory
is never loaded as an active module.

Historical templates support explicit upgrades with preserved bindings, declaration
names and comments. Changes to parameter types/units, result/declaration contracts
or major versions require manual editing. Semantic compatibility is the author's
responsibility; equal signatures alone do not prove equivalent behavior. Functions
keep their authored names and one saved implementation. An explicit function
upgrade changes that shared implementation for every call; changed call signatures
require manual editing. Reloading a library alone never upgrades saved code.

## Two insertion modes

```python
"""Motors

Connect motors and control their movement.
"""

@inline_block(level="beginner", icon="⚙", color="state", names=("motor",))
def create_motor(port: "Port" = Port.A):
    """Connect a motor to a hub port."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import Motor

    motor: "Motor" = Motor(port)

@block(level="intermediate", icon="↻", color="action")
def move_for(motor: "Motor" = motor,
             speed: "number[deg/s]" = 300,
             duration: "int[ms]" = 500):
    """Run a motor for a time and brake it."""
    from pybricks.tools import wait

    motor.run(speed)
    wait(duration)
    motor.brake()
```

`@inline_block` inserts its body. A single `return expression` defines an
expression block. Inline variables live in the destination scope; hygienic
renaming prevents capture and collisions. Repeated parameter occurrences repeat
the supplied expression, including any side effects.

`@block` inserts a call to an automatically managed ordinary function. Arguments
are evaluated once per call and local variables remain inside the function.
A function with a returned value supplies an expression block; an action supplies
a statement block. The choice of mode is explicit: the editor never silently
replaces inline code with a function call.

Decorators belong only to library definitions. Programs sent to a hub contain
ordinary Python, imports and helper functions, without LittleTinker Rig decorators or a
LittleTinker Rig runtime dependency.

## Properties in the source

| Property | Meaning |
|---|---|
| `level` | Introduction level: `beginner`, `intermediate`, `advanced`, `expert`; default `intermediate` |
| `icon` | A nonempty symbol or short text; default `▶` |
| `color` | A palette role or `#RRGGBB`; default `snippet` |
| `names` | Renameable declarations in an inline block; default empty |
| `kind` | Optional `statement` or `expression` override |
| `context` | Optional `loop` or `async` wrapper for context-dependent inline statements |
| `category` | Subject branch; inherits module `__category__`, otherwise uses the module heading |
| `family` | Complete primary identity, such as `my_blocks/motors/turn`; empty for a separate primary card |
| `variant` | Translatable form label; a family member without a label is a recognition/lesson compatibility alias |
| `advanced` | Tuple of optional parameter names to place under Additional settings |
| `bindings` | Mapping from parameter names to shared family field keys; omitted names keep their own keys |

Palette roles are `control`, `loop`, `action`, `value`, `state`, `definition`,
`placeholder`, `snippet`, and `warning`. Metadata values must be literals.
`all` is a cumulative library filter, not a block level. The source defines the
appearance for the card, inserted block, preview and generated reference page.

The signature supplies expression fields and defaults. Defaults such as
`motor=motor` are caller expressions, not objects created by loading the library.
Provide defaults to allow insertion without a dialog. A docstring supplies help
and search text. English is the source language; gettext provides translations
for descriptions and group documentation.

Family members must have compatible statement/expression and context requirements
and point directly to a primary in the same collection; chains are rejected.
Each form keeps its own signature, level, body and identity. Category moves and
translations do not change saved programs or personal links. Values transfer
between compatible shared fields only during an explicit variant edit. Optional
omission remains distinct from passing `None` or evaluating a default.
Use [Catalog properties in Block Editor](block-editor.md#save-recover-and-share)
to edit these literal fields with preview and text Undo.

## Types and units

Annotations are strings with a type and an optional numeric unit:

| Annotation | Contract |
|---|---|
| `"Motor"` | A motor object |
| `"int"` | An integer, excluding Boolean values |
| `"number[deg/s]"` | A numeric angular speed |
| `"int[ms]"` | An integer duration in milliseconds |
| `"Motor | DriveBase"` | Either supported object type |

Numeric types are `int`, `float`, and `number`. Units are `deg`, `deg/s`, `deg/s²`,
`mm`, `mm/s`, `ms`, `s`, `%`, `N`, and `Hz`. Values on the hub remain ordinary
numbers; there is no automatic unit conversion.

Annotate input parameters in the signature. Use `-> "number[mm]"`, for example,
only for a returned value. An action may omit the return annotation or use
`-> "None"`. Annotate created variables in the body, as in `motor: "Motor"` above.
Existing unannotated assignments can still match the same declaration block.

Static checks distinguish compatible, incompatible and unknown values. Obvious
wrong types or units produce a red diagnostic; unknown dynamic values remain
usable. A bare numeric literal adopts the field's unit. Types, suggestions, drag
compatibility and diagnostics share the same contracts. This is conservative
analysis, not a complete Python type checker or physical-units algebra.

## Public fields and names

Only signature fields and explicitly published declarations are editable inside
a recognized block. `names=("motor",)` allows the created variable to be renamed,
including its resolved uses in surrounding code. Nested declarations use lexical
paths, such as `names=("action", "action.value")` for a function and its parameter.
A signature parameter used as a declaration target can also be listed in `names`.
Renames check scope collisions and accidental capture.

Methods, operators, constants and private names stay fixed unless they occur
inside a public expression. Public expression lists can be edited structurally.
Expand a block or edit Python to change its implementation. If the result no
longer matches, it becomes ordinary Python and loses the old block description.

## Dependencies and helpers

Imports may be module-level or inside an inline template. Required global imports
are gathered into the managed import header; user imports remain untouched.
Function-local imports in generated helpers retain their normal Python scope.

Undecorated functions in the same module can be shared by several blocks. The
editor includes their reachable dependencies once in the managed helper section
after imports, retaining the original function names. Different definitions with
the same name require an explicit rename; they are never silently substituted.
Removing the last use removes unused helpers and imports. References in ordinary
code and Scratch count too, including unfinished Scratch text. Undo restores the
source and dependencies together. Existing generated implementations are retained
when a library changes; applying definitions does not rewrite open programs.

Block modules contain a docstring, imports and function definitions. Block
signatures have fixed parameters; inline bodies cannot use recursive templates,
nonempty classes, or `global`/`nonlocal`. An isolated empty class skeleton is allowed;
its published name can be edited and its body filled with ordinary Python blocks. These restrictions keep substitution explicit.
Ordinary helper functions retain ordinary Python signatures and local scopes.
Calling a decorated block from helper code requires all its fields explicitly:
block defaults fill the editor's insertion fields, not a runtime function signature.
Use an undecorated helper when ordinary Python default arguments are needed.

## Control statements

Use `kind="statement"` to retain `return` as a statement:

```python
@inline_block(kind="statement", level="intermediate", icon="↩", color="control")
def return_value(value=0):
    """Return a result."""
    return value
```

For `await`, use `context="async"` and one `async def` wrapper. Only its body
is inserted; Python rejects insertion outside an async function. The bundled
**Cooperative tasks** group includes the definition, await and run-task blocks.

For `break` and `continue`, use `context="loop"` and one `while` wrapper. Only its
body is inserted. The wrapper makes the definition valid Python; insertion still
checks that the destination is inside a loop. Context and insertion kind are not
encoded in the return type.

## Migrating older collections

Older undecorated templates and manifest `[levels]` remain readable. Migrate a
collection explicitly with:

```sh
little-tinker-rig migrate-blocks ./my_robot
little-tinker-rig migrate-blocks ./my_robot --write
```

The first command prints a diff. The second applies the validated conversion,
retaining inline algorithms, levels and historical versions. Existing programs
are unchanged. The Block Editor also converts an opened legacy module into a
source draft and removes its obsolete level entries when that draft is saved.
