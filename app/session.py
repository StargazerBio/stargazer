"""
### Encrypted-cookie session management.

Stores minimal user state in an **encrypted, authenticated** cookie using
Fernet (AES-CBC + HMAC) keyed off `SESSION_SECRET`. No server-side session
store — the cookie is the session, and only the admin app reads it.

Notebook pods never see `SESSION_SECRET` or the admin cookie. Each pod gets a
`pod_key` derived from the master secret and its own identity, and the admin
hands browsers a `create_pod_pass` pass encrypted under that key. The proxy
mirrors `_fernet` to check it, so a pass opens exactly one pod.

Encryption (not just signing) means the cookie's contents — github id /
username, and the OAuth token during the brief login→opt-in window — are
opaque client-side, readable only by a holder of `SESSION_SECRET`. Pod
capabilities (`sign_pod_capability`) stay *signed* rather than encrypted: they
carry only a non-secret fork name and need integrity, not secrecy.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import base64
import hashlib
import hmac
import json
from dataclasses import asdict, dataclass

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

SESSION_COOKIE = "sg_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


# A pod capability is signed with a distinct salt so a leaked session cookie
# can never be replayed as a pod capability (or vice versa). It outlives a
# single request — a long-running notebook pod fetches fresh git tokens with it
# at boot and at every shutdown sync — so it shares the session's max age.
_POD_CAPABILITY_SALT = "sg-pod-capability"


def _fernet(secret: str) -> Fernet:
    """Derive the Fernet cipher for session cookies from `SESSION_SECRET`.

    Fernet needs a 32-byte urlsafe-base64 key; `SESSION_SECRET` is an arbitrary
    string, so we hash it to a stable 32-byte key. The per-notebook proxy
    mirrors this derivation exactly so both sides encrypt/decrypt the same
    cookie — keep them in lockstep.
    """
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


@dataclass
class SessionData:
    """Session payload stored in the signed cookie.

    `fork_full_name` is the `owner/repo` of the user's *verified* stargazer
    fork, always the canonical `{username}/{upstream_name}` (see
    `github.canonical_fork_name`). It stays empty until the user opts in via
    `POST /workspace/enable`, which only records it after confirming the repo is
    a genuine fork of upstream at that canonical name; an empty value means
    Workspace saving is off.

    `app_installed` records that the user finished installing the GitHub App on
    the fork — the *second* opt-in step after forking. Saving needs **both**:
    forking alone (without the install) can't mint fork-scoped tokens, so a user
    who clicks Enable but abandons the GitHub install must not appear enabled.
    Set at `/auth/app-install-callback` and re-confirmed at login.

    `access_token` is the OAuth token, kept **only** in the window between login
    and finishing opt-in: it forks the upstream once at `/workspace/enable`,
    after which the install callback clears it (post-fork ops use fork-scoped
    installation tokens instead — see `app.installation_tokens`). A returning user who is
    already enabled never stores it at all. So an *enabled* session carries no
    OAuth token.
    """

    github_username: str
    github_id: int
    fork_full_name: str = ""
    access_token: str = ""
    app_installed: bool = False

    @property
    def fork_owner(self) -> str:
        """The fork's owner login, derived from `fork_full_name`."""
        return self.fork_full_name.split("/", 1)[0] if self.fork_full_name else ""

    @property
    def workspace_enabled(self) -> bool:
        """True once the user has a verified fork **and** the App is installed.

        Both halves of opt-in must be done: the fork exists (`fork_full_name`)
        and the GitHub App install is confirmed (`app_installed`). A half-
        finished opt-in (forked, install abandoned) reports off, since post-fork
        ops would fail. Not gated on the OAuth token, which is dropped once
        opt-in finishes — an enabled session is token-free.
        """
        return bool(self.fork_full_name and self.app_installed)


def create_session_cookie(data: SessionData, secret: str) -> str:
    """Serialize and encrypt session data into a cookie value (Fernet)."""
    raw = json.dumps(asdict(data)).encode("utf-8")
    return _fernet(secret).encrypt(raw).decode("ascii")


def read_session_cookie(
    cookie: str, secret: str, max_age: int = SESSION_MAX_AGE
) -> SessionData | None:
    """Decrypt and verify a session cookie.

    Returns None if the cookie is invalid, expired (`ttl`), or tampered with —
    Fernet authenticates as it decrypts, so a forged or modified cookie fails.
    """
    try:
        raw = _fernet(secret).decrypt(cookie.encode("ascii"), ttl=max_age)
        payload = json.loads(raw)
        return SessionData(**payload)
    except (InvalidToken, ValueError, TypeError, KeyError):
        return None


def sign_pod_capability(fork_full_name: str, secret: str) -> str:
    """Sign a notebook pod's capability to request fork-scoped git tokens.

    Injected into the pod as `SG_POD_TOKEN` in place of any GitHub credential.
    The pod presents it to the admin's `/workspace/pod-token` endpoint, which
    verifies the signature and mints a short-lived, fork-scoped installation
    token. The capability itself carries only the fork name — it is **not** a
    GitHub credential and is useless without the admin + the GitHub App key.
    """
    s = URLSafeTimedSerializer(secret, salt=_POD_CAPABILITY_SALT)
    return s.dumps({"fork_full_name": fork_full_name})


def read_pod_capability(
    capability: str, secret: str, max_age: int = SESSION_MAX_AGE
) -> str | None:
    """Verify a pod capability, returning its `fork_full_name` or None.

    None means the capability is missing, expired, tampered with, or signed for
    a different purpose (the salt won't match a session cookie). The admin's
    mint endpoint treats None as a 401.
    """
    s = URLSafeTimedSerializer(secret, salt=_POD_CAPABILITY_SALT)
    try:
        payload = s.loads(capability, max_age=max_age)
        return payload["fork_full_name"]
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


def pod_key(secret: str, project: str, app_name: str) -> str:
    """Derive the cookie key for one notebook pod from `SESSION_SECRET`.

    A notebook pod runs user code that can read its own environment, so it must
    never hold `SESSION_SECRET` — with it, a user could forge an admin session
    for anyone. Instead each pod gets an HMAC of the master secret over its
    `(project, app_name)` identity. Leaking it only lets the holder mint passes
    into that one pod, which its owner can already open. The admin re-derives
    the same key whenever it hands a browser (or itself) into the pod.
    """
    message = f"sg-pod-key|{project}|{app_name}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def create_pod_pass(key: str, github_username: str) -> str:
    """Mint a pass into one notebook pod, encrypted under that pod's `pod_key`.

    Carries only the username — never the admin session's contents (fork name,
    OAuth token) — since the pod is user-controlled. The proxy sets it as the
    pod's host-only cookie and checks it on every request.
    """
    raw = json.dumps({"github_username": github_username}).encode("utf-8")
    return _fernet(key).encrypt(raw).decode("ascii")


def read_pod_pass(
    pod_pass: str, key: str, max_age: int = SESSION_MAX_AGE
) -> str | None:
    """Return the pass's username, or None if it wasn't minted under `key`."""
    try:
        raw = _fernet(key).decrypt(pod_pass.encode("ascii"), ttl=max_age)
        return json.loads(raw)["github_username"]
    except (InvalidToken, ValueError, TypeError, KeyError):
        return None
