# App: Hosted Landing + Per-User Notebooks

The `app/` directory is **deployment glue** — FastAPI, OAuth, sessions, Flyte AppEnvironment definitions. It lives outside `src/stargazer/` because it is not invokable by tasks or workflows; the SDK stays importable in environments without FastAPI, OAuth secrets, or a Flyte control plane connection.

Two Flyte `AppEnvironment`s are defined here:

- **`app_env`** (admin landing) — one shared instance, fronts GitHub OAuth and provisions per-user resources on first login.
- **`notebook_env`** (notebook) — one definition, deployed once per user into the user's own Flyte project.

## Topology

```mermaid
flowchart LR
    U([User browser]) -->|/auth/login| L[admin app<br/>app_env]
    L --> GH[(GitHub OAuth)]
    L -->|provision per user| FCP[(Flyte control plane)]
    FCP -->|deploys| N[notebook_env instance<br/>project: sg-USERNAME]
    U -->|browser tab| N
```

One landing app, one notebook definition, N notebook deployments — one per user, isolated by Flyte project.

## Request Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as admin app
    participant G as GitHub
    participant F as Flyte CP

    B->>A: GET /
    A-->>B: login.html
    B->>G: authorize
    G-->>A: /auth/callback?code
    A->>G: exchange code
    A->>F: create project sg-USERNAME
    A->>F: serve notebook_env in project
    F-->>A: notebook URL
    A-->>B: dashboard + signed cookie {notebook_url}
```

If provisioning fails, the user lands on a provisioning page with a sign-out link as the escape hatch.

## Per-User Isolation

Per-user state is enforced by **Flyte project boundaries**, not by varying the env definition. `notebook_env` is a single, immutable `AppEnvironment`; `provision_user()` creates a project `sg-<sanitized-username>` and deploys that same env into it. Flyte's per-project storage and cache isolation keeps user state separate.

This is why `notebook_app` is not a factory function — nothing per-user lives in the env definition.

## Workspace Opt-In

Forking a user's GitHub account is **opt-in**, not automatic. Login creates the user's Flyte project but writes nothing to GitHub; `SessionData.fork_owner` stays empty (`SessionData.workspace_enabled` is False). Tutorials and Community notebooks run from the image and need no fork.

Opt-in is **two steps**, and `SessionData.workspace_enabled` requires both — gated on `fork_full_name` **and** `app_installed`. The Workspace section renders a disclaimer + an **Enable workspace saving** button. `POST /workspace/enable` forks the upstream repo, records `fork_full_name`, then redirects the user to install the GitHub App on the fork (see Credential Model). The App's setup-URL returns to `/auth/app-install-callback`, which sets `app_installed` (and drops the OAuth token) — only *then* is saving on. A user who forks but abandons the install is **not** shown as enabled (post-fork ops would fail), and a returning user's install is re-confirmed at login via `installation_tokens.get_installation_id`. Only when enabled does the section list the user's notebooks and `/launch` permit workspace launches (clone-on-start + push-on-sync against the fork's `main`). The `public_repo` OAuth scope is still requested at login, but no fork is created until this explicit action.

## Credential Model

Two GitHub identities, deliberately split so the broad credential is short-lived and never touches code the user controls:

| Step | Credential | Scope | Lifetime | Where it lives |
|---|---|---|---|---|
| Login + the one-time fork | **OAuth user token** (`read:user public_repo`) | all public repos | login → opt-in only | admin process + encrypted cookie, then **dropped** at install callback |
| Admin-side reads/writes (list/get/create/delete on the fork) | **GitHub App installation token** | the fork only | ~1h, minted on demand | admin process memory |
| Pod clone / push | **GitHub App installation token** via `GIT_ASKPASS` | the fork only | ~1h, minted at use | never persisted — fetched per operation |

The **GitHub App private key** is the trust anchor: held solely by the admin, it mints fork-scoped installation tokens (`app/installation_tokens.py`) for every post-fork operation. The OAuth token forks once at `/workspace/enable`; the App's install setup-URL hits `/auth/app-install-callback`, which clears the token from the session — so an *enabled* session carries no GitHub credential. A returning user whose fork already exists never stores the OAuth token at all.

**Pods never receive a GitHub credential.** `per_notebook_env` injects only a signed *capability* (`SG_POD_TOKEN`, carrying the fork name, not a token). At clone (`launch-notebook.sh`) and push (`proxy.py`), the pod exchanges that capability at the admin's `POST /workspace/pod-token` for a fresh fork-scoped token, fed to git via `GIT_ASKPASS` against a token-free remote — so nothing lands in `.git/config` or `os.environ`. The worst a malicious cell can do is mint a fork-scoped, ~1h, revocable token (uninstalling the App cuts it off) — never the broad OAuth token. The session cookie is **encrypted** (Fernet, keyed off `SESSION_SECRET`; the proxy mirrors the derivation), so even its identity fields are opaque client-side.

## Creating Notebooks & Per-Notebook Resources

Once opted in, the Workspace section offers a **New notebook** form (name, blank|template, cpu, memory). The seeds are real shipped notebooks — `notebooks/workspace/blank.py` and `template.py` — not generated source. `POST /workspace/create` slugifies the name, copies the chosen seed, injects the requested resources into its `[tool.stargazer]` header (`with_stargazer_resources`), writes it to the fork's `main` under `notebooks/workspace/`, and **returns the rendered tile HTML**. Create is a pure "add a notebook" action: the browser drops that tile into the Workspace grid and it behaves like every other tile (Edit/Run → launch → Open/Stop) — it does not launch or navigate. Both seed slugs are reserved create names and filtered out of the dashboard's tile listing.

Each Workspace tile also carries a **Delete** button (`POST /workspace/delete`, workspace-only). It removes `<slug>.py` from the fork's `main` (idempotent — a file already gone still succeeds; git history keeps it recoverable) and best-effort deactivates any running edit/run pod for that slug, so deleting can't orphan a pod with no tile left to Stop it. Seed slugs are rejected. The browser confirms, then drops the tile on success.

## Running State (stateful tiles)

Tile run-state is unified and authoritative. The dashboard's launch/stop handlers are **event-delegated**, so dynamically added tiles (a freshly created notebook) work with no re-binding. On load the page calls **`GET /launch/status`**, which queries Flyte (`App.get` per candidate `nb-{slug}-{mode}` in the user's project, in parallel) and returns the active ones with their endpoints; the page flips those tiles straight to **Open + Stop** instead of a fresh Edit/Run. Because it reads the control plane rather than in-memory state, it's correct across admin restarts. (`App.listall` can't be scoped to a per-user project, so per-candidate `App.get` is used.) The candidate-slug enumeration is shared with cleanup via `_candidate_slugs`.

**One modality at a time.** A notebook runs in either `edit` *or* `run` mode, never both — there's no use case for two live pods of the same notebook, and forbidding it caps pod count at one per notebook. So when a tile is launched (or hydrated as already-running), the dashboard hides **both** the launched mode's own Edit/Run button *and* the other mode's, leaving only that pod's controls: **Open in Edit Mode** / **Open in Run Mode** (the open link is labeled by mode), **Stop**, and **Save** for workspace tiles. **Stop** restores both buttons. This is a client-side affordance: it removes the second-pod path from the UI rather than enforcing mutual exclusion in the control plane.

A running **Workspace** tile also gets a **Save** button (`POST /workspace/save`): the admin resolves that one pod's `App.endpoint` and calls its `/__sg__/workspace/sync` (server-to-server, with the session cookie). It's per-notebook on purpose — each pod owns its own `/workspace` clone, so syncing one can't clobber another's edits. A global commit would race those copies. The call uses the app's public endpoint regardless of where the admin runs (in-cluster pod, local `uvicorn`, prod) — devbox is configured so that hostname resolves inside the cluster too (see `.opencode/reference/devbox_workarounds.md`).

A global **Clean up stopped apps** control (`POST /workspace/cleanup`) deletes (`App.delete`) the deployment records for every *deactivated* `nb-{slug}-{mode}` candidate — Stop deactivates an app but leaves the record; this removes them. Active/idle apps are left alone.

Resources live **in the notebook**. At `/launch`, the admin fetches a workspace notebook's source from the fork and `app.notebook_meta.parse_notebook_resources` reads `[tool.stargazer]` (cpu/memory) and passes it to `per_notebook_env(resources=…)`. Values are honored **as-authored — no ceiling**; you rightsize per-notebook for the target cluster. Parsing is purely textual — the admin never executes notebook code. Image-baked tutorials/community notebooks carry no such block and keep the env's legacy `("2Gi", "6Gi")` default.

## Working Branch

User notebooks live and persist on the fork's **`main`** — there is no side branch. The launch script clones `main`, the proxy's sync commits and pushes back to `main`, and the dashboard lists from `main`. Sync runs on two triggers: the explicit **Save** button, and **pod shutdown** — because `/workspace` is ephemeral, the proxy registers a FastAPI `lifespan` hook that flushes pending edits when Knative scales the pod to zero (uvicorn runs as PID 1 via the launch script's `exec`, so it receives the SIGTERM and runs the hook; a shell `trap` would not survive `exec`). Conflicts with upstream are avoided not by branch isolation but by **path discipline**: the proxy only ever `git add`s `src/stargazer/notebooks/workspace/`, and users create new-named notebooks rather than editing shipped files, so the fork's `main` and upstream touch disjoint paths. The one shared file, `template.py`, is copied (never edited in place) by the create flow. The fork is also not auto-synced from upstream, and the SDK that notebooks import comes from the per-notebook image (`/stargazer`), not the fork checkout — so a drifting `main` doesn't affect execution.

## Modules

| Module | Role |
|--------|------|
| `app/admin_app.py` | `app_env` + FastAPI routes (`/`, `/auth/login`, `/auth/callback`, `/auth/logout`, `/workspace/enable`, `/auth/app-install-callback`, `/workspace/create`, `/workspace/delete`, `/launch`, `/launch/status`, `/stop`, `/workspace/save`, `/workspace/cleanup`, `/workspace/pod-token`, `/health`). `/workspace/enable` is the opt-in that forks the upstream repo, records the verified `fork_full_name`, and redirects to the GitHub App install; `/auth/app-install-callback` finishes opt-in and drops the OAuth token; `/workspace/create` writes a new notebook to the fork's `main` and returns the rendered tile; `/workspace/delete` removes a workspace notebook (idempotent) and deactivates any running pod for it; `/launch` serves a per-notebook env (workspace launches require opt-in); `/launch/status` reports active per-notebook apps so the dashboard hydrates running tiles to Open/Stop; `/stop` deactivates by name; `/workspace/save` syncs one running pod's workspace to the fork; `/workspace/cleanup` deletes deactivated per-notebook app records; `/workspace/pod-token` mints a fork-scoped git token for a pod that presents its capability. Post-fork GitHub ops go through `app/installation_tokens.py` (installation tokens), not the OAuth token. Lifespan runs `init()` at startup. |
| `app/notebook_meta.py` | Static parsing of a notebook's PEP 723 `[tool.stargazer]` resource block (no code execution, honored as-authored — no ceiling); plus the resource-injection helper (`with_stargazer_resources`) used by `/workspace/create`. |
| `app/notebook_app.py` | `notebook_env` — marimo edit on the bundled scRNA tutorial. |
| `app/provision.py` | `provision_user()` — creates the Flyte project and serves `notebook_env` into it via `with_servecontext`. |
| `app/oauth.py` | GitHub OAuth helpers (login + the one-time fork). |
| `app/installation_tokens.py` | GitHub App client — mints fork-scoped, ~1h installation tokens from the App private key for every post-fork op (`fork_token`). The trust anchor of the Credential Model. |
| `app/session.py` | Encrypted-cookie session (`Fernet`, keyed off `SESSION_SECRET`). The cookie is the session — no server-side store. Also signs/verifies pod capabilities (`sign_pod_capability`). |
| `app/templates.py` + `templates/*.html` | Jinja2 template loader (`base.html`, `login.html`, `dashboard.html`, `_tile.html`); auto-escaped, shared chrome via `{% extends "base.html" %}`. Static assets (landing logo) served from `app/static/` at `/static`. |
| `app/init.py` | Runtime-context-aware Flyte init. |

## Runtime Init

The same `init()` works locally and in-cluster:

| Context | Signal | Call |
|---------|--------|------|
| In-cluster app pod | `_U_EP_OVERRIDE` set | `flyte.init_in_cluster()` |
| API-key context | `FLYTE_API_KEY` set | `flyte.init_from_api_key(...)` |
| Local dev / deployer | neither set | `flyte.init_from_config()` |

FastAPI's lifespan calls `init()` once at startup so subsequent SDK calls have a configured client.

## Images

The admin app and the notebook share a strict split:

- `app_env.image` is Flyte-built via `with_uv_project` — the admin is small Python with no heavy deps, and the Flyte builder is the natural fit.
- `notebook_env.image` is the pre-built `stargazer-note:latest` (the `note` target in the project `Dockerfile`). Referenced by string so Flyte does not try to (re)build it inside the admin pod — the admin pod has no Docker daemon and no project source layout, so the build would fail.

The admin deploy entrypoint (`python -m app.admin_app` / `stargazer-app`) runs `docker build --target note` and `docker push` for `stargazer-note:latest` before calling `flyte.serve(app_env)`, so the notebook image is always available in `STARGAZER_REGISTRY` when the admin pod first serves a per-user notebook.

## Open Issues

- **OAuth callback is synchronous.** `provision_user()` runs inline; a slow provision can outlive the browser's redirect window. Background provisioning + status polling is the planned fix.
- **Production auth.** `notebook_env.requires_auth=False` is a devbox concession. Production needs auth gated by the user's identity.
