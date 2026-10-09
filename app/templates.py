"""
### Jinja2 templates for the dashboard.

Templates live in `app/templates/` and are rendered via
`fastapi.templating.Jinja2Templates`. Routes hand off to
`templates.TemplateResponse(...)` with a request and context dict;
Jinja2 auto-escapes interpolated values (no manual `html.escape`
required) and gives every page the shared chrome via `{% extends
"base.html" %}`.

Layout:

- `base.html` — `<html>` shell, CSS, blocks `body` and `scripts`.
- `dashboard.html` — extends base for the post-login dashboard, with
  the user-menu avatar, the four tile sections, and the launch JS.
- `_tile.html` — partial for one notebook tile (rendered per tile
  in each dashboard section). Underscore prefix is convention for
  "not directly rendered, included only".

Context shape consumed by `dashboard.html`:

- `title` (str) — `<title>` chrome.
- `user` (`app.identity.User`) — the avatar initial and "Signed in as".
- `workspace_configured` (bool) — whether this deploy can save notebooks;
  False renders a notice in place of the Workspace grid.
- `workflows`, `snapshots`, `workspace`, `tutorials` (list of tile
  dicts) — each dict has `slug`, `title`, `description`, `section` (plus
  `cpu`/`memory` for workspace tiles). The dashboard loops and includes
  `_tile.html` for each. `snapshots` tiles are frozen: a Run-only launch
  (no Edit/gear); a Workspace tile's 📸 button freezes it into this
  section. Shipped public snapshots carry `source == "public-snapshots"`
  (what launch/copy/download send) and no delete. Workflows and Snapshots
  tiles carry a Copy-to-workspace button; Workspace and Snapshots tiles a
  Download link.
- `version` (str) — the commit the dashboard was deployed from, shown in
  the footer; empty shows nothing.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
