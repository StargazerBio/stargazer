"""
### Signed-cookie session management.

Stores minimal user state in a tamper-proof cookie using itsdangerous.
No server-side session store — the cookie is the session. Both the admin
app and the per-user dashboard app validate the same cookie using
`SESSION_SECRET`, so a single sign-in carries across all the pages a user
visits.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

from dataclasses import asdict, dataclass

from fastapi import Request
from itsdangerous import BadSignature, URLSafeTimedSerializer


SESSION_COOKIE = "sg_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


@dataclass
class SessionData:
    """Session payload stored in the signed cookie.

    `fork_full_name` is the `owner/repo` of the user's *verified* stargazer
    fork — the exact name GitHub created, which may differ from the upstream
    name on a collision (e.g. `alice/stargazer-1`). It stays empty until the
    user opts in via `POST /workspace/enable`, which only records it after
    confirming the repo is a genuine fork and not the upstream source; an
    empty value means Workspace saving is off. `access_token` is the OAuth
    token used by the dashboard to fork, list, clone, and push.
    """

    github_username: str
    github_id: int
    fork_full_name: str = ""
    access_token: str = ""

    @property
    def fork_owner(self) -> str:
        """The fork's owner login, derived from `fork_full_name`."""
        return self.fork_full_name.split("/", 1)[0] if self.fork_full_name else ""

    @property
    def workspace_enabled(self) -> bool:
        """True once the user has opted in to forking (Workspace saving)."""
        return bool(self.fork_full_name and self.access_token)


def create_session_cookie(data: SessionData, secret: str) -> str:
    """Serialize and sign session data into a cookie value."""
    s = URLSafeTimedSerializer(secret)
    return s.dumps(asdict(data))


def read_session_cookie(
    cookie: str, secret: str, max_age: int = SESSION_MAX_AGE
) -> SessionData | None:
    """Deserialize and verify a session cookie.

    Returns None if the cookie is invalid, expired, or tampered with.
    """
    s = URLSafeTimedSerializer(secret)
    try:
        payload = s.loads(cookie, max_age=max_age)
        return SessionData(**payload)
    except (BadSignature, TypeError, KeyError):
        return None


def session_from_request(request: Request, secret: str) -> SessionData | None:
    """Extract and verify the session cookie attached to a FastAPI request.

    Returns the deserialized `SessionData` or None if the cookie is
    missing or invalid. Shared by the admin app and the dashboard app so
    they enforce the same auth check.
    """
    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie:
        return None
    return read_session_cookie(cookie, secret)
