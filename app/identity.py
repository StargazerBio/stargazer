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
Each dashboard belongs to one user; `require_owner` admits only them.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import json
from dataclasses import dataclass
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
    """The signed-in user, or None when Union forwarded no subject."""
    subject = request.headers.get(SUBJECT_HEADER, "").strip()
    if not subject:
        return None
    return User(
        subject=subject,
        email=_claim(request.headers.get(EMAIL_HEADER)),
        name=_claim(request.headers.get(NAME_HEADER)),
    )


def require_owner(request: Request) -> User:
    """FastAPI dependency: the signed-in user if they own this app, else a 403.

    A dashboard serves exactly one owner (`config.OWNER_SUBJECT`, baked in at
    deploy). Union already proved the visitor may view the app's project, but
    org admins can view every project, so the subject must also match. Fails
    closed: no forwarded subject, or no configured owner, is a 403.
    """
    user = user_from_request(request)
    owner = config.OWNER_SUBJECT
    if not owner or user is None or user.subject != owner:
        raise HTTPException(status_code=403, detail="this dashboard isn't yours")
    return user


# Route parameter type for "the dashboard's owner": `user: CurrentUser`.
CurrentUser = Annotated[User, Depends(require_owner)]
