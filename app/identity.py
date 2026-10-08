"""
### Who is signed in — read from Union's auth layer.

Every dashboard and notebook pod runs behind Union's login
(`requires_auth=True`). Union gates each request and forwards the signed-in
user as headers it sets itself, overwriting anything a client sends:

- `X-User-Subject` — the stable Union user id. The key for everything
  per-user: Flyte project, workspace store prefix, asset `_owner`.
- `X-User-Claim-Email`, `X-User-Claim-Name` — display only. Claim values
  arrive JSON-encoded (`"\"a@b.c\""`).

There is no session cookie and no sign-in route of our own: Union owns both.
Each dashboard belongs to one user, but Union alone decides who may open it.

The devbox has no Union login, so its deploy names a stand-in user
(`config.DEVBOX_SUBJECT`) for requests that arrive without a subject. It is
never set on Union.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import json
from dataclasses import dataclass, replace
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app import config

SUBJECT_HEADER = "X-User-Subject"
EMAIL_HEADER = "X-User-Claim-Email"
NAME_HEADER = "X-User-Claim-Name"


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


def user_from_request(request: Request) -> User | None:
    """The signed-in user, or None when Union forwarded no subject.

    On the devbox, a request with no subject is the deploy's stand-in user.
    """
    subject = request.headers.get(SUBJECT_HEADER, "").strip()
    if not subject:
        if config.DEVBOX_SUBJECT:
            return User(subject=config.DEVBOX_SUBJECT, name="Devbox user")
        return None
    return User(
        subject=subject,
        email=_claim(request.headers.get(EMAIL_HEADER)),
        name=_claim(request.headers.get(NAME_HEADER)),
    )


def current_user(request: Request) -> User:
    """FastAPI dependency: the signed-in user, else a 401.

    Union's login is the only access control: whoever it admits (the owner, or
    an org admin who can view the project) gets the dashboard. State is keyed
    by the dashboard's owner (`config.OWNER_SUBJECT`, baked in at deploy), not
    the visitor, so an admin sees the owner's notebooks. The visitor's name and
    email are kept for display. With no owner configured (a local run) the
    visitor's own subject is the key.
    """
    user = user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="not signed in")
    if config.OWNER_SUBJECT:
        user = replace(user, subject=config.OWNER_SUBJECT)
    return user


# Route parameter type for "whose dashboard this is": `user: CurrentUser`.
CurrentUser = Annotated[User, Depends(current_user)]
