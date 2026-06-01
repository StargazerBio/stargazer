"""
### GitHub repo operations beyond OAuth.

Currently scoped to forking upstream `stargazer` into the authenticated
user's account. Idempotent — calling `fork_upstream` when a fork already
exists returns the existing one rather than erroring.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import base64
import os

import aiohttp


GITHUB_API_BASE = "https://api.github.com"
WORKSPACE_CONTENTS_PATH = "src/stargazer/notebooks/workspace"

# User notebooks live and persist on the fork's default branch. Edits are
# confined to WORKSPACE_CONTENTS_PATH (the proxy only `git add`s that dir),
# so the fork's `main` never collides with upstream's shipped files — no side
# branch needed. See docs/architecture/app.md.
WORKSPACE_BRANCH = "main"


def upstream_repo() -> tuple[str, str]:
    """Resolve the canonical upstream `(owner, name)` for forking.

    Read from `STARGAZER_UPSTREAM_REPO` (format `owner/name`); defaults
    to the public-org canonical path.
    """
    spec = os.environ.get("STARGAZER_UPSTREAM_REPO", "StargazerBio/stargazer")
    owner, _, name = spec.partition("/")
    if not owner or not name:
        raise ValueError(
            f"STARGAZER_UPSTREAM_REPO must look like 'owner/name', got {spec!r}"
        )
    return owner, name


def upstream_full_name() -> str:
    """Return the upstream repo as an `owner/name` string."""
    owner, name = upstream_repo()
    return f"{owner}/{name}"


def is_genuine_fork(repo: dict) -> bool:
    """True if `repo` is a real fork we may safely write to.

    Guards the transfer-redirect and self-fork cases: a repo whose path
    redirects to (or *is*) the upstream source comes back as the source —
    not a fork the user owns. We require GitHub's `fork` flag and a
    `full_name` distinct from the upstream. Writing to anything else risks
    clobbering the shared upstream (see docs/architecture/app.md).
    """
    full = (repo.get("full_name") or "").lower()
    return (
        repo.get("fork") is True
        and "/" in full
        and full != upstream_full_name().lower()
    )


async def fork_upstream(access_token: str) -> dict:
    """Idempotently fork the upstream stargazer repo into the token holder's account.

    GitHub's `POST /repos/{owner}/{repo}/forks` returns the existing fork
    if one already exists, so this is safe to call on every login.

    Returns the fork payload (dict with at least `owner.login`, `name`,
    `clone_url`). Raises `aiohttp.ClientResponseError` on transport or
    auth failure.
    """
    owner, name = upstream_repo()
    url = f"{GITHUB_API_BASE}/repos/{owner}/{name}/forks"
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        resp.raise_for_status()
        return await resp.json()


async def list_workspace(fork_full_name: str, access_token: str) -> list[str]:
    """List `.py` files under `notebooks/workspace/` in the user's fork.

    Cold-case fallback used by the admin dashboard when no per-notebook
    pod is up for the user. `fork_full_name` is the verified `owner/repo`
    of the fork. Reads from the fork's `WORKSPACE_BRANCH` (where the proxy's
    `/__sg__/workspace/sync` pushes). Returns an empty list if the directory
    doesn't exist yet.
    """
    url = (
        f"{GITHUB_API_BASE}/repos/{fork_full_name}/contents/"
        f"{WORKSPACE_CONTENTS_PATH}"
    )
    async with aiohttp.ClientSession() as session:
        resp = await session.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params={"ref": WORKSPACE_BRANCH},
        )
        if resp.status == 404:
            return []
        resp.raise_for_status()
        data = await resp.json()
    return sorted(
        item["name"]
        for item in data
        if item.get("type") == "file"
        and item.get("name", "").endswith(".py")
        and not item["name"].startswith("_")
    )


async def get_workspace_notebook(
    fork_full_name: str, access_token: str, filename: str
) -> str | None:
    """Fetch a workspace notebook's source from the fork's `WORKSPACE_BRANCH`.

    `fork_full_name` is the verified `owner/repo` of the fork. Returns the
    decoded UTF-8 source, or None if the file is absent. Used by `/launch` to
    read a notebook's `[tool.stargazer]` resource block before serving the
    pod, and by `/workspace/create` for collision + seed lookups. Non-404
    transport errors propagate so callers can fall back to defaults.
    """
    url = (
        f"{GITHUB_API_BASE}/repos/{fork_full_name}/contents/"
        f"{WORKSPACE_CONTENTS_PATH}/{filename}"
    )
    async with aiohttp.ClientSession() as session:
        resp = await session.get(
            url, headers=_auth_headers(access_token), params={"ref": WORKSPACE_BRANCH}
        )
        if resp.status == 404:
            return None
        resp.raise_for_status()
        data = await resp.json()
        return base64.b64decode(data["content"]).decode("utf-8")


def _auth_headers(access_token: str) -> dict:
    """Standard authenticated GitHub API headers."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def _ensure_ok(resp: aiohttp.ClientResponse, action: str) -> None:
    """Raise a descriptive error if `resp` failed, surfacing GitHub's reason.

    `aiohttp`'s `raise_for_status` only carries the bare status line, which
    hides the actual cause (e.g. missing scope, or `Resource not accessible`).
    Pull GitHub's JSON `message` and the granted token scopes so launch /
    create failures point at the real problem.
    """
    if resp.status < 400:
        return
    try:
        detail = (await resp.json()).get("message", "")
    except Exception:
        detail = (await resp.text())[:200]
    scopes = resp.headers.get("X-OAuth-Scopes", "")
    raise RuntimeError(
        f"{action}: GitHub {resp.status} ({detail}); token scopes=[{scopes}]"
    )


async def create_workspace_notebook(
    fork_full_name: str,
    access_token: str,
    filename: str,
    content: str,
    message: str | None = None,
) -> dict:
    """Create a new notebook file on the fork's `WORKSPACE_BRANCH`.

    `fork_full_name` is the verified `owner/repo` of the fork. As a final
    safety net, refuses to write if it resolves to the upstream source — a
    mis-set fork must never clobber the shared repo. Writes to the literal
    `/repos/{full_name}` path WITHOUT following redirects, so a transfer
    redirect surfaces as an error rather than silently retargeting upstream.
    Assumes the caller has checked the file does not exist (no `sha` is sent,
    so GitHub rejects an overwrite). Returns the Contents API payload.
    """
    if fork_full_name.lower() == upstream_full_name().lower():
        raise RuntimeError(
            f"refusing to write to the upstream source repo {fork_full_name!r}"
        )
    path = f"{WORKSPACE_CONTENTS_PATH}/{filename}"
    payload = {
        "message": message or f"workspace: create {filename}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": WORKSPACE_BRANCH,
    }
    url = f"{GITHUB_API_BASE}/repos/{fork_full_name}/contents/{path}"
    async with aiohttp.ClientSession() as session:
        resp = await session.put(
            url, headers=_auth_headers(access_token), json=payload, allow_redirects=False
        )
        if 300 <= resp.status < 400:
            raise RuntimeError(
                f"write notebook: {fork_full_name!r} redirected "
                f"(HTTP {resp.status}) — not a writable fork path"
            )
        await _ensure_ok(resp, "write notebook")
        return await resp.json()
