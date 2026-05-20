"""
### HTML template loaders.

Reads templates from `app/templates/` and substitutes placeholders using
`string.Template` (`$name` syntax — leaves CSS `{...}` untouched). Two
helpers in play:

- `login_html()` — admin app's unauthenticated landing page.
- `dashboard_html(username, body)` — admin app's post-login dashboard
  chrome; `body` is the three-section tile grid rendered by
  `app.admin_app._render_tiles(...)`.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

from pathlib import Path
from string import Template


_TEMPLATES = Path(__file__).parent / "templates"
_BASE = Template((_TEMPLATES / "base.html").read_text())
_LOGIN_BODY = (_TEMPLATES / "login.html").read_text()
_DASHBOARD_BODY = Template((_TEMPLATES / "dashboard.html").read_text())


def login_html() -> str:
    """Landing page with GitHub sign-in button."""
    return _BASE.substitute(title="Sign In", body=_LOGIN_BODY)


def dashboard_html(github_username: str, body: str) -> str:
    """Wrap the dashboard's tile grid in the shared chrome."""
    rendered = _DASHBOARD_BODY.substitute(
        github_username=github_username,
        body=body,
    )
    return _BASE.substitute(title="Dashboard", body=rendered)
