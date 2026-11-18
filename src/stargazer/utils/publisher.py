"""
### Client for the publisher, which signs public uploads.

On a hosted tenant the key that can write to Pinata's public network lives
only in the publisher, a Lambda no user's code runs beside. A pod holds a
read key: it queries the public tier itself, and to publish it asks the
publisher for a signed upload URL per file, then uploads the bytes there
(`stargazer.utils.pinata.upload_signed`). The publisher stamps `_owner` from
the caller, so a pod can only publish as its own user.

The pod proves who it is with its own AWS role: the publisher's function URL
takes only SigV4-signed requests, and each user's pods run as that user's
role, so the request is signed with the pod's credentials (boto3's usual
chain, the web identity token Flyte's project settings point it at).

The publisher's contract, each a JSON `POST`: `/sign` with
`{filename, keyvalues}` answers `{url, keyvalues}`, the signed URL and the
keyvalues it binds; `/update` with `{cid, keyvalues}` and `/delete` with
`{cid}` act on the caller's own public file for `cid`. The SDK only signs;
the dashboard also edits and deletes.

Without `STARGAZER_PUBLISHER_URL` there's no publisher, and a public tier
with a full key publishes directly (locally, on the devbox).

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import json
import os
from urllib.parse import urlparse

import aiohttp
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


class PublisherClient:
    """Asks the publisher for signed upload URLs, as the pod's own AWS role."""

    def __init__(self, url: str, region: str, session: boto3.Session | None = None):
        """A client for the publisher at `url`, signing for `region`.

        Args:
            url: The publisher's function URL
            region: The AWS region its signatures are scoped to
            session: Where credentials come from (defaults to boto3's chain)
        """
        self.url = url.rstrip("/")
        self.region = region
        self._session = session or boto3.Session()

    @classmethod
    def from_env(cls) -> PublisherClient | None:
        """The client for `STARGAZER_PUBLISHER_URL`, or None when it isn't set."""
        url = os.environ.get("STARGAZER_PUBLISHER_URL")
        if not url:
            return None
        # A function URL is https://<id>.lambda-url.<region>.on.aws/
        region = urlparse(url).hostname.split(".")[2]
        return cls(url, region)

    async def _post(self, route: str, payload: dict) -> dict:
        """POST `payload` to `route`, SigV4-signed with the session's credentials.

        Raises:
            ValueError: when there are no AWS credentials to sign with
            aiohttp.ClientResponseError: when the publisher refuses (403: not
                the caller's file, or not a user's role)
        """
        credentials = self._session.get_credentials()
        if credentials is None:
            raise ValueError(
                "STARGAZER_PUBLISHER_URL is set but there are no AWS credentials "
                "to sign with: publishing runs as the user's own role"
            )
        # The bytes sent must be the bytes signed.
        body = json.dumps(payload).encode()
        request = AWSRequest(
            method="POST",
            url=f"{self.url}{route}",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        SigV4Auth(credentials.get_frozen_credentials(), "lambda", self.region).add_auth(
            request
        )
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                request.url, data=body, headers=dict(request.headers.items())
            ) as response,
        ):
            response.raise_for_status()
            return await response.json()

    async def sign(self, filename: str, keyvalues: dict[str, str]) -> dict:
        """A signed upload URL for one public file.

        Args:
            filename: The name the file lands with
            keyvalues: Its metadata; the publisher restamps `_owner`

        Returns:
            `{url, keyvalues}`: where to upload the bytes, and the keyvalues
            the file will carry
        """
        return await self._post("/sign", {"filename": filename, "keyvalues": keyvalues})

    async def update(self, cid: str, keyvalues: dict[str, str]) -> dict:
        """Merge keyvalues onto the caller's own public file for `cid`.

        Returns:
            The updated record: `{cid, name, keyvalues, network}`
        """
        return await self._post("/update", {"cid": cid, "keyvalues": keyvalues})

    async def delete(self, cid: str) -> dict:
        """Delete the caller's own public file for `cid`."""
        return await self._post("/delete", {"cid": cid})
