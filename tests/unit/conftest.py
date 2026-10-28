"""Unit-test fixtures for the notebook runtime."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

# The issuer the tests' tokens name, standing in for Union's sign-in service.
UNION_ISSUER = "https://signin.example.test"


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
