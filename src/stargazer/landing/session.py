"""
### Signed-cookie session management.

Stores minimal user state in a tamper-proof cookie using itsdangerous.
No server-side session store — the cookie is the session.

spec: [docs/architecture/landing.md](../../docs/architecture/landing.md)
"""

from dataclasses import asdict, dataclass

from itsdangerous import BadSignature, URLSafeTimedSerializer


SESSION_COOKIE = "sg_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


@dataclass
class SessionData:
    """Minimal session payload stored in the signed cookie."""

    github_username: str
    github_id: int
    notebook_url: str | None = None


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
