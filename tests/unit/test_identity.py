"""Tests for `app.identity`: who is signed in, read from Union's headers.

Union's auth layer gates every request and forwards the signed-in user as
`X-User-*` headers. Claim values arrive JSON-encoded (`"\"a@b.c\""`); the
subject arrives bare. Union alone decides who may open a dashboard; state is
keyed by the dashboard's owner (`config.OWNER_SUBJECT`), whoever is viewing.
"""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import config
from app.identity import User, current_user, user_from_request

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


def test_current_user_is_the_owner_for_the_owner(monkeypatch):
    """The owner's request yields the owner, named from the claim headers."""
    monkeypatch.setattr(config, "OWNER_SUBJECT", OWNER)
    user = current_user(
        _request({"X-User-Subject": OWNER, "X-User-Claim-Name": '"Pryce User"'})
    )
    assert user == User(OWNER, "", "Pryce User")


def test_current_user_keys_an_admin_to_the_owner_but_keeps_their_name(monkeypatch):
    """A different signed-in visitor acts on the owner's state, shown by name."""
    monkeypatch.setattr(config, "OWNER_SUBJECT", OWNER)
    user = current_user(
        _request({"X-User-Subject": "111111111111111111", "X-User-Claim-Name": '"Adm"'})
    )
    assert user == User(OWNER, "", "Adm")


def test_current_user_without_a_configured_owner_uses_the_visitor(monkeypatch):
    """A local run (no owner baked in) keys state by the visitor's subject."""
    monkeypatch.setattr(config, "OWNER_SUBJECT", "")
    assert current_user(_request({"X-User-Subject": "42"})) == User("42")


def test_current_user_without_identity_is_401(monkeypatch):
    """No forwarded subject is not signed in."""
    monkeypatch.setattr(config, "OWNER_SUBJECT", OWNER)
    with pytest.raises(HTTPException) as exc:
        current_user(_request({}))
    assert exc.value.status_code == 401


def test_display_prefers_name_then_email_then_subject():
    """The label shown in the UI falls back sensibly."""
    assert User("1", "a@b.c", "Ann").display == "Ann"
    assert User("1", "a@b.c", "").display == "a@b.c"
    assert User("1", "", "").display == "1"


def test_initial_is_first_letter_uppercased():
    """The avatar initial comes from the display label."""
    assert User("1", "", "ann lee").initial == "A"
