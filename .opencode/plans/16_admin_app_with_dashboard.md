# Admin App with Embedded Dashboard

Layer 1 of the **two-app** architecture (was three; the per-user dashboard pod has been folded into the admin app). Layer 2 (per-notebook apps spawned on Edit/Run click) is in [`17_per_notebook_apps.md`](./17_per_notebook_apps.md).

The reshape: a single admin pod hosts both the unauthenticated landing and the post-login dashboard. There is **no per-user dashboard pod**, and **no per-user PVC** — Flyte v2 doesn't yet support pod templates on AppEnvironments (`"K8sPod app payload is not yet supported"` from the server), so per-notebook pods hold workspace state in their own ephemeral container storage, clone the user's fork on startup, and push back on shutdown. The admin app reads each user's workspace state on demand from whichever per-notebook pod they have running (via in-cluster service DNS), with the GitHub Contents API as a cold-case read-only fallback.

## Goal

After signing in via GitHub OAuth, the admin app renders a tile grid for the signed-in user and brokers Edit/Run clicks into per-notebook AppEnvironments deployed in the user's `sg-<username>` Flyte project.

## Already done

- `src/stargazer/notebooks/community/scrna_pipeline.py` — full 452-line production scRNA notebook (committed).
- `src/stargazer/notebooks/workspace/.gitkeep` — empty dir reserved for user-owned workspace notebooks in their forks.

## Architecture

```
┌─────────────────────────────────────────────┐
│ Admin app (single shared deployment)         │
│  GET /             → login OR dashboard      │
│  GET /auth/login   → GitHub OAuth            │
│  GET /auth/callback→ fork + provision +      │
│                       set cookie + 302 /     │
│  POST /launch      → serve.aio(per_nb_env)   │
│                       → 303 to nb URL         │
│                                              │
│  workspace listing on dashboard render:      │
│    1. try GET {nb_pod}/__sg__/workspace/list │
│    2. cold case → GitHub Contents API        │
└──────────────────────┬───────────────────────┘
                       │ serve.aio per click
                       ▼
        ┌──────────────────────────────────────┐
        │ Per-notebook app (per slug × mode)   │
        │   marimo + cookie proxy              │
        │   /__sg__/workspace/list (local)     │
        │   /__sg__/workspace/sync (local git) │
        └──────────────────────────────────────┘
```

## What's in the admin app

Roughly four route groups:

- **`GET /`** — `_get_session(request)` → if no session, return `login_html()`; else render `dashboard_html(username, _render_tiles(workspace_files))`. `workspace_files` comes from `_resolve_workspace_files(session, cookie)` which tries each known-launched per-notebook pod's `/__sg__/workspace/list`, falling back to `app.github.list_workspace(...)`.
- **`GET /auth/login` + `GET /auth/callback`** — unchanged from the existing OAuth flow except the callback now redirects to `/` (the dashboard) instead of a per-user dashboard URL.
- **`POST /launch`** — form-encoded `slug`, `mode`, `section`. Resolves slug to a notebook path (image-baked for tutorials/community, `/workspace/.../<slug>.py` for workspace), calls `per_notebook_env(...)`, `flyte.with_servecontext(project=sanitize_project_id(user), domain=...).serve.aio(env)`, records `(slug, mode)` in the in-memory `_launched` registry, returns 303 to `deployment.endpoint`.
- **`GET /health`, `GET /auth/logout`** — unchanged.

## Workspace listing

`_launched: dict[username, set[(slug, mode)]]` is an in-memory record of which per-notebook pods the user has spawned this admin-pod lifetime. On dashboard render, the admin tries each `nb-<slug>-<mode>.<project>.svc.cluster.local/__sg__/workspace/list` (short timeout, short-circuit on first 200). If none answer, falls back to `app.github.list_workspace(fork_owner, access_token)`.

State volatility: the registry is lost on admin pod restart. After a restart, dashboards fall back to GitHub for listing until the user re-launches any notebook. Acceptable for MVP; could be persisted to a sidecar later if needed.

## Per-user provisioning

`provision_user(github_username=...)` is now a single step: ensure the user's Flyte project exists via `Project.create.aio(...)`. No PVC creation, no `serve.aio` — per-notebook pods are spawned only on click, and they manage their own workspace state in pod-local storage.

## Done in code

All the above has been implemented:

- `app/admin_app.py` rewritten to host the dashboard, `/launch`, and workspace listing helper.
- `app/dashboard_app.py` deleted.
- `app/templates.py` simplified; `app/templates/post_login.html` deleted; `dashboard.html` signature unchanged.
- `app/provision.py` simplified to a single step: ensure the Flyte project exists.
- `app/per_notebook.py` factory now bakes `FORK_OWNER`, `GITHUB_TOKEN`, `SESSION_SECRET` into env_vars for the launch script + proxy.
- `app/github.py` gained `list_workspace(...)` Contents API fallback (reads the `workspace` branch).
- `app/proxy.py` gained `/__sg__/workspace/{list,sync}` routes before the marimo catch-all.
- `app/launch-notebook.sh` clones the fork into the container-local `/workspace` directory if `/workspace/.git` is missing.
- `app/__init__.py` docstring updated to the two-app architecture.

## Open questions still standing

1. **Token lifetime for long-lived workspace pods.** GitHub OAuth tokens are non-expiring under the standard flow, so this is mostly moot until we move to refresh tokens. Confirm in practice after first multi-day session.
2. **Cross-namespace HTTP from admin to per-notebook pods.** Plain k8s DNS works without network policies on devbox; production hardening will need a NetworkPolicy that explicitly allows the admin namespace to reach `sg-*` namespaces on port 8080.

## Out of scope

- Per-notebook auth proxy details, marimo sandbox, PEP 723 inline deps — see plan 17.
- MCP / in-notebook LLM.
- Promotion workflow (still implicit via GitHub PR from the user's fork).
- Authentication beyond the signed cookie (e.g. CSRF tokens on `/launch`) — left for a hardening pass.
