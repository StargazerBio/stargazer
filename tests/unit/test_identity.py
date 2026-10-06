"""Tests for `app.identity`: who is signed in, read from Union's headers.

Union's auth layer gates every request and forwards the signed-in user as
`X-User-*` headers. Claim values arrive JSON-encoded (`"\"a@b.c\""`); the
subject arrives bare. A dashboard serves one owner (`config.OWNER_SUBJECT`);
everyone else, and every request when the owner is unset, is refused.
"""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import config
from app.identity import User, require_owner, user_from_request

OWNER = "387300641116005877"


def _request(headers: dict[str, str]) -> Request:
    """A bare ASGI request carrying `headers`."""
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw})


def test_reads_subject_and_decodes_claims():
    """Subject is taken as-is; JSON-quoted claims are decoded."""
    user = user_from_request(
        _request(
            {
                "X-User-Subject": "387300641116005877",
                "X-User-Claim-Email": '"pryce@stargazer.bio"',
                "X-User-Claim-Name": '"Pryce User"',
            }
        )
    )
    assert user == User("387300641116005877", "pryce@stargazer.bio", "Pryce User")


def test_unquoted_claims_pass_through():
    """A claim that isn't JSON-encoded is used verbatim."""
    user = user_from_request(
        _request({"X-User-Subject": "42", "X-User-Claim-Name": "Plain Name"})
    )
    assert user == User("42", "", "Plain Name")


def test_no_subject_is_anonymous():
    """Without a subject header there is no user."""
    assert user_from_request(_request({"X-User-Claim-Name": '"x"'})) is None


def test_require_owner_returns_the_owner_with_display_details(monkeypatch):
    """The owner's request yields the owner, named from the claim headers."""
    monkeypatch.setattr(config, "OWNER_SUBJECT", OWNER)
    user = require_owner(
        _request({"X-User-Subject": OWNER, "X-User-Claim-Name": '"Pryce User"'})
    )
    assert user == User(OWNER, "", "Pryce User")


@pytest.mark.parametrize(
    ("owner", "headers"),
    [
        (OWNER, {"X-User-Subject": "111111111111111111"}),  # someone else
        (OWNER, {}),  # no identity forwarded
        ("", {"X-User-Subject": OWNER}),  # owner not configured: fail closed
        ("", {}),
    ],
)
def test_require_owner_refuses_everyone_else_with_403(monkeypatch, owner, headers):
    """Only the configured owner gets through; an unset owner admits nobody."""
    monkeypatch.setattr(config, "OWNER_SUBJECT", owner)
    with pytest.raises(HTTPException) as exc:
        require_owner(_request(headers))
    assert exc.value.status_code == 403


def test_display_prefers_name_then_email_then_subject():
    """The label shown in the UI falls back sensibly."""
    assert User("1", "a@b.c", "Ann").display == "Ann"
    assert User("1", "a@b.c", "").display == "a@b.c"
    assert User("1", "", "").display == "1"


def test_initial_is_first_letter_uppercased():
    """The avatar initial comes from the display label."""
    assert User("1", "", "ann lee").initial == "A"
