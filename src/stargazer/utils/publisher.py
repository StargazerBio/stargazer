"""
### Client for the publisher service, which signs public uploads.

On a hosted tenant the key that can write to Pinata's public network lives
only in the publisher service, in a project no user runs code in. A pod
holds a read key: it queries the public tier itself, and to publish it asks
the service for a signed upload URL per file, then uploads the bytes there
(`stargazer.utils.pinata.upload_signed`). The service stamps `_owner` from
the caller, so a pod can only publish as its own project's owner.

The pod proves who it is with its project's API key, the one Flyte's
in-cluster client already uses (`_UNION_EAGER_API_KEY`): the key is traded
for a token at the tenant's token endpoint (OAuth client credentials), and
the token goes to the service as a bearer.

The service's contract: `POST <url>/sign` with JSON `{filename, keyvalues}`
answers `{url, keyvalues}`, the signed URL and the keyvalues it binds.

Without `STARGAZER_PUBLISHER_URL` there's no service, and a public tier
with a full key publishes directly (locally, on the devbox).

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import base64
import os
import time

import aiohttp

# The variable Flyte's in-cluster client reads the project's key from, which
# `STARGAZER_SECRETS` declares.
API_KEY_VAR = "_UNION_EAGER_API_KEY"

# Renew a token this long before Union says it expires.
_TOKEN_MARGIN_SECONDS = 60


class PublisherClient:
    """Asks the publisher service for signed upload URLs, as the pod's project."""

    def __init__(
        self, url: str, token_endpoint: str, client_id: str, client_secret: str
    ):
        """A client for the service at `url`, authenticating as the key's client.

        Args:
            url: The publisher service's base URL
            token_endpoint: The tenant's OAuth token endpoint
            client_id: The project key's client id
            client_secret: The project key's secret
        """
        self.url = url.rstrip("/")
        self.token_endpoint = token_endpoint
        self.client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._token_expires = 0.0

    @classmethod
    def from_env(cls) -> PublisherClient | None:
        """The client `STARGAZER_PUBLISHER_URL` and the pod's project key name, or None.

        Raises:
            ValueError: when the service is set but the pod has no project key
        """
        url = os.environ.get("STARGAZER_PUBLISHER_URL")
        if not url:
            return None
        key = os.environ.get(API_KEY_VAR)
        if not key:
            raise ValueError(
                f"STARGAZER_PUBLISHER_URL is set but {API_KEY_VAR} isn't: the "
                "publisher needs the project's API key (STARGAZER_API_KEY_SECRET)"
            )
        # A Union API key is base64("<endpoint>:<client id>:<secret>:<org>"),
        # and the endpoint may carry a `dns:///` prefix with colons of its own.
        endpoint, client_id, secret, _ = base64.b64decode(key).decode().rsplit(":", 3)
        host = endpoint.removeprefix("dns:///")
        # The tenant's OAuth metadata names this endpoint (measured 2026-11-18).
        return cls(url, f"https://{host}/auth/token", client_id, secret)

    async def _bearer(self, session: aiohttp.ClientSession) -> str:
        """A token for the project's key, reused until shortly before it expires."""
        if self._token and time.monotonic() < self._token_expires:
            return self._token
        async with session.post(
            self.token_endpoint,
            auth=aiohttp.BasicAuth(self.client_id, self._client_secret),
            data={"grant_type": "client_credentials", "scope": "all"},
        ) as response:
            response.raise_for_status()
            body = await response.json()
        self._token = body["access_token"]
        self._token_expires = (
            time.monotonic() + body["expires_in"] - _TOKEN_MARGIN_SECONDS
        )
        return self._token

    async def sign(self, filename: str, keyvalues: dict[str, str]) -> dict:
        """A signed upload URL for one public file.

        Args:
            filename: The name the file lands with
            keyvalues: Its metadata; the service restamps `_owner`

        Returns:
            `{url, keyvalues}`: where to upload the bytes, and the keyvalues
            the file will carry
        """
        async with aiohttp.ClientSession() as session:
            bearer = await self._bearer(session)
            async with session.post(
                f"{self.url}/sign",
                headers={"Authorization": f"Bearer {bearer}"},
                json={"filename": filename, "keyvalues": keyvalues},
            ) as response:
                response.raise_for_status()
                return await response.json()
