"""
### Per-user Flyte project provisioning.

On each GitHub login, ensure a `sg-<github-username>` Flyte project exists
and deploy the user's own marimo notebook into it. Project creation is
idempotent (existence check via `Project.get.aio` first); the notebook
`serve.aio()` is re-run every login — Flyte/Knative roll a new revision.

The Flyte v2 docs claim the Python SDK provides read-only access to
projects, but `flyte.remote.Project.create()` exists and works (the
`flyte create project` CLI just wraps the same gRPC call). We use the SDK
directly because the CLI subprocess does not inherit the in-pod
`_U_EP_OVERRIDE` init context and fails with `InitializationError`.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import re

import flyte
from flyte.remote import Project

from stargazer.config import logger

from app.notebook_app import notebook_env


DOMAIN = "development"


def sanitize_project_id(github_username: str) -> str:
    """Convert a GitHub username to a valid Flyte project id.

    Lowercases, replaces invalid characters with hyphens, collapses runs,
    and prefixes `sg-` to avoid colliding with system projects.
    """
    clean = re.sub(r"[^a-z0-9-]", "-", github_username.lower())
    clean = re.sub(r"-+", "-", clean).strip("-")
    return f"sg-{clean}"


async def _ensure_project(project_id: str, github_username: str) -> None:
    """Get the project or create it via the SDK. Idempotent."""
    try:
        await Project.get.aio(name=project_id)
        logger.info(f"Project {project_id!r} already exists")
        return
    except Exception:
        pass

    logger.info(f"Creating project {project_id!r} for {github_username!r}")
    await Project.create.aio(
        id=project_id,
        name=f"Stargazer: {github_username}",
        description=f"Per-user notebook workspace for GitHub user {github_username}",
        labels={"managed-by": "stargazer-landing", "github-user": github_username},
    )


async def provision_user(github_username: str) -> str:
    """Ensure project + notebook app for the user; return the notebook URL."""
    project_id = sanitize_project_id(github_username)
    logger.info(f"Provisioning {github_username!r} → project {project_id!r}")

    await _ensure_project(project_id, github_username)

    app = await flyte.with_servecontext(
        project=project_id, domain=DOMAIN
    ).serve.aio(notebook_env)

    # `App.endpoint` is the user-facing public URL; `App.url` is the in-cluster
    # Flyte console URL (mis-named in the SDK).
    logger.info(f"Provisioned {github_username!r}: {app.endpoint}")
    return app.endpoint
