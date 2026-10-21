"""
### A notebook's declared pod image (`main_img`): find it and evaluate it.

A notebook can declare the image its own pod runs on, as a `flyte.Image`
expression built on `notebook_base` in its setup block. At `/launch` the
dashboard pulls that expression out of the source (`extract_main_img`, pure
`ast`) and evaluates it (`evaluate_main_img`) into the image the notebook's
AppEnvironment runs on. Building is the SDK's: `serve` builds the image on
Union's remote builder, or finds it already built, before it deploys.

Only the expression runs, with `flyte` and `notebook_base` in scope. The
dashboard doesn't carry each notebook's own dependencies, so it can't run the
rest of the setup block.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import ast

import flyte

from app import config
from stargazer.notebooks import notebook_image_base


class MainImgError(Exception):
    """A notebook's `main_img` can't be served; the message is for the dashboard."""


def _is_setup_block(node: ast.stmt) -> bool:
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


def _assigns_main_img(stmt: ast.stmt) -> ast.expr | None:
    """The value `stmt` assigns to `main_img`, if it does."""
    if isinstance(stmt, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "main_img" for t in stmt.targets
    ):
        return stmt.value
    if (
        isinstance(stmt, ast.AnnAssign)
        and isinstance(stmt.target, ast.Name)
        and stmt.target.id == "main_img"
    ):
        return stmt.value
    return None


def extract_main_img(source: str) -> str | None:
    """Return the `main_img = <expr>` expression from the setup block, or None.

    Marimo writes the setup cell as a top-level `with app.setup:` block and
    each cell as a function, so an assignment inside a cell is never found.
    The last assignment wins, as it would when the block runs. Never raises:
    source that doesn't parse declares no image.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError, ValueError:
        return None
    found = None
    for node in tree.body:
        if _is_setup_block(node):
            for stmt in node.body:
                found = _assigns_main_img(stmt) or found
    return ast.unparse(found) if found is not None else None


def evaluate_main_img(expr: str) -> flyte.Image:
    """Evaluate a `main_img` expression into the image to serve the notebook on.

    `notebook_base` is this dashboard's deployed notebook image. Raises
    `MainImgError` when this deployment can't build images (only Union has a
    builder), when the expression raises, or when its result isn't a
    `flyte.Image` built on `notebook_base`: the pod needs the proxy, launch
    script and tools the notebook image carries.
    """
    if config.TARGET != "union":
        raise MainImgError("Notebooks can't build their own image on this deployment.")
    base = notebook_image_base(config.NOTEBOOK_IMAGE)
    try:
        # The owner's own code, in their own dashboard. Its one secret, the
        # org's Pinata key, is one any of the owner's tasks can read anyway.
        img = eval(expr, {"flyte": flyte, "notebook_base": base})
    except Exception as exc:
        raise MainImgError(f"main_img: {type(exc).__name__}: {exc}") from exc
    if isinstance(img, flyte.Image) and img.base_image == base.base_image:
        return img
    raise MainImgError("main_img must be a flyte.Image built on notebook_base")
