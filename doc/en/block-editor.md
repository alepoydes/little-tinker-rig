# Block Editor

Open **Block Editor** in the workspace rail, or press **Ctrl+Alt+3**. The library's
context menu and each block's help section also offer **Open definition**.
Definitions are ordinary Python function templates, edited as text. The editor
parses them; it never executes their defaults, imports, or bodies.

## Inspect and create

Collections, modules and blocks appear on the left. Search includes descriptions.
Built-in definitions are read-only examples. **Copy to my collection** copies the
selected function, including its decorators, imports and reachable helper functions.
The copy has its own identity; it does not replace the built-in block.

Choose a **Group / module**, such as `custom` or `robots/motors`, and a starter:
**Action**, **Expression**, or **Multi-command action**. **New block** adds a
function to that module. Copies use the same group field. Name collisions receive
a numeric suffix. Functions in one module form one library group and one help
page. Edit the function name, signature, docstring and body directly in Python.

In the program, **Edit → Create block from selection** starts a definition from
the selected structural block or selected Python text. The program stays intact.
Declare parameters explicitly in the new signature and use them in its body;
this action does not guess which constants should become parameters.

## Preview above the source

The preview uses the same renderer as the program, initially showing at most four
source lines. **Expand preview** reveals the rest. Drag the horizontal splitter
to resize the preview and source editor. Typing does not resize these areas.
**In the library** switches to the actual library card.

Moving the cursor into a decorated function selects its block. Ordinary helpers and blank lines between functions
retain the previous selection. Click a parameter in the program preview to jump
to its declaration and highlight its uses; click the description to reach the
docstring. Public declaration fields jump to their declarations too. Decorator,
signature, parameter and annotation highlighting and context hints
explain the definition's structure. **Ctrl+Space** completes names from the module.

**Test values** substitutes Python expressions only in the program preview.
It does not change definition defaults or execute these expressions. The library
card continues to show the defaults readers will get on insertion. **Reset test
values** restores the defaults. Invalid source or test expressions keep the last
valid preview and show an error; click a source error to jump to its line.

## Save, recover and share

**Save and apply**, or **Ctrl+S**, validates the module and collection, then updates
the working library and help. The level, icon and color controls edit literal
properties in the decorator. These are ordinary text edits with normal Undo;
there is no separate copy of block metadata. Descriptions, defaults, type contracts
and public names stay in the same Python source. Imports may be module-level or
inside functions, and undecorated helpers may be shared by several blocks.
A placeholder default such as `motor=motor` is valid here; it is not evaluated.
See [the template format](snippets.md) for supported Python patterns.

Edits are retained as drafts after a short pause, including invalid Python, and
recovered on reopening the module. Switching modules preserves their text undo
histories during the session. **Reopen saved** discards the current module draft
with confirmation. Invalid drafts never replace the active library. External
changes to the same module or collection settings prevent an accidental overwrite.
Legacy modules are converted into a source draft; obsolete manifest levels are
removed only when that draft is saved.

The default user collection lives in `blocks/` beside the program; its relative
connection is stored in the program's `.pyblocks.json` workspace. Copy that
workspace and the collection with the program to another computer. Drafts are
stored in `blocks/.drafts/` as JSON, outside the active Python library. They are
only needed when continuing unfinished definition edits.

Saving definitions never rewrites open programs or Scratch, commits their Python
drafts, or changes their undo history. Recognition uses the new definitions;
old source that no longer matches remains ordinary Python. Program changes and
version upgrades are separate, explicit actions. Hub upload/run is unavailable
while editing definitions.

Right-click an inserted block and choose **Open definition** to navigate directly
here. A recognized historical block opens its original file and version read-only,
not the current implementation with the same identity. Copy it to a user collection
to make an editable variant.
