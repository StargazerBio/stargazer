"""
### Jinja2 templates for the dashboard.

Templates live in `app/templates/` and are rendered via
`fastapi.templating.Jinja2Templates`. Routes hand off to
`templates.TemplateResponse(...)` with a request and context dict;
Jinja2 auto-escapes interpolated values (no manual `html.escape`
required) and gives every page the shared chrome via `{% extends
"base.html" %}`.

Layout:

- `base.html` — `<html>` shell and CSS, blocks `extra_css`, `body` and
  `scripts`.
- `dashboard.html` — extends base for the post-login dashboard: the user-menu
  avatar, the Workflows, Workspace and Tutorials tile sections, the asset
  panel (`_assets.html`), the Settings section and the launch JS.
- `_tile.html` — partial for one notebook tile (rendered per tile
  in each dashboard section). Underscore prefix is convention for
  "not directly rendered, included only".

Context consumed by `dashboard.html` (built by `app.admin_app.dashboard`):

- `title` (str), `version` (str, the deployed commit; empty shows nothing).
- `user` (`app.identity.User`) — the avatar initial and "Signed in as".
- `workspace_configured` (bool) — whether this deploy can save notebooks;
  False renders a notice in place of the Workspace grid and Settings.
- `workflows`, `workspace`, `tutorials` (lists of tile dicts with `slug`,
  `title`, `description`, `section`), included through `_tile.html`.
- `settings` (dict) — the user's settings, filling the Settings form.
- `console_runs_url` (str) — header link to the project's runs; empty omits it.
- The asset panel's: `username` (the visitor's subject), `public_assets`
  (bool), `tus_max_bytes` and `tus_chunk_bytes` (upload limits).

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
