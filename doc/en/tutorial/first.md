# First steps

A program is a sequence of actions. LittleTinker Rig keeps those actions in an ordinary
Python file and shows their structure as colored blocks.

Open the editor using the shortcut or launcher from [installation](../INSTALL.md),
then choose **File → Examples → first.py**. No terminal options are needed when
opening it again.

The narrow icon sidebar on the left switches workspaces, including **Program**,
**Control**, **Block Editor** and **Help**. Hover over an icon to see its name.
The library shows a block's description and Python preview. Files open in tabs
across the top. The two small icons at the top right of the document switch
between **Blocks** and **Python**; the same commands are in the View menu.
**Scratch** starts hidden; open it with the bottom button and drag blocks there
to set them aside.
**Console** opens from the bottom bar.

The **File → Examples** menu opens the bundled programs, including all subdirectories.
The first opening creates your own working copy, including local modules. Later
openings continue your last attempt, even after restarting the app. Changes are
saved automatically. **File → Examples → Start this example again** creates another
attempt; **My attempts** opens earlier work. **Save as** keeps the link to the
example and copies its local modules to your chosen folder.

## From an empty document

Choose **File → New** for an empty document.
On first launch, the library starts at Beginner level; later it remembers your
choice. Select the level button **1** (Beginner) and the **Catalog** view button
using their tooltips. Open the **Program** category.

1. Drag **Repeat with counter** into the empty program.
2. Click `10`, type `3`, and press Enter.
3. Drag **Display value**, also in **Program**, onto `pass` inside the loop.
   The action replaces `pass` inside the loop.
4. Change `"Hello!"` to your own quoted message and press Enter.
5. Choose **Connect hub → Virtual hub → Robot Inventor / SPIKE Prime → Connect**.
6. Press **Run**, then open **Console**. Your message appears three times.
   Run uses the current text without asking for a filename.

Use **Save** when you want to choose a filename and folder. Run first checkpoints
your work for crash recovery; it does not save ordinary files or choose their names.
Save remembers the chosen file. New documents and first launch never silently
create `main.py` or `untitled.py` in the working directory. Close the document and
use **File → Open** or **Open recent** to continue it later.

## Change a parameter

Click the quoted message in your `print(...)` block. Type `"Hello, robot!"`,
including the quotes, and press Enter. If you opened `examples/first.py`, click
`message` in `print(message)` instead. Suggestions have an arrow only when
alternatives are available.

Enter, choosing a suggestion or leaving the field applies valid input. Save and
Run also apply it first. Escape cancels the edit. Invalid input stays visible and
editable; correct or cancel it before saving, running or leaving the document.
**Stop / F6** and disconnect remain available and preserve the unfinished field.

Quoted text is a string. An unquoted word refers to a variable. A number such as
`42` needs no quotes. F3 opens the selected block's parameter editor.

## Add and move actions

Drag a library card into the program. A line and preview show the destination and
indentation. Release to insert the default values immediately; no dialog appears.
Click its parameter fields to adapt it. To insert a statement from the library
without dragging, double-click its card; insertion uses the current selection.

Drag an existing block to move it. Its background and outline show selection.
Python rules still apply: a `break` cannot move outside a loop. Empty loop,
condition and function bodies contain `pass`. Click that row
before double-clicking a library card, or drag onto it, to fill the body.

To put an action after the final loop, drop it in the empty space below the
program. Check the destination preview before releasing. Dropping onto the lower
half of the last row inside the loop keeps it inside the loop.

Ctrl+Z undoes an operation; Ctrl+Shift+Z redoes it. The Python icon opens an ordinary
text editor. It accepts unfinished text and formats valid Python when you save,
run, return to blocks, or press Ctrl+Alt+L. F2 edits just the selected fragment.

## Run without a robot

Click **Connect hub** at the top right, choose **Virtual hub** and a model, then
press **F5 / Run**. The Console button indicates new output. **F6 / Stop** stops
the program, including an infinite loop.

For motor practice, open `examples/motor.py`. For a complete delivery-robot task,
open `examples/courier.py` and follow the [robot guide](../robotics.md#delivery-robot).

## Work on several files

Open selects one or more Python files and creates document tabs. Opening a file
again selects its existing tab. Switching tabs preserves unfinished Python,
selection, scrolling, and undo. The × button or Ctrl+W closes a file and asks about
unsaved changes. Cancelling keeps it open.

Ctrl+S saves the Python file. Scratch fragments and collection settings are stored
beside it in `name.py.ltr.json`; the Python program does not need that file to
run. In Blocks, Ctrl+X moves a fragment to Scratch. In Python, Ctrl+X is ordinary
text cutting. If a file changes outside the editor, Save offers **Reload from
disk**, **Save a copy…**, or Cancel. Reload replaces the open version; ordinary
Open just selects its tab. See [editing and recovery](../usage.md#documents-and-views).

Ctrl+S also saves unfinished Python. Fix its syntax before running or switching
back to Blocks. After a crash, the editor offers to recover open tabs, unsaved text
and Scratch. Execution errors show a short explanation and **Show block** in the
Console; if you have edited the program meanwhile, it shows the executed source
read-only. See [editing and recovery](../usage.md#recovery-examples-and-runtime-errors).
