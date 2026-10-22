"""
### A notebook's declared pod environment (`main_env`): find it and evaluate it.

A notebook can declare the environment its own pod runs in, a
`flyte.app.AppEnvironment` cloned from `notebook_env`, in its setup block,
beside its name and description (`app.notebook_meta`):

    main_env = notebook_env.clone_with(
        name="variant-qc",
        image=notebook_base.with_apt_packages("bcftools"),
        resources=flyte.Resources(cpu=2, memory="4Gi"),
    )

At `/launch` the dashboard pulls that expression out of the source
(`extract_main_env`, pure `ast`) and evaluates it (`evaluate_main_env`);
`app.per_notebook.per_notebook_env` then puts the dashboard's own fields on
top. Building is the SDK's: `serve` builds a declared image on Union's remote
builder, or finds it already built, before it deploys.

Only the expression runs, with `flyte`, `notebook_base` and `notebook_env`
in scope. The dashboard doesn't carry each notebook's own dependencies, so it
can't run the rest of the setup block.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import ast
from collections.abc import Iterator
from contextlib import contextmanager

import flyte
import flyte.app
from flyte._environment import list_loaded_environments

from app import config
from app.notebook_meta import setup_assignments
from stargazer.notebooks import notebook_environment, notebook_image_base


class MainEnvError(Exception):
    """A notebook's `main_env` can't be served; the message is for the dashboard."""


def extract_main_env(source: str) -> str | None:
    """Return the `main_env = <expr>` expression from the setup block, or None.

    The last assignment wins, as it would when the block runs. Never raises:
    source that doesn't parse declares no environment.
    """
    stmt = setup_assignments(source).get("main_env")
    return ast.unparse(stmt.value) if stmt is not None else None


def evaluate_main_env(expr: str) -> flyte.app.AppEnvironment:
    """Evaluate a `main_env` expression into the environment the notebook declares.

    `notebook_base` is this dashboard's deployed notebook image, and
    `notebook_env` the default environment on it. Raises `MainEnvError` when
    the expression raises, when its result isn't an `AppEnvironment` on a
    `flyte.Image` built on `notebook_base` (the pod needs the proxy, launch
    script and tools the notebook image carries), or when it adds layers and
    this deployment can't build images (only Union has a builder).
    """
    base = notebook_image_base(config.NOTEBOOK_IMAGE)
    scope = {
        "flyte": flyte,
        "notebook_base": base,
        "notebook_env": notebook_environment(base),
    }
    try:
        # The owner's own code, in their own dashboard. Its one secret, the
        # org's Pinata key, is one any of the owner's tasks can read anyway.
        env = eval(expr, scope)
    except Exception as exc:
        raise MainEnvError(f"main_env: {type(exc).__name__}: {exc}") from exc
    if not isinstance(env, flyte.app.AppEnvironment):
        raise MainEnvError(
            "main_env must be a flyte.app.AppEnvironment, like notebook_env.clone_with(...)"
        )
    if not (
        isinstance(env.image, flyte.Image) and env.image.base_image == base.base_image
    ):
        raise MainEnvError("main_env's image must be built on notebook_base")
    if env.image != base and config.TARGET != "union":
        raise MainEnvError("Notebooks can't build their own image on this deployment.")
    return env


@contextmanager
def forget_new_environments() -> Iterator[None]:
    """Unregister every Flyte environment created inside the block.

    Each environment registers itself as it's built, for `flyte deploy` to
    find. The dashboard serves what it builds directly and never deploys from
    the registry, so without this every launch's environments would stay in
    it for the life of the process.
    """
    registry = list_loaded_environments()
    before = {id(env) for env in registry}
    try:
        yield
    finally:
        registry[:] = [env for env in registry if id(env) in before]
