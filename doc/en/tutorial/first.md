# First steps

A program is a sequence of actions. PyBlocks keeps those actions in an ordinary
Python file and shows their structure as colored blocks.

```sh
uv run --extra qt pyblocks-qt examples/first.py
```

The narrow tabs on the left switch between **Program**, **Control** and **Help**.
The library shows a block's description and Python preview. Files open in tabs
across the top. The two small icons at the top right of the document switch
between **Blocks** and **Python**; the same commands are in the View menu.
**Scratch** is visible on the right; drag blocks there to set them aside.
**Console** opens from the bottom bar.

The **File → Examples** menu opens the bundled programs, including all subdirectories.
It opens the example file itself; use **Save as** to keep your own variation.

## From an empty document

Launch `uv run --extra qt pyblocks-qt` without a filename, or choose **File → New**.
The library starts with **Python basics** at Beginner level.

1. Select **Repeat actions a given number of times** and click **Add selected block**.
2. Click `10`, type `3`, and press Enter.
3. Click the `pass` row inside the loop, then add **Display a value in the console**.
   The action replaces `pass` inside the loop.
4. Change `"Hello!"` to your own quoted message and press Enter.
5. Choose **Connect hub → Virtual hub → Robot Inventor / SPIKE Prime → Connect**.
6. Press **Run**. Choose a name and folder when prompted, then open **Console**.
   Your message appears three times. Cancelling the save also cancels execution.

Save remembers the chosen file. New documents and first launch never silently
create `main.py` or `untitled.py` in the working directory. Close the document and
use **File → Open** or **Open recent** to continue it later.

## Change a parameter

Click the visible field around `message` in `print(message)`. Select a suggestion
or type `"Hello, robot!"`, including the quotes, and press Enter. The editor
updates the Python source immediately. Invalid input stays in the inline field so
you can correct it; the program is unchanged. Click outside or press Escape to cancel.

Quoted text is a string. An unquoted word refers to a variable. A number such as
`42` needs no quotes. F3 opens the first parameter of the selected block.

## Add and move actions

Drag a library card into the program. A line and preview show the destination and
indentation. Release to insert the default values immediately; no dialog appears.
Click its parameter fields to adapt it. To insert a statement from the library
without dragging, select its card and use **Add selected block**.

Drag an existing block to move it. A block's selected background slowly pulses;
it has no selection border. Python rules still apply: a `break` cannot move outside
a loop. Empty loop, condition and function bodies contain `pass`. Click that row
before **Add selected block**, or drag onto it, to fill the body.

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
beside it in `name.py.pyblocks.json`; the Python program does not need that file to
run. In Blocks, Ctrl+X moves a fragment to Scratch. In Python, Ctrl+X is ordinary
text cutting. External changes to a file are detected before saving: reopen the
current file or use Save as to another path.

Ctrl+S also saves unfinished Python. Fix its syntax before running or switching
back to Blocks. After a crash, the editor offers to recover open tabs, unsaved text
and Scratch. Execution errors show a short explanation and **Show block** in the
Console; if you have edited the program meanwhile, it shows the executed source
read-only. See [editing and recovery](../usage.md#recovery-examples-and-runtime-errors).
