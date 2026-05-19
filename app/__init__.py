"""
### Stargazer deployment infrastructure.

Two Flyte AppEnvironments:
- `app.admin_app.app_env` — shared FastAPI landing/OAuth/provisioning service
- `app.notebook_app.notebook_env` — per-user marimo notebook env, deployed once per user project by the admin app

Plus supporting modules: `oauth`, `session`, `templates`, `provision`,
`init`. Lives outside `src/stargazer` because it is deployment glue, not
part of the bioinformatics SDK.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""
