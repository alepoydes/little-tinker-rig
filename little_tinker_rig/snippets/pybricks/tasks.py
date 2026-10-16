"""Cooperative tasks

Run several robot actions concurrently using Pybricks async functions."""

__category__ = "program"


@inline_block(
    level="expert",
    icon="ƒ",
    color="definition",
    names=("task",),
    category="functions",
    title="Define async task",
)
def define_task():
    """Define an async task; use await for operations that take time."""

    async def task():
        pass


@inline_block(
    level="expert", icon="◷", color="control", context="async", title="Await operation"
)
def await_task(operation=wait(10)):
    """Wait for an operation inside an async function, allowing other tasks to run."""
    from pybricks.tools import wait

    async def wrapper():
        await operation


@inline_block(level="expert", icon="▶", color="control", title="Run main task")
def start_task(operation=task()):
    """Run the main async task; call once from the ordinary program body."""
    from pybricks.tools import run_task

    run_task(operation)


@inline_block(
    level="expert",
    icon="⟳",
    color="control",
    variant="Wait for all",
    title="Combine async tasks",
)
def parallel_tasks(first=task1(), second=task2()):
    """Combine asynchronous operations.

    Create a task that waits for both operations to finish."""
    from pybricks.tools import multitask

    return multitask(first, second)


@inline_block(
    level="expert",
    icon="⟳",
    color="control",
    family="pybricks/tasks/parallel_tasks",
    variant="Finish with the first",
    title="Combine async tasks",
)
def race_tasks(first=task1(), second=wait(2000)):
    """Finish when one operation completes and cancel the other, for example a timeout."""
    from pybricks.tools import multitask, wait

    return multitask(first, second, race=True)
