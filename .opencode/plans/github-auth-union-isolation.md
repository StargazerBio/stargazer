# Plan: GitHub Auth + Per-User Project Isolation on Union

## Context

Stargazer is deploying to Union (hosted Flyte v2). The primary interface is a Marimo notebook at `app.stargazer.bio`. Currently there is no authentication — the notebook runs with `requires_auth=False` and `--no-token`. We need:

- GitHub OAuth login via a landing page
- Auto-provisioning of isolated Union projects per user on first login
- Transparent Flyte auth in per-user notebooks via env vars
- Same GitHub identity usable in the Union console (via SSO), scoped to user's project only
- Admin account (pryce-turner) for provisioning and management

**Out of scope (future plan):** Per-user data persistence strategy. Called out as a dependency below since it shares boundaries with auth (project-scoped storage, user identity in asset metadata, CID ownership).

---

## Phase 0: Union BYOC SSO Setup (Manual / External)

This is a prerequisite — coordinate with Union support before any code ships.

1. **Register GitHub OAuth App** for Union SSO at `github.com/settings/developers`:
   - Homepage: `https://app.stargazer.bio`
   - Callback: `https://signin.hosted.unionai.cloud/oauth2/v1/authorize/callback`
   - Note Client ID + Client Secret
2. **File Union support ticket** to configure GitHub as OIDC IdP via Okta federation:
   - Provide Client ID (plaintext) and Client Secret (PGP-encrypted with Union public key)
   - Request GitHub username → Union user identity mapping
3. **Register a second GitHub OAuth App** for the FastAPI landing page:
   - Callback: `https://app.stargazer.bio/auth/callback`
   - Scope: `read:user`
   - This is app-level auth, separate from Union SSO
4. **Create Union secrets** (via admin CLI):
   - `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` — landing page OAuth app
   - `SESSION_SECRET` — random 32-byte hex for cookie signing
   - `ADMIN_API_KEY` — admin-level Union API key (base64-encoded)

**Why two OAuth apps?** Union SSO lets users into the console. The landing page OAuth identifies users for provisioning — separate concerns, separate apps.

---

## Phase 1: Unified Flyte Init Helper

Small, testable locally. Decouples all entry points from the auth mode.

### New file: `src/stargazer/init.py`

```python
def init(**kwargs):
    """Initialize Flyte from API key (remote) or config (local)."""
    if os.environ.get("FLYTE_API_KEY"):
        flyte.init_from_api_key(
            project=os.environ.get("FLYTE_PROJECT"),
            domain=os.environ.get("FLYTE_DOMAIN", "development"),
            **kwargs,
        )
    else:
        flyte.init_from_config(**kwargs)
```

### Modified files:
| File | Change |
|------|--------|
| `src/stargazer/notebooks/getting_started.py:29` | `flyte.init_from_config()` → `from stargazer.init import init; init()` |
| `src/stargazer/server.py:80` | Same swap |
| `src/stargazer/app.py:74` | `flyte.init_from_config(root_dir=...)` → `init(root_dir=...)` |

---

## Phase 2: Landing Page Service

### New package: `src/stargazer/landing/`

| File | Purpose |
|------|---------|
| `__init__.py` | Package init, module docstring + spec link |
| `oauth.py` | GitHub OAuth helpers: `github_auth_url()`, `exchange_code()`, `get_github_user()`. Uses `aiohttp` (existing dep). |
| `session.py` | Signed-cookie sessions via `itsdangerous`. `SessionData` dataclass: `github_username`, `github_id`, `notebook_url`. No server-side store. |
| `provision.py` | Core provisioning: project creation, per-user app deployment, RBAC binding. Uses admin API key. |
| `templates.py` | HTML templates as Python functions — `login_html()`, `dashboard_html()`, `provisioning_html()`. No Jinja. |
| `app.py` | FastAPI app + `AppEnvironment` definition |
| `deploy.py` | CLI entry point: `flyte.serve(landing_env)` |

### Routes in `landing/app.py`:

| Route | Purpose |
|-------|---------|
| `GET /` | Landing page or dashboard (if session exists) |
| `GET /auth/login` | Redirect to GitHub OAuth with CSRF state cookie |
| `GET /auth/callback` | Exchange code → get user → provision if new → set session → redirect |
| `GET /auth/logout` | Clear session cookie, redirect to `/` |
| `GET /health` | Health check |

### AppEnvironment for the landing page:

```python
landing_env = flyte.app.AppEnvironment(
    name="stargazer-landing",
    image=flyte.Image.from_debian_base(python_version=(3, 13)).with_pip_packages(
        "stargazer", "fastapi>=0.115", "uvicorn>=0.34", "itsdangerous>=2.1",
    ),
    args=["uvicorn", "stargazer.landing.app:app", "--host", "0.0.0.0", "--port", "8080"],
    port=8080,
    requires_auth=False,  # Public — handles its own auth
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    secrets=[
        flyte.Secret(key="GITHUB_CLIENT_ID", as_env_var="GITHUB_CLIENT_ID"),
        flyte.Secret(key="GITHUB_CLIENT_SECRET", as_env_var="GITHUB_CLIENT_SECRET"),
        flyte.Secret(key="SESSION_SECRET", as_env_var="SESSION_SECRET"),
        flyte.Secret(key="ADMIN_API_KEY", as_env_var="ADMIN_API_KEY"),
        STARGAZER_SECRETS,  # PINATA_JWT
    ],
    env_vars=STARGAZER_ENV_VARS,
)
```

---

## Phase 3: Provisioning Logic (`landing/provision.py`)

Core function: `async def provision_user(github_username: str) -> str`

### Steps:

1. **Sanitize username** → `project_id = f"sg-{re.sub(r'[^a-z0-9-]', '-', username.lower())}"`
2. **Create Union project** (idempotent):
   - `flyte create project --id {project_id} --name "Stargazer: {username}" -l managed-by=stargazer-landing`
   - Catch "already exists" error gracefully
3. **Set RBAC binding** — grant the GitHub-mapped Union user `ProjectMember` role on their project:
   - Use Union admin REST API if available
   - Fallback: coordinate with Union support for programmatic RBAC, or manual step for v1
4. **Deploy per-user notebook app**:
   - Construct `AppEnvironment` dynamically (template from `marimo_env` in `app.py`)
   - Key differences from the base `marimo_env`:
     - `name=f"notebook-{project_id}"`
     - `requires_auth=True` (Union SSO gates access)
     - `env_vars` includes `FLYTE_PROJECT={project_id}`, `FLYTE_DOMAIN=development`
     - `secrets` includes `ADMIN_API_KEY` as `FLYTE_API_KEY` (see note below)
   - Deploy via `flyte.init_from_api_key()` with admin key, then `flyte.deploy()`
5. **Return notebook URL** from the deployment object

### API key strategy (v1):

All per-user notebooks use the **admin API key** injected as `FLYTE_API_KEY`, but are scoped to their project via `FLYTE_PROJECT` env var. RBAC provides the hard isolation boundary. This avoids the need for per-user API key generation which may not be programmatically available.

**Future improvement:** When Union exposes per-user API key creation via REST API, generate scoped keys during provisioning instead.

### Provisioning latency:

First login triggers project creation + app deployment, which could take 1-2 minutes. The callback route should:
1. Return a "Setting up your workspace..." page immediately
2. Poll `GET /provision/status/{username}` until ready
3. Redirect to notebook URL on completion

The notebook image (`with_pip_packages("stargazer")`) should be cached after the first user, so subsequent provisions are faster.

---

## Phase 4: Config Changes

### Modified: `src/stargazer/config.py`

Add:
```python
LANDING_SECRETS = [
    flyte.Secret(key="GITHUB_CLIENT_ID", as_env_var="GITHUB_CLIENT_ID"),
    flyte.Secret(key="GITHUB_CLIENT_SECRET", as_env_var="GITHUB_CLIENT_SECRET"),
    flyte.Secret(key="SESSION_SECRET", as_env_var="SESSION_SECRET"),
    flyte.Secret(key="ADMIN_API_KEY", as_env_var="ADMIN_API_KEY"),
]

USER_NOTEBOOK_SECRETS = [
    STARGAZER_SECRETS,  # PINATA_JWT
    flyte.Secret(key="ADMIN_API_KEY", as_env_var="FLYTE_API_KEY"),
]
```

### Modified: `pyproject.toml`

Dependencies:
```
"fastapi>=0.115",
"uvicorn>=0.34",
"itsdangerous>=2.1",
```

Scripts:
```
stargazer-landing = "stargazer.landing.deploy:main"
```

---

## Phase 5: Union Console Access

Handled entirely by Phase 0 SSO setup. Once GitHub is configured as IdP:
- Users log into `https://<org>.hosted.unionai.cloud` with GitHub
- RBAC scopes their view to `sg-{username}` project
- Landing page dashboard includes direct link to console executions view

---

## Data Persistence Dependency (Future Plan)

The auth system creates the identity and isolation boundaries that per-user data persistence will build on. Key touch points to design later:

- **Project-scoped storage**: Each user's assets (AnnData, references, etc.) live in their `sg-{username}` project. The `STARGAZER_LOCAL` dir and Pinata uploads need project-scoping.
- **Asset ownership**: The `Asset` base class may need a `project` or `owner` field in `to_keyvalues()` so queries are project-aware.
- **Shared vs private data**: Demo bundles and reference genomes should be accessible across projects. User-generated data should be private.
- **Storage backend per project**: Union isolates cache per project-domain pair. Need to decide if Pinata (IPFS) storage follows the same boundary or stays global with metadata-level isolation.

---

## File Summary

### New files (8):
- `src/stargazer/init.py`
- `src/stargazer/landing/__init__.py`
- `src/stargazer/landing/oauth.py`
- `src/stargazer/landing/session.py`
- `src/stargazer/landing/provision.py`
- `src/stargazer/landing/templates.py`
- `src/stargazer/landing/app.py`
- `src/stargazer/landing/deploy.py`

### Modified files (5):
- `src/stargazer/config.py` — Add landing + user notebook secrets
- `src/stargazer/notebooks/getting_started.py` — Use `init()` helper
- `src/stargazer/server.py` — Use `init()` helper
- `src/stargazer/app.py` — Use `init()` helper
- `pyproject.toml` — Add deps + script entry point

---

## Risks

| Risk | Mitigation |
|------|-----------|
| No programmatic per-user API key creation | v1 uses admin key + project scoping + RBAC. Upgrade when Union API available. |
| RBAC API may not be programmatic | Coordinate with Union support. Manual step for v1 if needed. |
| Provisioning latency on first login | Polling UI with "Setting up..." page. Pre-build notebook image. |
| GitHub username → project ID collisions | `sg-` prefix + sanitization. Check for existing project before create. |

## Implementation Sequence

1. **Phase 0** — SSO setup with Union support (blocking, external)
2. **Phase 1** — `init()` helper + update existing entry points (small, testable locally)
3. **Phase 2** — Landing page OAuth + session (testable independently with test GitHub OAuth app)
4. **Phase 3** — Provisioning logic (needs admin API key, testable against staging)
5. **Phase 4** — Config + dependency changes
6. **Phase 5** — Deploy landing page, test full end-to-end flow

## Verification

1. **Phase 1**: Run existing tests — `init()` should fall back to config when no `FLYTE_API_KEY` is set
2. **Phase 2**: Run landing page locally with `uvicorn`, test GitHub OAuth round-trip against a test OAuth app
3. **Phase 3**: Test provisioning against a staging Union deployment with admin API key
4. **End-to-end**: Login at `app.stargazer.bio` → first-login provision → notebook loads → run a task → check Union console shows execution in user's project only
