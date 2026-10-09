"""Fixtures for the pinata tier (`uv run --all-extras pytest -m pinata`).

These tests call the real Pinata API with the key in tests/.secrets/pinata_jwt.
The root conftest strips PINATA_JWT before anything imports stargazer; each
test here gets it back for its own duration.
"""

import pytest
from conftest import SECRETS_DIR


@pytest.fixture(autouse=True)
def pinata_jwt(monkeypatch):
    """Set PINATA_JWT from tests/.secrets/pinata_jwt for the test.

    A run without the key fails rather than skipping, so it can't pass by
    testing nothing.
    """
    jwt_file = SECRETS_DIR / "pinata_jwt"
    if not jwt_file.exists():
        pytest.fail(f"Pinata JWT not found — put your token in {jwt_file}")
    jwt = jwt_file.read_text().strip()
    if not jwt:
        pytest.fail(f"Pinata JWT file is empty: {jwt_file}")
    monkeypatch.setenv("PINATA_JWT", jwt)
