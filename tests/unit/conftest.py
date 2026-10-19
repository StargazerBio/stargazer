"""Unit-test fixtures for the app tier."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import config

# The issuer the tests' tokens name, standing in for Union's sign-in service.
UNION_ISSUER = "https://signin.example.test"


@pytest.fixture(autouse=True)
def deployed_notebook_image(monkeypatch):
    """Stand in for the notebook image URI a real deploy bakes into the admin pod."""
    monkeypatch.setattr(config, "NOTEBOOK_IMAGE", "test.example/notebook-app:unit")


@pytest.fixture(scope="session")
def union_signer():
    """Signs tokens the way Union's login does: `sign(subject, ...)` -> a JWT.

    `sign.public_key` verifies them. `iss`, `expires_in` and `key` override the
    issuer, the lifetime in seconds (negative for an expired token) and the
    signing key.
    """
    own = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def sign(sub, *, iss=UNION_ISSUER, expires_in=3600, key=None):
        now = int(time.time())
        claims = {"iss": iss, "sub": sub, "iat": now, "exp": now + expires_in}
        return jwt.encode(claims, key or own, algorithm="RS256")

    sign.public_key = own.public_key()
    sign.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return sign
