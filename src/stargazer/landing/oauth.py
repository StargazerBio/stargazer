"""
### GitHub OAuth helpers.

Handles the authorization URL construction, code-for-token exchange,
and authenticated user profile fetch against the GitHub API.

spec: [docs/architecture/landing.md](../../docs/architecture/landing.md)
"""

import urllib.parse

import aiohttp


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


def github_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Build the GitHub OAuth authorization URL.

    Requests read:user scope to access the authenticated user's profile.
    """
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user",
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> str:
    """Exchange an authorization code for an access token.

    Returns the access token string. Raises ValueError on failure.
    """
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        data = await resp.json()

    if "access_token" not in data:
        error = data.get("error_description", data.get("error", "unknown error"))
        raise ValueError(f"GitHub token exchange failed: {error}")

    return data["access_token"]


async def get_github_user(access_token: str) -> dict:
    """Fetch the authenticated GitHub user's profile.

    Returns a dict with at least 'login' (username) and 'id' (numeric).
    """
    async with aiohttp.ClientSession() as session:
        resp = await session.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        return await resp.json()
