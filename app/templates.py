"""
### HTML template loaders.

Reads templates from `app/templates/` and substitutes placeholders using
`string.Template` (`$name` syntax — leaves CSS `{...}` untouched). No Jinja
dependency; templates are loaded once at module import.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

from pathlib import Path
from string import Template


_TEMPLATES = Path(__file__).parent / "templates"
_BASE = Template((_TEMPLATES / "base.html").read_text())
_LOGIN_BODY = (_TEMPLATES / "login.html").read_text()
_DASHBOARD_BODY = Template((_TEMPLATES / "dashboard.html").read_text())
_PROVISIONING_BODY = Template((_TEMPLATES / "provisioning.html").read_text())


def login_html() -> str:
    """Landing page with GitHub sign-in button."""
    return _BASE.substitute(title="Sign In", body=_LOGIN_BODY)


def dashboard_html(github_username: str, notebook_url: str) -> str:
    """Post-login dashboard linking to the user's per-project notebook."""
    body = _DASHBOARD_BODY.substitute(
        github_username=github_username,
        notebook_url=notebook_url,
    )
    return _BASE.substitute(title="Dashboard", body=body)


def provisioning_html(github_username: str) -> str:
    """Interim page shown while the user's notebook app is being deployed."""
    body = _PROVISIONING_BODY.substitute(github_username=github_username)
    return _BASE.substitute(title="Setting Up", body=body)
