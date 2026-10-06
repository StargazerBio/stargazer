"""
### Who is signed in — read from Union's auth layer.

Both the admin and every notebook pod run behind Union's login
(`requires_auth=True`). Union gates each request and forwards the signed-in
user as headers it sets itself, overwriting anything a client sends:

- `X-User-Subject` — the stable Union user id. The key for everything
  per-user: Flyte project, workspace store prefix, asset `_owner`.
- `X-User-Claim-Email`, `X-User-Claim-Name` — display only. Claim values
  arrive JSON-encoded (`"\"a@b.c\""`).

There is no session cookie and no sign-in route of our own: Union owns both.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import json
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request

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


def require_user(request: Request) -> User:
    """FastAPI dependency: the signed-in user, or a 401.

    Behind Union a request without a subject never arrives; the 401 covers a
    local `uvicorn` run and any misconfigured deploy with auth turned off.
    """
    user = user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="not signed in")
    return user


# Route parameter type for "the signed-in user": `user: CurrentUser`.
CurrentUser = Annotated[User, Depends(require_user)]
