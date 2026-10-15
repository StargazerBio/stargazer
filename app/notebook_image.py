"""
### A notebook's declared pod image (`main_img`): find it, evaluate it, build it.

A notebook can declare the image its own pod runs on, as a `flyte.Image`
expression built on `notebook_base` in its setup block. At `/launch` the
dashboard pulls that expression out of the source (`extract_main_img`, pure
`ast`, nothing executed), then evaluates and builds it in a fresh subprocess
(`python -m app.notebook_image`) on Union's remote builder. The subprocess
keeps a hang or crash in the owner's code out of the dashboard, and gives each
build a fresh SDK, whose `build` is cached per process.

Only the expression runs, with `flyte` and `notebook_base` in scope. The
dashboard doesn't carry each notebook's own dependencies, so it can't run the
rest of the setup block.

Builds run in a thread pool, one per expression, so a launch can answer
"building" and a later launch joins the same build. The deployed notebook
image is fixed for the life of a dashboard, so the expression alone keys a
build.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import ast
import asyncio
import json
import os
import subprocess
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass

import flyte

from app import config
from app.init import init
from stargazer.config import logger
from stargazer.notebooks import notebook_base

# How long a launch waits on a build before answering "building". An image
# that already exists resolves well inside this, so it launches in one go.
BUILD_WAIT_SECONDS = 10.0
BUILD_TIMEOUT_SECONDS = 3600
# Marks the subprocess's result line among whatever the SDK prints.
_RESULT_PREFIX = "SG_MAIN_IMG "
_UNBUILT = "This notebook's image couldn't be built. Try launching again."


@dataclass(frozen=True)
class ImageResult:
    """A resolved `main_img`: the image URI to serve, or an error to show."""

    uri: str | None = None
    error: str | None = None


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
    The last assignment wins, as it would when the block runs. The expression
    comes back normalized (`ast.unparse`), so reformatting it isn't a new
    build. Never raises: source that doesn't parse declares no image.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    found = None
    for node in tree.body:
        if _is_setup_block(node):
            for stmt in node.body:
                found = _assigns_main_img(stmt) or found
    return ast.unparse(found) if found is not None else None


def evaluate_main_img(expr: str, base: flyte.Image) -> flyte.Image:
    """Evaluate a `main_img` expression with `flyte` and `notebook_base` in scope.

    Raises TypeError if the result isn't a `flyte.Image`, and ValueError if
    it isn't built on `base`, since the pod needs the proxy, launch script and
    tools the notebook image carries. An error the expression raises
    propagates.
    """
    # The owner's own code, run in a subprocess of their own dashboard.
    img = eval(expr, {"flyte": flyte, "notebook_base": base})
    if not isinstance(img, flyte.Image):
        raise TypeError(f"main_img must be a flyte.Image, not {type(img).__name__}")
    if img.base_image != base.base_image:
        raise ValueError("main_img must be built on notebook_base")
    return img


def checked_uri(uri: str | None) -> ImageResult:
    """Accept a built image's URI only if it names a registry.

    When the SDK can't check whether an image exists (no remote builder, an
    API error), it assumes it does and hands back the bare `name:tag`, which
    no node can pull.
    """
    if uri and "/" in uri:
        return ImageResult(uri=uri)
    return ImageResult(error=_UNBUILT)


def _build(expr: str) -> ImageResult:
    """Evaluate `expr` and build the image; the subprocess's whole job."""
    try:
        img = evaluate_main_img(expr, notebook_base)
    except Exception as exc:
        return ImageResult(error=f"main_img: {type(exc).__name__}: {exc}")
    if img == notebook_base:
        return ImageResult(uri=notebook_base.base_image)
    try:
        init()
        build = flyte.build(img)
    except Exception as exc:
        return ImageResult(error=f"This notebook's image failed to build: {exc}")
    return checked_uri(build.uri)


def resolve_main_img(expr: str) -> ImageResult:
    """Evaluate and build `expr` in a fresh subprocess; blocks until it's done.

    The subprocess builds on the deployed notebook image, passed in its env.
    """
    env = dict(os.environ)
    if config.NOTEBOOK_IMAGE:
        env["STARGAZER_NOTEBOOK_IMAGE"] = config.NOTEBOOK_IMAGE
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "app.notebook_image"],
            input=expr,
            capture_output=True,
            text=True,
            env=env,
            timeout=BUILD_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ImageResult(error="This notebook's image took too long to build.")
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(_RESULT_PREFIX):
            return ImageResult(**json.loads(line.removeprefix(_RESULT_PREFIX)))
    logger.error(f"main_img subprocess exited {proc.returncode}: {proc.stderr[-2000:]}")
    return ImageResult(error=_UNBUILT)


_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="main-img")
_builds: dict[str, Future[ImageResult]] = {}


async def launch_image(expr: str) -> ImageResult | None:
    """The image a launch should serve for `expr`, or None while it builds.

    The first launch of an expression starts its build; later launches join
    it. A finished build is kept, so a relaunch reuses its URI; a failed one
    is dropped once reported, so the next launch tries again. Only Union has
    an image builder.
    """
    if config.TARGET != "union":
        return ImageResult(
            error="Notebooks can't build their own image on this deployment."
        )
    future = _builds.get(expr)
    if future is None:
        future = _builds[expr] = _executor.submit(resolve_main_img, expr)
    if not future.done():
        await asyncio.wait([asyncio.wrap_future(future)], timeout=BUILD_WAIT_SECONDS)
        if not future.done():
            return None
    try:
        result = future.result()
    except Exception as exc:
        logger.error(f"main_img build crashed for {expr!r}: {exc}")
        result = ImageResult(error=_UNBUILT)
    if result.error:
        _builds.pop(expr, None)
    return result


def main() -> None:
    """Subprocess entry: read the expression on stdin, print the result line."""
    result = _build(sys.stdin.read())
    print(_RESULT_PREFIX + json.dumps(asdict(result)), flush=True)


if __name__ == "__main__":
    main()
