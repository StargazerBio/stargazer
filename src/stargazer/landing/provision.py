"""
### Per-user Union project provisioning.

Creates an isolated Union project and deploys a per-user Marimo notebook
app on first login. Uses the admin API key for all Union operations.

spec: [docs/architecture/landing.md](../../docs/architecture/landing.md)
"""

import re

from stargazer.config import logger


def sanitize_project_id(github_username: str) -> str:
    """Convert a GitHub username to a valid Union project ID.

    Lowercases, replaces invalid characters with hyphens, and adds
    the sg- prefix to avoid collisions with system projects.
    """
    clean = re.sub(r"[^a-z0-9-]", "-", github_username.lower())
    clean = re.sub(r"-+", "-", clean).strip("-")
    return f"sg-{clean}"


async def provision_user(github_username: str) -> str:
    """Create a Union project and deploy a notebook for a new user.

    Returns the notebook URL. Idempotent — safe to call on repeat logins.

    Raises RuntimeError if provisioning fails.
    """
    project_id = sanitize_project_id(github_username)
    logger.info(f"Provisioning user {github_username!r} → project {project_id!r}")

    # Step 1: Create project (idempotent)
    await _create_project(project_id, github_username)

    # Step 2: Deploy per-user notebook app
    notebook_url = await _deploy_notebook(project_id)

    logger.info(f"Provisioned {github_username!r}: {notebook_url}")
    return notebook_url


async def _create_project(project_id: str, github_username: str):
    """Create a Union project for the user. No-op if it already exists."""
    # TODO: Replace with flyte SDK calls once Union deployment is live.
    # flyte create project --id {project_id} \
    #   --name "Stargazer: {github_username}" \
    #   -l managed-by=stargazer-landing
    logger.info(f"[stub] Would create project {project_id!r} for {github_username!r}")


async def _deploy_notebook(project_id: str) -> str:
    """Deploy a per-user Marimo notebook app into the project.

    Returns the notebook URL.
    """
    # TODO: Replace with flyte.deploy() once Union deployment is live.
    # The AppEnvironment is constructed dynamically from the marimo_env
    # template in stargazer.app, with:
    #   - name=f"notebook-{project_id}"
    #   - requires_auth=True
    #   - env_vars includes FLYTE_PROJECT, FLYTE_DOMAIN
    #   - secrets includes ADMIN_API_KEY as FLYTE_API_KEY
    logger.info(f"[stub] Would deploy notebook for project {project_id!r}")
    return f"https://{project_id}.app.stargazer.bio"
