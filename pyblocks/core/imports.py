"""One explicitly delimited managed header; user imports are never removed."""

import ast
import io
import tokenize

from .analysis import Scopes, identifiers
from .edit import patches
from .syntax import Span, Syntax

START = "# --- automatically managed imports ---"
END = "# --- user imports ---"


def managed_section(source: str, start=START, end=END) -> Span | None:
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    starts, ends = [], []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT or token.start[1] != 0:
            continue
        if token.string == start:
            starts.append(offsets[token.start[0] - 1])
        if token.string == end:
            ends.append(offsets[token.start[0]])
    if not starts and not ends:
        return None
    if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
        raise ValueError("Managed section markers must form one ordered pair")
    return Span(starts[0], ends[0])


def import_entries(nodes):
    """Split managed dependencies into bound names and canonical statements."""
    for node in nodes:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            raise ValueError("Future imports belong to the user header")
        for alias in node.names:
            if alias.name == "*":
                raise ValueError("Managed dependencies cannot use star imports")
            single = (
                ast.Import(names=[alias])
                if isinstance(node, ast.Import)
                else ast.ImportFrom(module=node.module, names=[alias], level=node.level)
            )
            yield alias.asname or alias.name.split(".")[0], ast.unparse(single)


def manage_imports(
    source: str, required: tuple[str, ...] = (), *, retain: tuple[str, ...] = ()
) -> str:
    """Add dependencies and prune imports only when their bound names disappear.

    Uses in ordinary, unrecognized code count too. A name collision is reported
    instead of silently changing the meaning of an existing binding.
    """
    syntax = Syntax(source)
    section = managed_section(source)
    managed, user = [], []
    for node in syntax.tree.body:
        if section and section.contains(syntax.spans[node].start):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                raise ValueError("Managed section may contain only imports")
            managed.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            user.append(node)
    requested = []
    for text in required:
        nodes = ast.parse(text).body
        if not nodes or not all(
            isinstance(node, (ast.Import, ast.ImportFrom)) for node in nodes
        ):
            raise ValueError("Dependency must be an import statement")
        requested.extend(nodes)

    user_entries = dict(
        import_entries(
            n
            for n in user
            if not (
                isinstance(n, ast.ImportFrom)
                and (n.module == "__future__" or any(a.name == "*" for a in n.names))
            )
        )
    )
    statements = [
        node for node in syntax.tree.body if node not in managed and node not in user
    ]
    scopes = Scopes(ast.Module(body=statements, type_ignores=[]))
    used = {
        node.id
        for node, _ in scopes.references
        if (owner := scopes.resolve(node, node.id)) is None or owner is scopes.root
    }
    for fragment in retain:
        try:
            for token in tokenize.generate_tokens(io.StringIO(fragment).readline):
                if token.type == tokenize.NAME:
                    used.add(token.string)
        except (tokenize.TokenError, IndentationError):
            pass  # Tokens before an unfinished fragment still retain their imports.
    assignments = set(scopes.root.bindings)
    for node in ast.walk(syntax.tree):
        annotation = getattr(node, "annotation", None)
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            try:
                used.update(identifiers(ast.parse(annotation.value, mode="eval")))
            except SyntaxError:
                pass
    for name, _ in import_entries(requested):
        if name in used and name in assignments:
            raise ValueError(
                f"Import name {name!r} conflicts with an existing variable"
            )
    kept = {}
    for name, text in import_entries([*managed, *requested]):
        if name not in used:
            continue
        previous = user_entries.get(name, kept.get(name))
        if previous is not None and previous != text:
            raise ValueError(
                f"Import name {name!r} is already bound; use an explicit alias"
            )
        if name not in user_entries:
            kept[name] = text
    imports = sorted(text for name, text in kept.items() if name in used)
    header = START + "\n" + "\n".join(imports) + "\n" + END + "\n" if imports else ""
    if section:
        return patches(source, [(section, header)])
    if not header:
        return source
    # Preserve the module docstring and mandatory placement of future imports.
    offset = 0
    # Keep interpreter/encoding directives ahead of generated source. Ordinary
    # leading comments may delimit another managed section and must stay intact.
    for line in syntax.lines[:2]:
        if line.startswith("#!") or line.lstrip().startswith("#") and "coding" in line:
            offset += len(line)
        else:
            break
    for index, node in enumerate(syntax.tree.body):
        docstring = (
            index == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
        future = isinstance(node, ast.ImportFrom) and node.module == "__future__"
        if not docstring and not future:
            break
        offset = syntax.block_span(node).end
    return patches(source, [(Span(offset, offset), header + "\n")])
