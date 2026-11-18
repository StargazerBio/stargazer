"""Tests for the publisher client, against a local stand-in for the service and Union's token endpoint."""

import base64

from aiohttp import web
from aiohttp.test_utils import TestServer

from stargazer.utils.publisher import PublisherClient


def _service(seen: dict) -> web.Application:
    """Union's token endpoint and the publisher's `/sign`, logging what they get."""

    async def token(request):
        form = await request.post()
        seen.setdefault("tokens", []).append(
            (request.headers["Authorization"], form["grant_type"], form["scope"])
        )
        return web.json_response({"access_token": "tok-1", "expires_in": 3600})

    async def sign(request):
        seen.setdefault("signs", []).append(
            (request.headers["Authorization"], await request.json())
        )
        return web.json_response(
            {
                "url": "https://uploads.example/v3/files/signed-1",
                "keyvalues": {"asset": "reference", "_owner": "subject-1"},
            }
        )

    app = web.Application()
    app.router.add_post("/auth/token", token)
    app.router.add_post("/sign", sign)
    return app


async def test_sign_sends_the_files_metadata_with_a_token_from_the_project_key():
    """The pod trades its project key for a token once, and gets a signed URL per file."""
    seen: dict = {}
    async with TestServer(_service(seen)) as server:
        client = PublisherClient(
            url=str(server.make_url("")).rstrip("/"),
            token_endpoint=str(server.make_url("/auth/token")),
            client_id="client-1",
            client_secret="secret-1",
        )

        first = await client.sign("ref.fa", {"asset": "reference", "_owner": "me"})
        await client.sign("ref.fa.fai", {"asset": "reference_index"})

    assert first == {
        "url": "https://uploads.example/v3/files/signed-1",
        "keyvalues": {"asset": "reference", "_owner": "subject-1"},
    }
    basic = "Basic " + base64.b64encode(b"client-1:secret-1").decode()
    assert seen["tokens"] == [(basic, "client_credentials", "all")]
    assert seen["signs"] == [
        (
            "Bearer tok-1",
            {"filename": "ref.fa", "keyvalues": {"asset": "reference", "_owner": "me"}},
        ),
        (
            "Bearer tok-1",
            {"filename": "ref.fa.fai", "keyvalues": {"asset": "reference_index"}},
        ),
    ]


def test_from_env_reads_the_service_and_the_project_key(monkeypatch):
    """The publisher's URL and the pod's project key (Flyte's own variable) configure it."""
    key = base64.b64encode(b"dns:///tenant.example:client-1:secret-1:org-1").decode()
    monkeypatch.setenv("STARGAZER_PUBLISHER_URL", "https://publisher.example/")
    monkeypatch.setenv("_UNION_EAGER_API_KEY", key)

    client = PublisherClient.from_env()

    assert (client.url, client.token_endpoint, client.client_id) == (
        "https://publisher.example",
        "https://tenant.example/auth/token",
        "client-1",
    )


def test_from_env_is_none_without_a_service(monkeypatch):
    """Without a publisher (locally, on the devbox) the pod publishes with the full key."""
    monkeypatch.delenv("STARGAZER_PUBLISHER_URL", raising=False)

    assert PublisherClient.from_env() is None
