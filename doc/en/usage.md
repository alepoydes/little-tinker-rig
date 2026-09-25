# Editing and command-line tools

## Documents and views

Files have independent tabs, drafts and undo histories. The hub connection and
console belong to the window. Run always saves and runs the active document.
Use the two document icons or **View → Blocks / Python** to change the editor mode.
Global workspaces use narrow rotated labels and neutral active indicators.
**Block Editor** (**Ctrl+Alt+3**) edits template definitions with a preview above
the source; see [its guide](block-editor.md).

The Python editor has syntax highlighting, line numbers, indentation with
Tab/Shift+Tab, word completion with Ctrl+Space, and search with Ctrl+F. Ruff
formats committed edits. Invalid drafts never replace the committed document
or file; a file containing invalid Python opens as a text draft.

In Blocks, clicking a parameter opens a text field over its source value.
When alternatives exist, an arrow opens a list below the field; otherwise the
input has no arrow. Declaration names are plain editable text. The editable field
exists only while editing; the parameter name is a
tooltip, and a read-only suffix shows its unit. Suggestions respect known types:
conditions offer booleans and button readings, motor fields offer motor variables.
Repeated occurrences change together. Enter or choosing an item applies; Escape
dismisses. A structural selection uses the whole block background, including the
remaining line width.

Scratch is visible by default and can be resized or closed with its dock controls.
The bottom Scratch button restores it. Control mode hides Scratch. The title bar
always shows minimize, maximize/restore, and close. Double-click it to toggle
maximization; drag it or a window edge to move or resize. F11 toggles full screen.

Descriptions above blocks and symbols before the comment text explain their purpose without
adding comments to the Python file. Indentation colors continue through blank
lines. A motor definition is one block with the same color as its library card.

## Structural navigation

| Action | Qt | TUI |
| --- | --- | --- |
| Parent / child | Alt+Left / Right | Alt+Left / Right |
| Previous / next node | Alt+Up / Down | Alt+Up / Down |
| Edit Python fragment | F2 | F2 |
| Parameters | F3 | F3 |
| Expand recognized snippet | Ctrl+E | Ctrl+E |
| Start move | Ctrl+M | Ctrl+M |
| Previous / next destination | Alt+Up / Down | Alt+Up / Down |
| Outdent / indent destination | Ctrl+Alt+Left / Right | Alt+Left / Right |
| Commit / cancel move | Ctrl+Enter / Esc | Ctrl+Enter / Esc |
| Fold region | Ctrl+Shift+F | Ctrl+F |
| Upgrade old snippet | Ctrl+U | Ctrl+U |

Dragging a block attaches a colored preview of at most four displayed lines to the
pointer. The source is temporarily replaced by an amber **Previous position** row;
an expression leaves this marker in its original parameter. Escape cancels, even
while the mouse button remains held. Returning to the amber row changes nothing.

Hover the upper half of a source row to insert above it, or the lower half to
insert below it. Below a loop or `if` header means the beginning of its body. To
insert after a compound block, hover the next outside block or a following blank
line; horizontal position selects nesting on blank lines. A green **Insert here**
row opens space before the destination's descriptions. Its appearance keeps the
same source row and relative point under the pointer. Edges scroll the view;
dragging does not fold code automatically.

Only an empty parameter (`None`) accepts a compatible expression. Populated
parameters are not replaced by a drop. Invalid contexts offer no insertion and
release restores the source. Library blocks use defaults and known device names.
A successful transfer commits once; Undo restores both program and Scratch.
Attached Python comments move with the block. Syntax validity does not prove that
a moved program still has the intended meaning.

## Library, Scratch and help

Search the library by name, category or description. The level filter combines
with search: **Beginner**, **Intermediate**, **Advanced**, **Expert**, or **All**.
Each level includes the preceding levels. Groups start collapsed above Beginner
and search opens matching groups. All is
only a filter choice. A fresh installation starts with Beginner; the selected
level is remembered. See the [learning paths](learning.md). Cards use the same semantic
color as inserted blocks. Hover shows the full preview. F1 opens the selected
block's section on its group page or the guide. Help includes offline Markdown and snippet
parameters/source, with search, internal links and Back.

Scratch is a vertical ribbon of independent editable fragments. Drag blocks from
the program or library into the ribbon. The ⠿ handle moves a whole cell; a block
inside it can also be detached individually. Drop between cells to reorder, inside
a cell to combine, or onto a program boundary to restore. Library dependencies
are imported only when the fragment enters the program. One undo restores both
areas after a transfer.

Each cell has Blocks / Python icons. Python accepts arbitrary unfinished text;
parseable fragments can be edited structurally without a complete execution
context. For example, a detached `break` is allowed in Scratch but can only return
inside a loop. Invalid drops preserve both areas. In TUI select Scratch with Tab,
use F2 to edit, Ctrl+N to create, and Ctrl+R to restore.

**View → Name diagnostics** lists unknown names. This lexical analysis does not
infer every execution path or inspect third-party runtime objects.

## CLI

Coordinates refer to the formatted source returned by `inspect`: lines start at
1, columns at 0 and count Unicode characters. Transformations print their result;
only `--write` saves it.

```sh
uv run pyblocks inspect examples/courier.py
uv run pyblocks diagnose examples/courier.py
uv run pyblocks snippets main.py
uv run pyblocks insert main.py python/basics/display --param 'value="Hello"'
uv run pyblocks replace main.py '4 + 5' --at 1:4
uv run pyblocks move main.py --at 2:0 --to 7:0
uv run pyblocks scratch main.py --at 2:0 --write
uv run pyblocks restore main.py 0 --at 1:0 --write
uv run pyblocks format main.py --write
```

`diagnose` exits with 1 for warnings and 0 otherwise. Input/transformation errors
exit with 2. `pyblocks --help` lists commands. Add a collection with
`pyblocks --collection ./my_snippets qt main.py`; saving remembers its path.
See [authoring snippets](snippets.md) and [robot control](robotics.md).

![Multiple documents, inline parameters and the English interface](images/editor.png)

![Offline guide and block reference](images/help.png)

![Previewing an insertion from the library](images/drop-preview.png)

## Recent files and block descriptions

**File → Open recent** lists the ten most recently opened or saved files. Opening
a file already in a tab selects that tab and preserves its unfinished draft.
Missing files remain visible but disabled. **Clear recent files** clears the list.

A block description occupies a separate row in its own semantic color. Nested
expression blocks have their own description rows. The insertion marker appears
before the target block's descriptions and any attached Python comments.

Parameter editing (F3), To Scratch and Python fragment (F2) remain in the menus;
the toolbar focuses on files, history and hub actions.

## Expressions and your own functions

Edit the receiver, callable name, operands and operators directly in the source.
For example, `left.run(speed + 10)` has separate editable values. Click an operator
to choose another; operand grouping is preserved. Right-click an expression to
edit it as Python, clear it to `None`, or wrap it in a logical, arithmetic or
comparison expression. Drag compatible blocks into the resulting empty fields.

Click inside a call, function header or logical expression to show its compact
list controls. Select the list when several are nested. **+** inserts after the
selected item, or appends when no item is selected; its menu also inserts before
an item. **−** removes an item, and the arrows reorder it. Calls and definitions
may have no arguments; `and` and `or` retain at least two operands. Parameters may
include annotations, defaults and Python's `/`, `*`, `*args` and `**kwargs` forms.
Edits that violate Python syntax leave the document unchanged. Each accepted
operation is one Undo step.

Use **Define your own function** to create a definition, then edit its name and
parameters and insert actions into its body. Module-level functions appear in
**My functions** in the library. Their calls initially include required
parameters as `None`; optional parameters use the function’s own defaults. Add
optional arguments explicitly when needed. Renaming a function or parameter
updates statically resolved references and known keyword calls. Conflicting or
capturing renames are rejected. Changing a signature keeps existing calls visible.
A known incompatible call receives a red border and an error comment; uncertain
dynamic calls are not reported as signature errors. The program remains editable.
Use **Return a value** inside a function.

The Beginner repeat block exposes its counter and repeat count. The Intermediate
range block exposes the counter, start, exclusive stop and step. Expand a template
to edit its fixed Python parts. A zero range step is reported as an error.

Search matches all entered words across the name, source, group and complete
localized help text, regardless of word order. Comment rows start with `#`, followed
by the enlarged block symbol and description, without additional line spacing.
They share the block's background, hover and selection, including ancestor bands.

![Function parameters, logical operands and a known call error](images/functions.png)
