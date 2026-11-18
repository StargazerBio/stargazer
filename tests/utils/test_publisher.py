"""Tests for the publisher client, against a local stand-in for the publisher's function URL."""

import json

import boto3
from aiohttp import web
from aiohttp.test_utils import TestServer

from stargazer.utils.publisher import PublisherClient

SIGNED = {
    "url": "https://uploads.example/v3/files/signed-1",
    "keyvalues": {"asset": "reference", "_owner": "subject-1"},
}


def _service(seen: list) -> web.Application:
    """The publisher's `/sign`, logging each request's headers and body."""

    async def sign(request):
        seen.append((dict(request.headers), await request.read()))
        return web.json_response(SIGNED)

    async def update(request):
        seen.append((request.path, json.loads(await request.read())))
        return web.json_response({"cid": "bafy1", "keyvalues": {"_owner": "s"}})

    async def delete(request):
        seen.append((request.path, json.loads(await request.read())))
        return web.json_response({"cid": "bafy1"})

    app = web.Application()
    app.router.add_post("/sign", sign)
    app.router.add_post("/update", update)
    app.router.add_post("/delete", delete)
    return app


def _session() -> boto3.Session:
    """Static credentials, standing in for a pod's role."""
    return boto3.Session(
        aws_access_key_id="AKIDPOD",
        aws_secret_access_key="secret",
        aws_session_token="session-token",
    )


async def test_sign_sends_the_files_metadata_signed_with_the_pods_role():
    """Each request is SigV4-signed for Lambda with the pod's credentials, over the body it sends."""
    seen: list = []
    session = boto3.Session(
        aws_access_key_id="AKIDPOD",
        aws_secret_access_key="secret",
        aws_session_token="session-token",
    )
    async with TestServer(_service(seen)) as server:
        client = PublisherClient(
            str(server.make_url("")), region="us-west-2", session=session
        )

        first = await client.sign("ref.fa", {"asset": "reference", "_owner": "me"})

    assert first == SIGNED
    [(headers, body)] = seen
    assert json.loads(body) == {
        "filename": "ref.fa",
        "keyvalues": {"asset": "reference", "_owner": "me"},
    }
    assert headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIDPOD/")
    assert "/us-west-2/lambda/aws4_request" in headers["Authorization"]
    assert headers["X-Amz-Security-Token"] == "session-token"


async def test_update_and_delete_post_to_their_routes():
    """Edits and deletes of the caller's own public files go to the publisher too."""
    seen: list = []
    async with TestServer(_service(seen)) as server:
        client = PublisherClient(
            str(server.make_url("")), region="us-west-2", session=_session()
        )

        updated = await client.update("bafy1", {"build": "hg38"})
        deleted = await client.delete("bafy1")

    assert updated == {"cid": "bafy1", "keyvalues": {"_owner": "s"}}
    assert deleted == {"cid": "bafy1"}
    assert seen == [
        ("/update", {"cid": "bafy1", "keyvalues": {"build": "hg38"}}),
        ("/delete", {"cid": "bafy1"}),
    ]


def test_from_env_reads_the_url_and_its_region(monkeypatch):
    """The function URL names its region, which the signature is scoped to."""
    monkeypatch.setenv(
        "STARGAZER_PUBLISHER_URL", "https://abc123.lambda-url.us-west-2.on.aws/"
    )

    client = PublisherClient.from_env()

    assert (client.url, client.region) == (
        "https://abc123.lambda-url.us-west-2.on.aws",
        "us-west-2",
    )


def test_from_env_is_none_without_a_service(monkeypatch):
    """Without a publisher (locally, on the devbox) the pod publishes with the full key."""
    monkeypatch.delenv("STARGAZER_PUBLISHER_URL", raising=False)

    assert PublisherClient.from_env() is None
