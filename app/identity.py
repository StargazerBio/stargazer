"""
### Who is signed in — read from Union's auth layer.

Every dashboard and notebook pod runs behind Union's login
(`requires_auth=True`). Union gates each request and forwards the signed-in
user as headers it sets itself, overwriting anything a client sends:

- `X-User-Subject` — the stable Union user id. The key for everything
  per-user: Flyte project, workspace store prefix, asset `_owner`.
- `X-User-Claim-Email`, `X-User-Claim-Name` — display only. Claim values
  arrive JSON-encoded (`"\"a@b.c\""`).
- `X-User-Token` — `IDToken <jwt>` from a browser, `Bearer <jwt>` from the CLI
  or an API key: the signed token the login checked.

Those headers are only trustworthy through the app's public address. Every app
also answers at an in-cluster address that skips the login, and any pod in any
project can send it whatever headers it likes (measured 2026-10-18). So on
Union (`config.AUTH_ISSUER` set) only the token counts: its signature is
checked against the issuer's published keys, and the subject is its `sub`. The
visitor must then be the dashboard's owner or one of `config.ADMIN_SUBJECTS`,
standing in for Union's own check that they can view the project. Elsewhere,
with no login in front, the headers are taken as they come.

There is no session cookie and no sign-in route of our own: Union owns both.

A deploy with no login in front of it can name a stand-in user
(`config.STAND_IN_SUBJECT`) for requests that arrive without a subject.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import json
from dataclasses import dataclass, replace
from functools import cache
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, HTTPException, Request

from app import config

SUBJECT_HEADER = "X-User-Subject"
EMAIL_HEADER = "X-User-Claim-Email"
NAME_HEADER = "X-User-Claim-Name"
TOKEN_HEADER = "X-User-Token"
# Clock skew allowed on a token's expiry and not-before times.
_LEEWAY_SECONDS = 60


@dataclass(frozen=True)
class User:
    """The signed-in user. `subject` keys all per-user state."""

    subject: str
    email: str = ""
    name: str = ""

    @property
    def display(self) -> str:
        """The label shown in the UI: name, else email, else the subject."""
        return self.name or self.email or self.subject

    @property
    def initial(self) -> str:
        """One uppercase letter for the avatar."""
        return self.display[:1].upper()


def _claim(raw: str | None) -> str:
    """Decode a JSON-encoded claim value; pass through anything else."""
    if not raw:
        return ""
    try:
        value = json.loads(raw)
    except ValueError:
        return raw
    return value if isinstance(value, str) else raw


@cache
def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    """The issuer's signing keys, found from its discovery document."""
    discovery = httpx.get(f"{issuer}/.well-known/openid-configuration", timeout=10)
    discovery.raise_for_status()
    # An hour between refreshes: a token signed by a key not yet cached
    # refetches the set anyway, and the first fetch blocks the request.
    return jwt.PyJWKClient(discovery.json()["jwks_uri"], lifespan=3600)


def _signing_key(token: str):
    """The issuer's public key that signed `token`."""
    return _jwks_client(config.AUTH_ISSUER).get_signing_key_from_jwt(token).key


def _token_subject(request: Request) -> str | None:
    """The `sub` of the request's `X-User-Token`, if the issuer signed it and
    it hasn't expired; else None."""
    _, _, token = request.headers.get(TOKEN_HEADER, "").partition(" ")
    if not token:
        return None
    try:
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            issuer=config.AUTH_ISSUER,
            leeway=_LEEWAY_SECONDS,
            options={"require": ["exp", "iss", "sub"], "verify_aud": False},
        )
    except jwt.PyJWTError:
        return None
    return claims["sub"]


def user_from_request(request: Request) -> User | None:
    """The signed-in user, or None when there's no identity to go on.

    On Union the subject is the signed token's (see the module docstring).
    Elsewhere it's the subject header, and with a stand-in configured, a
    request with no subject is that user.
    """
    if config.AUTH_ISSUER:
        subject = _token_subject(request) or ""
    else:
        subject = request.headers.get(SUBJECT_HEADER, "").strip()
    if not subject:
        if config.STAND_IN_SUBJECT:
            return User(subject=config.STAND_IN_SUBJECT)
        return None
    return User(
        subject=subject,
        email=_claim(request.headers.get(EMAIL_HEADER)),
        name=_claim(request.headers.get(NAME_HEADER)),
    )


def current_user(request: Request) -> User:
    """FastAPI dependency: the signed-in user, else a 401.

    On Union only the owner and `config.ADMIN_SUBJECTS` get in; anyone else
    signed in is a 403. Elsewhere whoever arrives does. State is keyed by the
    dashboard's owner (`config.OWNER_SUBJECT`, baked in at deploy), not the
    visitor, so an admin sees the owner's notebooks. The visitor's name and
    email are kept for display. With no owner configured (a local run) the
    visitor's own subject is the key.
    """
    user = user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="not signed in")
    if config.OWNER_SUBJECT:
        if config.AUTH_ISSUER and user.subject not in {
            config.OWNER_SUBJECT,
            *config.ADMIN_SUBJECTS,
        }:
            raise HTTPException(
                status_code=403, detail="This dashboard belongs to someone else."
            )
        user = replace(user, subject=config.OWNER_SUBJECT)
    return user


# Route parameter type for "whose dashboard this is": `user: CurrentUser`.
CurrentUser = Annotated[User, Depends(current_user)]
