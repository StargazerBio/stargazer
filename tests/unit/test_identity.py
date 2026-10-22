"""Tests for `app.identity`: who is signed in, read from Union's headers.

Union's auth layer gates every request and forwards the signed-in user as
`X-User-*` headers. Claim values arrive JSON-encoded (`"\"a@b.c\""`); the
subject arrives bare. State is keyed by the dashboard's owner
(`config.OWNER_SUBJECT`), whoever is viewing. On Union (`config.AUTH_ISSUER`
set) only the signed `X-User-Token` counts, since an app's in-cluster address
skips the login and takes any header, and only the owner and the admins get in.
"""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import config, identity
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


def test_a_deploy_without_a_login_can_name_a_stand_in(monkeypatch):
    """With no login in front, a request without a subject is the stand-in."""
    monkeypatch.setattr(config, "STAND_IN_SUBJECT", "devbox-user")
    assert user_from_request(_request({})) == User("devbox-user")


def test_a_forwarded_identity_beats_the_stand_in(monkeypatch):
    """A subject header, when there is one, is still who's signed in."""
    monkeypatch.setattr(config, "STAND_IN_SUBJECT", "devbox-user")
    user = user_from_request(_request({"X-User-Subject": OWNER}))
    assert user is not None and user.subject == OWNER


def test_the_stand_in_is_never_honored_on_union():
    """Union's login always forwards a subject; set there, the variable does nothing."""
    assert (
        config.stand_in_subject(
            {"STARGAZER_TARGET": "devbox", "SG_STAND_IN_SUBJECT": "devbox-user"}
        )
        == "devbox-user"
    )
    assert (
        config.stand_in_subject(
            {"STARGAZER_TARGET": "union", "SG_STAND_IN_SUBJECT": "devbox-user"}
        )
        == ""
    )
    assert config.stand_in_subject({"STARGAZER_TARGET": "devbox"}) == ""


@pytest.fixture
def on_union(monkeypatch, union_signer):
    """Token checks on, against the test signer, for a dashboard OWNER owns."""
    monkeypatch.setattr(config, "AUTH_ISSUER", union_signer.issuer)
    monkeypatch.setattr(config, "OWNER_SUBJECT", OWNER)
    monkeypatch.setattr(config, "ADMIN_SUBJECTS", frozenset())
    monkeypatch.setattr(identity, "_signing_key", lambda token: union_signer.public_key)
    return union_signer


def test_on_union_the_subject_comes_from_the_signed_token(on_union):
    """The token's subject wins over a subject header that disagrees."""
    user = user_from_request(
        _request(
            {
                "X-User-Token": f"IDToken {on_union(OWNER)}",
                "X-User-Subject": "999999999999999999",
                "X-User-Claim-Name": '"Pryce User"',
            }
        )
    )
    assert user == User(OWNER, "", "Pryce User")


def test_on_union_a_bearer_token_counts_too(on_union):
    """A CLI or API caller's access token arrives as `Bearer <jwt>`."""
    user = user_from_request(_request({"X-User-Token": f"Bearer {on_union(OWNER)}"}))
    assert user == User(OWNER)


def test_on_union_a_subject_header_without_a_token_is_anonymous(on_union):
    """What a pod can send to the in-cluster address: headers, no signed token."""
    assert user_from_request(_request({"X-User-Subject": OWNER})) is None


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("not.a.jwt", id="garbage"),
        pytest.param("other-key", id="signed-by-another-key"),
        pytest.param("expired", id="expired"),
        pytest.param("other-issuer", id="another-issuer"),
    ],
)
def test_on_union_a_bad_token_is_anonymous(on_union, token):
    """Only an unexpired token Union's issuer signed identifies anyone, whatever
    subject header comes with it."""
    made = {
        "not.a.jwt": "not.a.jwt",
        "other-key": on_union(OWNER, key=on_union.other_key),
        "expired": on_union(OWNER, expires_in=-3600),
        "other-issuer": on_union(OWNER, iss="https://elsewhere.example.test"),
    }[token]
    forged = {"X-User-Token": f"IDToken {made}", "X-User-Subject": OWNER}
    assert user_from_request(_request(forged)) is None


def test_on_union_a_stranger_is_refused(on_union):
    """A valid token for someone who isn't the owner or an admin is a 403."""
    with pytest.raises(HTTPException) as exc:
        current_user(
            _request({"X-User-Token": f"IDToken {on_union('222222222222222222')}"})
        )
    assert exc.value.status_code == 403


def test_on_union_an_admin_gets_the_owners_dashboard(on_union, monkeypatch):
    """A listed admin is keyed to the owner, like the owner is."""
    monkeypatch.setattr(config, "ADMIN_SUBJECTS", frozenset({"111111111111111111"}))
    user = current_user(
        _request({"X-User-Token": f"Bearer {on_union('111111111111111111')}"})
    )
    assert user.subject == OWNER


def test_on_union_no_token_is_401(on_union):
    """Forged headers and no token: not signed in."""
    with pytest.raises(HTTPException) as exc:
        current_user(_request({"X-User-Subject": OWNER}))
    assert exc.value.status_code == 401


def test_the_issuer_is_unions_on_union_and_unset_elsewhere():
    """Token checks are on for Union deploys and off where there's no login."""
    assert config.auth_issuer({"STARGAZER_TARGET": "union"})
    assert config.auth_issuer({"STARGAZER_TARGET": "devbox"}) == ""


def test_admin_subjects_are_a_comma_separated_list():
    """`STARGAZER_ADMIN_SUBJECTS`, spaces and empty entries ignored."""
    assert config.admin_subjects({"STARGAZER_ADMIN_SUBJECTS": " 1, 2,,"}) == {"1", "2"}
    assert config.admin_subjects({}) == frozenset()
