"""
### GitHub repo operations beyond OAuth.

Currently scoped to forking upstream `stargazer` into the authenticated
user's account. Idempotent — calling `fork_upstream` when a fork already
exists returns the existing one rather than erroring.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os

import aiohttp


GITHUB_API_BASE = "https://api.github.com"


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


def fork_clone_url(fork_owner: str, access_token: str) -> str:
    """Build an authenticated HTTPS clone URL for the user's fork.

    Uses GitHub's `x-access-token` username convention so HTTP basic-auth
    works without per-clone token files. Suitable for `git clone` /
    `git push` inside pods.
    """
    _, name = upstream_repo()
    return f"https://x-access-token:{access_token}@github.com/{fork_owner}/{name}.git"


async def list_workspace(fork_owner: str, access_token: str) -> list[str]:
    """List `.py` files under `notebooks/workspace/` in the user's fork.

    Cold-case fallback used by the admin dashboard when no per-notebook
    pod is up for the user. Reads from the `workspace` branch (where the
    proxy's `/__sg__/workspace/sync` pushes). Returns an empty list if
    the directory or branch doesn't exist yet.
    """
    _, repo_name = upstream_repo()
    url = (
        f"{GITHUB_API_BASE}/repos/{fork_owner}/{repo_name}/contents/"
        "src/stargazer/notebooks/workspace"
    )
    async with aiohttp.ClientSession() as session:
        resp = await session.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params={"ref": "workspace"},
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
