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

The publisher's contract: `POST <url>/sign` with JSON `{filename, keyvalues}`
answers `{url, keyvalues}`, the signed URL and the keyvalues it binds.

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

    async def sign(self, filename: str, keyvalues: dict[str, str]) -> dict:
        """A signed upload URL for one public file.

        Args:
            filename: The name the file lands with
            keyvalues: Its metadata; the publisher restamps `_owner`

        Returns:
            `{url, keyvalues}`: where to upload the bytes, and the keyvalues
            the file will carry

        Raises:
            ValueError: when there are no AWS credentials to sign with
        """
        credentials = self._session.get_credentials()
        if credentials is None:
            raise ValueError(
                "STARGAZER_PUBLISHER_URL is set but there are no AWS credentials "
                "to sign with: publishing runs as the user's own role"
            )
        # The bytes sent must be the bytes signed.
        body = json.dumps({"filename": filename, "keyvalues": keyvalues}).encode()
        request = AWSRequest(
            method="POST",
            url=f"{self.url}/sign",
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
