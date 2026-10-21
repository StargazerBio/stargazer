"""
### A notebook's setup block: what the dashboard reads from it, and rewriting it.

A notebook declares what the dashboard needs to know about it in marimo's
`with app.setup:` block, beside the image its pod runs on (`main_img`,
`app.notebook_image`):

    with app.setup:
        import flyte

        main_name = "QC run"
        main_description = "Quality control on new runs."
        main_resources = flyte.Resources(cpu=2, memory="4Gi")

The tile shows the name and description, and `/launch` sizes the pod from the
resources. The dashboard reads them with `ast` and runs no notebook code, so
the name and description are string literals and `main_resources` is a
`flyte.Resources(...)` call whose arguments are literals. Whatever a notebook
declares is honored as-is; there is no ceiling.

The gear on a workspace tile edits the whole block (`setup_block_text`,
`replace_setup_block`), and create and copy set the name and description
(`with_setup_values`).

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import ast
import json

import flyte


class SetupError(Exception):
    """A setup block the dashboard can't use; the message is for the dashboard."""


def is_setup_block(node: ast.stmt) -> bool:
    """Whether `node` is marimo's `with app.setup:` (or `app.setup(...)`) block."""
    if not isinstance(node, ast.With) or len(node.items) != 1:
        return False
    expr = node.items[0].context_expr
    if isinstance(expr, ast.Call):
        expr = expr.func
    return (
        isinstance(expr, ast.Attribute)
        and expr.attr == "setup"
        and isinstance(expr.value, ast.Name)
        and expr.value.id == "app"
    )


def _parse(source: str) -> ast.Module | None:
    """`source` parsed, or None when it doesn't parse."""
    try:
        return ast.parse(source)
    except SyntaxError, ValueError:
        return None


def _setup_block(tree: ast.Module | None) -> ast.With | None:
    """The module's setup block, or None."""
    if tree is None:
        return None
    return next((node for node in tree.body if is_setup_block(node)), None)


def _assignments(block: ast.With) -> dict[str, ast.Assign | ast.AnnAssign]:
    """Each name `block` assigns at its top level, mapped to its last assignment.

    Marimo writes each cell as a function, so an assignment inside a cell is
    never the setup block's.
    """
    found: dict[str, ast.Assign | ast.AnnAssign] = {}
    for stmt in block.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = stmt
        elif (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.value is not None
        ):
            found[stmt.target.id] = stmt
    return found


def setup_assignments(source: str) -> dict[str, ast.Assign | ast.AnnAssign]:
    """Each name the setup block assigns, mapped to its last assignment.

    Never raises: source that doesn't parse, or has no setup block, assigns
    nothing.
    """
    block = _setup_block(_parse(source))
    return _assignments(block) if block is not None else {}


def _string(stmt: ast.Assign | ast.AnnAssign | None) -> str | None:
    """The string literal `stmt` assigns, or None if it assigns anything else."""
    if stmt is None:
        return None
    try:
        value = ast.literal_eval(stmt.value)
    except ValueError, TypeError, SyntaxError, MemoryError, RecursionError:
        return None
    return value if isinstance(value, str) else None


def notebook_name(source: str) -> str:
    """The notebook's `main_name`, or "" when it declares none."""
    return _string(setup_assignments(source).get("main_name")) or ""


def notebook_description(source: str) -> str:
    """The notebook's `main_description`, or "" when it declares none."""
    return _string(setup_assignments(source).get("main_description")) or ""


def _resources(stmt: ast.Assign | ast.AnnAssign) -> flyte.Resources:
    """Build the `flyte.Resources` a `main_resources` assignment declares.

    Raises `SetupError` when the value isn't a `flyte.Resources(...)` call or
    an argument isn't a literal.
    """
    call = stmt.value
    if not (
        isinstance(call, ast.Call)
        and ast.unparse(call.func) in ("flyte.Resources", "Resources")
    ):
        raise SetupError("main_resources must be a flyte.Resources(...) call.")
    try:
        args = [ast.literal_eval(arg) for arg in call.args]
        kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords}
    except ValueError, TypeError, SyntaxError, MemoryError, RecursionError:
        raise SetupError(
            'main_resources: every argument must be a literal value, like cpu=2 or memory="4Gi".'
        ) from None
    try:
        return flyte.Resources(*args, **kwargs)
    except (TypeError, ValueError) as exc:
        raise SetupError(f"main_resources: {exc}") from exc


def notebook_resources(source: str) -> flyte.Resources | None:
    """The notebook's `main_resources`, or None when it declares none.

    Raises `SetupError` when they're declared but can't be read.
    """
    stmt = setup_assignments(source).get("main_resources")
    return _resources(stmt) if stmt is not None else None


def _block_span(source: str) -> tuple[int, int] | None:
    """The setup block's lines in `source`, as a `[start, end)` index range.

    `ast` ends the block at its last statement, but a comment that closes the
    block belongs to it too, so the span runs on through indented comment
    lines (and the blank lines between them).
    """
    block = _setup_block(_parse(source))
    if block is None:
        return None
    lines = source.splitlines(keepends=True)
    start, end = block.lineno - 1, block.end_lineno
    i = end
    while i < len(lines):
        line = lines[i]
        if line.strip() and not (line[0].isspace() and line.lstrip().startswith("#")):
            break
        i += 1
        if line.strip():
            end = i
    return start, end


def setup_block_text(source: str) -> str | None:
    """The setup block as written, from its `with` line through its last line.

    None when the notebook has no setup block or doesn't parse.
    """
    span = _block_span(source)
    if span is None:
        return None
    text = "".join(source.splitlines(keepends=True)[span[0] : span[1]])
    return text if text.endswith("\n") else text + "\n"


def _check_block(block: str) -> None:
    """Raise `SetupError` unless `block` is one setup block the dashboard can read."""
    try:
        tree = ast.parse(block)
    except SyntaxError as exc:
        raise SetupError(f"line {exc.lineno}: {exc.msg}") from exc
    if len(tree.body) != 1 or not is_setup_block(tree.body[0]):
        raise SetupError("The setup block must be one `with app.setup:` block.")
    found = _assignments(tree.body[0])
    if "main_resources" in found:
        _resources(found["main_resources"])
    for name in ("main_name", "main_description"):
        if name in found and _string(found[name]) is None:
            raise SetupError(f"{name} must be a string.")


def replace_setup_block(source: str, block: str) -> str:
    """Return `source` with its setup block replaced by `block`.

    A notebook without a setup block gets `block` right after its
    `app = marimo.App(...)` line, where marimo writes one. Raises `SetupError`,
    and changes nothing, when `block` isn't one readable setup block or there's
    nowhere to put it.
    """
    block = block.replace("\r\n", "\n").rstrip() + "\n"
    _check_block(block)
    lines = source.splitlines(keepends=True)
    span = _block_span(source)
    if span is not None:
        return "".join(lines[: span[0]] + [block] + lines[span[1] :])
    tree = _parse(source)
    app_line = next(
        (
            stmt.end_lineno
            for stmt in (tree.body if tree is not None else [])
            if isinstance(stmt, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "app" for t in stmt.targets)
        ),
        None,
    )
    if app_line is None:
        raise SetupError(
            "This notebook has no `app = marimo.App(...)` line to put a setup block after."
        )
    return "".join(lines[:app_line] + ["\n", block] + lines[app_line:])


def with_setup_values(source: str, **values: str) -> str:
    """Return `source` with each `name = "value"` declared in its setup block.

    A name the block already assigns is reassigned in place; a new one goes
    after the block's leading imports. A notebook without a setup block gets
    one. Raises `SetupError` as `replace_setup_block` does.
    """
    for name, value in values.items():
        line = f"{name} = {json.dumps(value, ensure_ascii=False)}\n"
        text = setup_block_text(source)
        if text is None:
            source = replace_setup_block(source, f"with app.setup:\n    {line}")
            continue
        block = ast.parse(text).body[0]
        lines = text.splitlines(keepends=True)
        indent = " " * block.body[0].col_offset
        stmt = _assignments(block).get(name)
        if stmt is not None:
            lines[stmt.lineno - 1 : stmt.end_lineno] = [indent + line]
        else:
            imports = []
            for s in block.body:
                if not isinstance(s, ast.Import | ast.ImportFrom):
                    break
                imports.append(s)
            at = imports[-1].end_lineno if imports else block.body[0].lineno - 1
            lines.insert(at, indent + line)
        source = replace_setup_block(source, "".join(lines))
    return source
