"""Unit-test fixtures for the app tier."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import config, deploy

# The issuer the tests' tokens name, standing in for Union's sign-in service.
UNION_ISSUER = "https://signin.example.test"


@pytest.fixture(autouse=True)
def deployed_notebook_image(monkeypatch):
    """Stand in for the notebook image URI a real deploy bakes into the admin pod."""
    monkeypatch.setattr(config, "NOTEBOOK_IMAGE", "test.example/notebook-app:unit")


@pytest.fixture
def served_dashboard(monkeypatch) -> dict:
    """Fake the dashboard serve; return what `deploy_dashboard` serves.

    The dict fills with `ctx` (the serve context's arguments), `env`, a copy of
    its `env_vars` and its `domain`. Nothing reaches a cluster, the notebook
    image is a stand-in URI and the deployer has no Flyte org.
    """
    served = {}

    def fake_servecontext(**ctx):
        """Stand in for `flyte.with_servecontext`, keeping its arguments."""

        def serve(env):
            """Record the served env and answer with its endpoint."""
            served.update(
                ctx=ctx, env=env, env_vars=dict(env.env_vars), domain=env.domain
            )
            return SimpleNamespace(endpoint="https://u-jane.apps.example")

        return SimpleNamespace(serve=serve)

    monkeypatch.setattr(deploy.flyte, "with_servecontext", fake_servecontext)
    monkeypatch.setattr(deploy, "_notebook_image", lambda: "reg/notebook-app:h1")
    monkeypatch.setattr(deploy, "get_init_config", lambda: SimpleNamespace(org=None))
    return served


@pytest.fixture
def workspace_root(tmp_path, monkeypatch):
    """Point the workspace store at a fresh local directory."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", str(tmp_path / "store"))


@pytest.fixture
def union(monkeypatch):
    """Run as the hosted Union deploy."""
    monkeypatch.setattr(config, "TARGET", "union")


@pytest.fixture
def devbox(monkeypatch):
    """Run as the local devbox deploy."""
    monkeypatch.setattr(config, "TARGET", "devbox")


@pytest.fixture(scope="session")
def union_signer():
    """Signs tokens the way Union's login does: `sign(subject, ...)` -> a JWT.

    `sign.public_key` verifies them. `iss`, `expires_in` and `key` override the
    issuer, the lifetime in seconds (negative for an expired token) and the
    signing key.
    """
    own = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def sign(sub, *, iss=UNION_ISSUER, expires_in=3600, key=None):
        """A signed token for `sub`."""
        now = int(time.time())
        claims = {"iss": iss, "sub": sub, "iat": now, "exp": now + expires_in}
        return jwt.encode(claims, key or own, algorithm="RS256")

    sign.issuer = UNION_ISSUER
    sign.public_key = own.public_key()
    sign.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return sign
