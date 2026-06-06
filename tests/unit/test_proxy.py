"""Tests for the per-notebook proxy's callback-fetch git token (`app.proxy`).

The proxy is baked into the notebook image as a standalone module; here we
import it directly and exercise `_fetch_pod_git_token`, which exchanges the
`SG_POD_TOKEN` capability for a fresh fork-scoped token at push time. The
GitHub/admin round-trip is faked via `httpx.post`.
"""

from types import SimpleNamespace

from app import proxy
from app.session import SessionData, create_session_cookie


# ---------------------------------------------------------------------------
# Encrypted session cookie — the proxy must validate what the admin issues
# ---------------------------------------------------------------------------


def test_proxy_validates_admin_issued_cookie(monkeypatch):
    """The proxy's Fernet derivation matches app.session, so it accepts the cookie."""
    secret = "shared-session-secret"
    monkeypatch.setenv("SESSION_SECRET", secret)
    cookie = create_session_cookie(
        SessionData("octocat", 1, fork_full_name="octocat/stargazer"), secret
    )
    assert proxy._cookie_is_valid(cookie) is True


def test_proxy_rejects_tampered_or_foreign_cookie(monkeypatch):
    """A wrong-secret, tampered, absent, or unencrypted cookie is rejected."""
    secret = "shared-session-secret"
    cookie = create_session_cookie(SessionData("octocat", 1), "a-different-secret")
    monkeypatch.setenv("SESSION_SECRET", secret)
    assert proxy._cookie_is_valid(cookie) is False
    assert proxy._cookie_is_valid(None) is False
    assert proxy._cookie_is_valid("not-a-real-cookie") is False


def test_proxy_denies_when_secret_missing(monkeypatch):
    """No SESSION_SECRET in the pod env → deny everything."""
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    assert proxy._cookie_is_valid("anything") is False


def test_proxy_cookie_secure_mirrors_config(monkeypatch):
    """The proxy's Secure read matches `app.config.SECURE_COOKIES` (off by default)."""
    monkeypatch.delenv("STARGAZER_SECURE_COOKIES", raising=False)
    assert proxy._cookie_secure() is False
    monkeypatch.setenv("STARGAZER_SECURE_COOKIES", "1")
    assert proxy._cookie_secure() is True


def _stub_httpx_post(monkeypatch, *, status: int, text: str):
    """Patch proxy.httpx.post to return a canned response, recording the call."""
    recorder: dict = {}

    def fake_post(url, headers=None, timeout=None):
        recorder.update(url=url, headers=headers or {})
        return SimpleNamespace(status_code=status, text=text)

    monkeypatch.setattr(proxy.httpx, "post", fake_post)
    return recorder


def test_fetch_token_missing_capability_returns_none(monkeypatch):
    """With no SG_POD_TOKEN/admin URL there's nothing to exchange — None."""
    monkeypatch.delenv("SG_POD_TOKEN", raising=False)
    monkeypatch.delenv("STARGAZER_ADMIN_URL", raising=False)
    assert proxy._fetch_pod_git_token() is None


def test_fetch_token_posts_capability_and_returns_token(monkeypatch):
    """The capability is sent as a bearer; the plain-text token is returned."""
    monkeypatch.setenv("SG_POD_TOKEN", "signed-cap")
    monkeypatch.setenv("STARGAZER_ADMIN_URL", "http://admin/")
    recorder = _stub_httpx_post(monkeypatch, status=200, text="ghs_pod\n")

    token = proxy._fetch_pod_git_token()

    assert token == "ghs_pod"
    assert recorder["url"] == "http://admin/workspace/pod-token"
    assert recorder["headers"]["Authorization"] == "Bearer signed-cap"


def test_fetch_token_non_200_returns_none(monkeypatch):
    """A 401/502 from the admin yields None (caller turns it into a failure)."""
    monkeypatch.setenv("SG_POD_TOKEN", "signed-cap")
    monkeypatch.setenv("STARGAZER_ADMIN_URL", "http://admin")
    _stub_httpx_post(monkeypatch, status=502, text="")
    assert proxy._fetch_pod_git_token() is None
