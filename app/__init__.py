"""
### Stargazer deployment infrastructure.

Two kinds of app, both behind Union's login (`requires_auth=True`) and both
deployed into the owning user's own Flyte project (`u-<subject>`):

- `app.admin_app.app_env` — the user's dashboard, one per user. Admits only
  its owner (`app.identity`), renders the dashboard tile grid, and brokers
  Edit/Run clicks into per-notebook apps via
  `app.per_notebook.per_notebook_env(...)`.
- `app.per_notebook.per_notebook_env(...)` — factory for per-notebook
  AppEnvironments, spawned by the dashboard's `/launch` handler and owned by
  the same user. The image is `notebook-app` (uv + marimo +
  system tools + an owner-checking reverse proxy). Each pod hydrates the
  user's notebooks from the workspace store at startup and saves edits back
  to it; the store (`app.workspace_store`, object storage keyed by the
  user's Union subject) is the durable copy, pods are working copies.

Plus supporting modules: `identity`, `workspace_store`,
`notebooks`, `notebook_meta`, `assets`, `proxy`, `templates`, `init`.
Lives outside `src/stargazer` because it is deployment glue, not part of
the bioinformatics SDK.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""
