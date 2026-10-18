"""Distinguish unfinished block inputs from variadic type annotations."""

import ast


def unfinished_inputs(tree):
    """Yield ellipses that still represent inputs to fill before execution."""
    typed = set()
    for node in ast.walk(tree):
        annotations = []
        if isinstance(node, (ast.arg, ast.AnnAssign)):
            annotations.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotations.append(node.returns)
        elif isinstance(node, getattr(ast, "TypeAlias", ())):
            annotations.append(node.value)
        for annotation in annotations:
            if annotation is not None and not (
                isinstance(annotation, ast.Constant) and annotation.value is Ellipsis
            ):
                typed.update(id(child) for child in ast.walk(annotation))
    return (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and node.value is Ellipsis
        and id(node) not in typed
    )
