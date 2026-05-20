"""
### Per-user provisioning called from the admin app's OAuth callback.

One idempotent step per login: ensure the user's Flyte project
(`sg-<username>`) exists. Workspace state used to live on a per-user
PVC, but Flyte v2 doesn't support pod templates on AppEnvironments yet,
so we hold workspace state in each per-notebook pod's ephemeral
storage and push back to the user's GitHub fork on shutdown.

We use `flyte.remote.Project.create()` directly because shelling out to 
`flyte create project` from the admin pod fails:
the subprocess does not inherit the pod's `_U_EP_OVERRIDE` init context
and `ensure_client()` raises before any work is done. See
`.opencode/reference/devbox_workarounds.md`.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import re

from flyte.remote import Project

from stargazer.config import logger


def sanitize_project_id(github_username: str) -> str:
    """Convert a GitHub username to a valid Flyte project / k8s namespace id.

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
        name=github_username,
        description=f"Per-user notebook workspace for GitHub user {github_username}",
        labels={"managed-by": "stargazer-landing", "github-user": github_username},
    )


async def provision_user(*, github_username: str) -> None:
    """Ensure the user's Flyte project exists. Idempotent."""
    project_id = sanitize_project_id(github_username)
    logger.info(f"Provisioning {github_username!r} → project {project_id!r}")
    await _ensure_project(project_id, github_username)
    logger.info(f"Provisioned {github_username!r}")
