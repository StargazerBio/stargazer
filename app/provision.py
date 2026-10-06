"""
### Per-user provisioning: make sure the user's Flyte project exists.

Every user gets one Flyte project, `u-<subject>`, keyed by their Union
subject so it never changes. Their notebook pods are served into it, which
isolates their runs and caches from everyone else's.

There is no login callback to hang this on — Union owns sign-in — so the
admin ensures the project on a user's first request to this process
(`provision_user`) and remembers it, keeping the control-plane round-trip off
every later request.

We use `flyte.remote.Project.create()` directly because shelling out to
`flyte create project` from the admin pod fails:
the subprocess does not inherit the pod's `_U_EP_OVERRIDE` init context
and `ensure_client()` raises before any work is done. See
`.opencode/reference/devbox_workarounds.md`.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import re

from flyte.remote import Project

from app.identity import User
from stargazer.config import logger

# Projects already ensured by this process. Losing it on restart only costs
# one idempotent re-check per user.
_provisioned: set[str] = set()


def project_id(subject: str) -> str:
    """The user's Flyte project id: `u-<subject>`, in `[a-z0-9-]`."""
    clean = re.sub(r"[^a-z0-9-]", "-", subject.lower())
    return "u-" + re.sub(r"-+", "-", clean).strip("-")


async def _ensure_project(project: str, user: User) -> None:
    """Get the project or create it via the SDK. Idempotent."""
    try:
        await Project.get.aio(name=project)
        logger.info(f"Project {project!r} already exists")
        return
    except Exception:
        pass

    logger.info(f"Creating project {project!r} for {user.display!r}")
    await Project.create.aio(
        id=project,
        name=user.display,
        description=f"Stargazer notebooks for {user.display}",
        labels={"managed-by": "stargazer", "union-subject": user.subject},
    )


async def provision_user(user: User) -> str:
    """Ensure the user's project exists (once per process); return its id."""
    project = project_id(user.subject)
    if project not in _provisioned:
        await _ensure_project(project, user)
        _provisioned.add(project)
    return project
