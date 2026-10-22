"""
### Deploying a user's dashboard: the images, the version, and the serve.

`deploy_dashboard` serves `app.admin_app.app_env` into a user's project with
the owner and their settings baked in, at the stable subdomain `<project>`.
The same app definition goes to every user: only the project, the owner and
the subdomain differ. Union doesn't reject a second app asking for a taken
subdomain (it hangs), so uniqueness comes from project ids being unique.

Each dashboard is deployed under the commit it came from (`release_version`)
as its version, and shows it on its page. A redeploy waits for the user's
runs to finish (`active_runs`, `refuse_while_running`): the dashboard holds
their asset index, and a write that lands on the outgoing version is lost.

Onboarding, which makes users, their projects and their access and calls
this for each, lives in the infra repo. The devbox's dashboard
(`devbox/dashboard.py`) deploys through here too.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import asyncio
import os
import subprocess
import time
from functools import cache
from pathlib import Path

import flyte
import flyte.app
from flyte._initialize import get_init_config
from flyte.models import ActionPhase
from flyte.remote import App, Run

from app import config
from app.admin_app import app_env
from app.per_notebook import list_project_apps, notebook_app_img_recipe
from stargazer.config import PROJECT_ROOT, logger

# How long a deploy whose watch reported failure gets to come up anyway.
_ACTIVE_POLLS, _ACTIVE_POLL_SECONDS = 24, 5
# The dashboard's env as defined, before any user's settings are applied, so
# deploying several users in one run never carries one user's values over.
_BASE_ENV_VARS = dict(app_env.env_vars)
# Where the dashboard keeps its SQLite index, on its own disk (Litestream
# makes it durable). `~` expands in the pod.
_DASHBOARD_INDEX = "~/.stargazer/index.db"
_UNFINISHED = (
    ActionPhase.QUEUED,
    ActionPhase.WAITING_FOR_RESOURCES,
    ActionPhase.INITIALIZING,
    ActionPhase.RUNNING,
)


def build_notebook_image() -> str:
    """Build the per-notebook image recipe and return its content-hashed URI.

    A dashboard pod can't build images (no Docker daemon, no project layout),
    so the deployer builds here and every dashboard gets the URI as
    `STARGAZER_NOTEBOOK_IMAGE`; every notebook app then runs exactly this
    build. Content hashing makes a rebuild of an unchanged recipe a registry
    hit, so a release builds once however many users it deploys.
    """
    logger.info("Building per-notebook flyte.Image (recipe)")
    result = flyte.build(notebook_app_img_recipe)
    if result.uri is None:
        raise RuntimeError("flyte.build did not return an image URI")
    logger.info(f"Per-notebook image: {result.uri}")
    return result.uri


@cache
def _notebook_image() -> str:
    """The notebook image URI, built at most once per run."""
    return build_notebook_image()


def release_version(root: Path = PROJECT_ROOT) -> str:
    """The commit the deployer's checkout is at: the dashboard's deploy version.

    `git describe --always --dirty`: the short hash (tag-relative once the
    repo has tags), with `-dirty` when tracked files have uncommitted changes,
    since a deploy ships the working tree, not the commit. Read at each
    deploy, so it names what that deploy shipped, on the dashboard's page and
    in the console. `unknown` outside a git checkout.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "describe", "--always", "--dirty"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def deploy_dashboard(
    project: str, owner_subject: str, extra_env: dict[str, str] | None = None
) -> str:
    """Deploy the dashboard into `project` for its owner; return its URL.

    Same app definition for every user: only the project, the owner and the
    subdomain differ. Images are content-hashed, so a release builds each
    once and every user's dashboard runs the same build. The deploy is
    versioned with `release_version()`, which the dashboard also shows on its
    page; redeploying under a version the app already has still updates it.
    `extra_env` is applied last.
    """
    version = release_version()
    env_vars = {
        **_BASE_ENV_VARS,
        "FLYTE_PROJECT": project,
        "SG_OWNER_SUBJECT": owner_subject,
        "STARGAZER_OWNER": owner_subject,
        "STARGAZER_NOTEBOOK_IMAGE": _notebook_image(),
        "STARGAZER_INDEX_URL": _DASHBOARD_INDEX,
        "STARGAZER_VERSION": version,
    }
    # Assets live under the same root as the workspace notebooks.
    env_vars.pop("STARGAZER_STORE_ROOT", None)
    if config.WORKSPACE_ROOT:
        env_vars["STARGAZER_STORE_ROOT"] = config.WORKSPACE_ROOT
    # The bucket's region, for Litestream (app.dashboard_launch), when the
    # deployer gives one; the pod's AWS_REGION wins if it has one.
    if region := os.environ.get("STARGAZER_STORE_REGION"):
        env_vars["STARGAZER_STORE_REGION"] = region
    # The org admins who may open every user's dashboard and notebooks
    # (`app.identity`), when the deployer names them.
    if admins := os.environ.get("STARGAZER_ADMIN_SUBJECTS"):
        env_vars["STARGAZER_ADMIN_SUBJECTS"] = admins
    # Public assets turned off for every dashboard the deploy touches
    # (`app.config.PUBLIC_ASSETS`), when the deployer says so.
    if public := os.environ.get("STARGAZER_PUBLIC_ASSETS"):
        env_vars["STARGAZER_PUBLIC_ASSETS"] = public
    # In-cluster init can't discover the org in an app pod; bake the deployer's.
    if org := get_init_config().org:
        env_vars["FLYTE_ORG"] = org
    env_vars.update(extra_env or {})
    # Serve `app_env` itself, set up for this user, rather than a
    # `clone_with` copy: the copy records `dataclasses.py` as the frame it was
    # created in, and Flyte resolves `include=` and the pod's loader from that
    # frame, so the deploy fails looking for `templates/` in the stdlib.
    env = app_env
    env.env_vars = env_vars
    env.domain = flyte.app.Domain(subdomain=project)
    ctx = flyte.with_servecontext(
        project=project, domain=config.FLYTE_DOMAIN, version=version
    )
    # The serve watch can report failure on a redeploy that does succeed: it
    # trips on an older failed revision while the new one is still starting
    # (seen on the tenant and the devbox). Trust the app's own
    # state over it, giving the new revision a little time.
    try:
        return ctx.serve(env).endpoint
    except RuntimeError as exc:
        for _ in range(_ACTIVE_POLLS):
            app = App.get(name=env.name, project=project, domain=config.FLYTE_DOMAIN)
            if app.is_active() and app.endpoint:
                logger.warning(
                    f"Serve watch for {project} reported {exc}; the app is up"
                )
                return app.endpoint
            time.sleep(_ACTIVE_POLL_SECONDS)
        raise


def active_runs(project: str) -> list[str]:
    """Names of the project's runs that haven't finished."""
    return [
        run.name
        for run in Run.listall(
            in_phase=_UNFINISHED,
            project=project,
            domain=config.FLYTE_DOMAIN,
            limit=50,
        )
    ]


def refuse_while_running(projects: list[str]) -> None:
    """Raise if any of these projects has a run that hasn't finished.

    A dashboard redeploy briefly runs the old and new versions side by side;
    an index write the old one accepts after the new one has restored its
    database is lost. Until that's handled properly, redeploys wait for runs
    to finish.
    """
    busy = {p: runs for p in projects if (runs := active_runs(p))}
    if busy:
        detail = "; ".join(f"{p}: {', '.join(runs)}" for p, runs in busy.items())
        raise RuntimeError(
            f"runs still going, so their dashboards can't be redeployed yet ({detail})"
        )


def stop_project_apps(project: str) -> list[str]:
    """Deactivate every active app in the project; return their names."""

    async def _stop() -> list[str]:
        stopped = []
        for listed in await list_project_apps(project, domain=config.FLYTE_DOMAIN):
            app = await App.get.aio(
                name=listed.name, project=project, domain=config.FLYTE_DOMAIN
            )
            if app.is_active():
                await app.deactivate.aio()
                stopped.append(listed.name)
        return stopped

    return asyncio.run(_stop())
