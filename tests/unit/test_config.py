"""Tests for the app-tier config home (`app.config`).

The config *values* are module constants resolved once at import; the logic
worth testing is the boolean-flag parser they're built from. Constants like
`SECURE_COOKIES` are exercised end-to-end by the admin/proxy cookie tests
(which `monkeypatch.setattr` the constant), so here we just pin the parser and
the documented defaults.
"""

from app import config


def test_flag_truthy_spellings(monkeypatch):
    """1/true/yes/on are truthy (case-insensitive); everything else is False."""
    for val in ("1", "true", "TRUE", "Yes", "on", " on "):
        monkeypatch.setenv("SG_TEST_FLAG", val)
        assert config._flag("SG_TEST_FLAG") is True
    for val in ("", "0", "false", "nope", "2"):
        monkeypatch.setenv("SG_TEST_FLAG", val)
        assert config._flag("SG_TEST_FLAG") is False


def test_flag_missing_is_false(monkeypatch):
    """An unset variable is False, not an error."""
    monkeypatch.delenv("SG_TEST_FLAG", raising=False)
    assert config._flag("SG_TEST_FLAG") is False


def test_secure_cookies_defaults_off():
    """The shipped default for cookie Secure is off (devbox/http)."""
    assert isinstance(config.SECURE_COOKIES, bool)
    # Tests run without STARGAZER_SECURE_COOKIES set → off.
    assert config.SECURE_COOKIES is False
