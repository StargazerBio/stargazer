# 25 — One Login: Union Auth + Workspace State on Object Storage

Make Union's GitHub SSO the **only** login a user ever sees, and make saving
notebooks automatic. The app tier stops talking to GitHub entirely: no OAuth
App, no fork, no GitHub App install, no session cookie of our own.

**Why.** Users already sign in to Union with GitHub to reach anything on the
tenant. Today the dashboard then asks them to sign in to GitHub *again* (our
own OAuth App), and saving a notebook asks a third time (fork + GitHub App
install). Two extra GitHub consent steps in front of the core feature is
terrible UX. Both exist only because the app had to own identity and had no
durable storage. Union now provides the first and object storage the second.

This plan absorbs plan 24's Piece 2 (collapse to a single OAuth App) and the
roadmap's **identity-gated production auth** and **async OAuth provisioning**
items. With no OAuth callback, there is nothing left to make async.

## What the user sees

| Step | Today | After |
|---|---|---|
| Sign in | Union login (GitHub), then the dashboard's own GitHub login | Union login only |
| Run tutorials / workflows | Nothing more | Unchanged |
| Save your own notebooks | Fork + GitHub App install | **Nothing.** Saving just works |
| Share a notebook upstream | PR from the fork | Download the `.py`, PR it like any contribution |

## Verified on the tenant (2026-10-05)

Measured against `stargazerbio.us-west-2.unionai.cloud` with throwaway apps
before writing this plan:

- **`requires_auth=True` gates on Union login.** An anonymous request gets a
  302 to the tenant's sign-in page (Google / GitHub (Stargazer Bio) /
  Microsoft).
- **Identity is forwarded, and can't be forged.** A signed-in request carries
  `X-User-Subject` (stable Union user id, e.g. `387300641116005877`),
  `X-User-Claim-Email`, `X-User-Claim-Name`, and `X-User-Token: IDToken <JWT>`.
  Client-sent `X-User-*` headers are overwritten by the proxy. **No GitHub
  login, id or token is forwarded** (`preferred_username` is an opaque
  `u-…`).
- **The browser's Union session cookies reach the app pod** (`flyte_idt`,
  `flyte_at_1/2`, `flyte_user_info`).
- **App pods can use object storage, across projects.** `flyte.storage.put` /
  `get` with `recursive=True` work from an app pod after
  `flyte.init_in_cluster()`. An app in project `flytesnacks` read what an app
  in project `default` wrote, and vice versa. Bucket:
  `s3://union-us-west-2-stargazerbio`.
- **Every project runs as one IAM role**
  (`union-us-west-2-stargazerbio-userflyterole`), for tasks and apps alike.

## Settled design decisions

Recorded so they are not relitigated mid-build.

- **Union auth on both app kinds.** The admin and every per-notebook app run
  `requires_auth=True`. Identity comes from `X-User-Subject` on each request.
  No session cookie, no `SESSION_SECRET`, no Fernet.
- **The user key is the Union subject.** It is stable, unique, and the only
  identifier Union guarantees. Email and name are display-only. Derived:
  - Flyte project: `u-<subject>` (replaces `sanitize_project_id(github_username)`)
  - object-store prefix: `<root>/users/<subject>/`
  - `_owner` stamped on assets: the subject (an email would leak into public
    asset bylines)
- **Notebook pods check ownership, not just login.** Union only proves the
  visitor is an org member. The proxy compares `X-User-Subject` with the
  owner subject baked into the pod's env and 403s anyone else. This replaces
  the pod pass, `SG_POD_KEY` and the `sg_launch` handoff.
- **No admin→pod calls.** A pod behind `requires_auth=True` is unreachable
  for the admin's server-to-server calls. So:
  - The dashboard lists notebooks from the object store (Piece 4), not from
    pods.
  - The pod saves itself: the proxy syncs `/workspace` to the object store
    when a file changes and on shutdown. The dashboard's Save button goes.
  - Readiness: the proxy answers immediately and serves a "starting…" page
    that refreshes until marimo answers, so the admin no longer polls
    `/__sg__/ready`.
- **Object storage, not a PVC.** Hot state on pod-local disk, the object
  store is the durable copy. Root is a deploy setting,
  `STARGAZER_WORKSPACE_ROOT` (e.g. `s3://union-us-west-2-stargazerbio/stargazer`).
- **Directory sync, not a tarball.** Each notebook stays an individually
  addressable object, which the dashboard listing depends on.
- **Keyed per notebook.** Each pod writes only its own notebook's object, so
  two running notebooks can never clobber each other.
- **The SIGTERM sync chain stays load-bearing.** The `exec` discipline through
  `fserve` → launch script → uvicorn and `--timeout-graceful-shutdown 15`
  remain correctness-critical; only the verb at the end changes.
- **No GitHub in the app tier at all.** No "publish to GitHub" path either.
  Sharing upstream is a normal contribution from a downloaded file.
- **Public snapshots ship in the image**, like tutorials. Own snapshots live
  in the object store.
- **Recoverable deletes come from bucket versioning**, replacing git history.

## Accepted risks (recorded, not solved here)

- **Shared IAM role.** Any notebook pod's user code can read and write every
  user's workspace objects, because all projects share one role. This is
  already true of task data in the same bucket. Today's fork model gave
  per-user isolation for notebook sources; this plan gives that up. Fix is
  per-project roles on Union's side → ROADMAP.
- **Union cookies reach notebook pods.** The proxy strips them before
  forwarding to marimo, but a pod's own code could still capture a visiting
  org member's Union token. The ownership check stops other members using the
  notebook, not a malicious owner luring them to its URL → ROADMAP.
- **Onboarding is a Union invite.** Only `stargazerbio` org members get past
  the login. Union does not auto-provision users on first login, so new users
  need an invite until it does → ROADMAP.
- **The devbox has no Union auth**, so the app tier won't run there after this
  change. Per the Union-first priority, a devbox identity shim is a follow-up
  → ROADMAP.
- **Anonymous pages go.** The logged-out landing page and anonymous public
  asset browsing sit behind the login like everything else.

## Delivery

Two PRs:

1. **Storage layer** (Piece 1) — new module + tests, nothing wired in. Lands
   independently.
2. **The cut-over** (Pieces 2–7) — auth, hydrate/sync, dashboard, deletions
   and docs together. They can't land separately: the dashboard can't lose its
   own login while workspace still depends on the OAuth token for the fork.

---

## Piece 0 — Verify before building

- [x] `flyte.storage` `put`/`get` with `recursive=True` work from an app pod
      (`flyte.init_in_cluster()`).
- [x] Cross-project access: the admin (project `flytesnacks`) can read objects
      written by a pod in another project.
- [x] Identity forwarded to `requires_auth=True` apps, and unforgeable.
- [ ] `flyte.storage` is importable by the proxy: it runs at system level in
      the notebook image, outside any sandbox venv. Confirm `flyte` is
      installed there, or add it.
- [ ] Bucket versioning is enabled on `union-us-west-2-stargazerbio`. (Union
      manages the bucket — ask them if the console doesn't show it.)
- [ ] A per-notebook app with `requires_auth=True` still receives the
      Knative SIGTERM and runs the shutdown flush (auth sits in front of the
      pod and shouldn't affect it; prove it once).

## Piece 1 — The storage layer (PR 1)

One module, `app/workspace_store.py`, owns the key layout and the
read/write primitives, so no route composes URIs by hand.

### Tests first

- [ ] Round-trip: write a notebook, read it back byte-identical.
- [ ] List returns only that user's notebooks, never another user's.
- [ ] Key derivation rejects a slug or subject that would escape its prefix
      (`../`, `/`, empty).
- [ ] Reading a missing notebook returns `None` and doesn't raise.
- [ ] Create refuses to overwrite (the 409 rule `/workspace/create` and
      `/workspace/copy` depend on).
- [ ] Delete is idempotent.

Tests run against a `file://` root in a temp dir, through the real
`flyte.storage` calls. No mocks.

### Implementation

- [ ] Key layout: `<root>/users/<subject>/notebooks/<slug>.py` and
      `<root>/users/<subject>/snapshots/<slug>.py`.
- [ ] Functions mirroring today's GitHub helpers so call sites change shape as
      little as possible: list, get, create (no-overwrite), update, delete,
      for workspace and snapshots.
- [ ] `STARGAZER_WORKSPACE_ROOT` in `app/config.py`.

## Piece 2 — Identity from Union

- [ ] `requires_auth=True` on `app_env` and in `per_notebook_env`.
- [ ] A FastAPI dependency returning the current user (`subject`, `email`,
      `name`) from `X-User-*`, 401 when absent. Replaces `_require_session`,
      `SessionData` and every `session.github_username` read.
- [ ] Ensure the user's project on first request per process (an in-memory
      seen-set in front of the idempotent `_ensure_project`). No login
      callback is left to do it in.
- [ ] `/assets` routes: owner from the subject. The private tab, sign and
      update keep their fail-closed ownership checks.
- [ ] Delete `/auth/login`, `/auth/callback`, `/auth/logout`, the login page,
      and the session/OAuth modules.

## Piece 3 — Pod hydrate, ownership, and self-sync

- [ ] `launch-notebook.sh`: recursive `get` of the user's notebooks prefix
      into `/workspace` instead of `git clone`. A brand-new user hydrates an
      empty workspace rather than failing.
- [ ] Pod env: `SG_OWNER_SUBJECT`, `STARGAZER_WORKSPACE_ROOT`. Drop
      `FORK_*`, `SG_POD_TOKEN`, `SG_POD_KEY`, `STARGAZER_SECURE_COOKIES`.
- [ ] Proxy: 403 unless `X-User-Subject == SG_OWNER_SUBJECT`; strip `Cookie`
      and `X-User-Token` before forwarding to marimo.
- [ ] Proxy: sync changed notebooks to the store on a short interval and in
      the `lifespan` shutdown hook. **Don't touch the signal chain.**
- [ ] Proxy: "starting…" page while marimo is cold, replacing the admin's
      `/__sg__/ready` polling.
- [ ] Verify an interrupted upload can't leave a corrupt object (a single PUT
      is atomic per object).

## Piece 4 — Dashboard on the store

- [ ] Workspace and own-snapshot listings, and the per-notebook
      `[tool.stargazer]` header reads, come from the store.
- [ ] `/workspace/create`, `/settings`, `/delete`, `/snapshot`, `/copy` move to
      the Piece 1 layer.
- [ ] `/workspace/copy` reads Workflows notebooks from the image, not a fork
      source tree.
- [ ] Public snapshots list from the image; own snapshots from the store.
- [ ] Remove the opt-in gate (`workspace_enabled`) everywhere. Saving needs
      nothing.
- [ ] Add a per-notebook **Download** action, the path for sharing a notebook
      upstream.

## Piece 5 — What gets deleted

Track the simplification. If something here survives, the design drifted.

- [ ] `app/oauth.py`, `app/session.py`, `app/github.py`,
      `app/installation_tokens.py` and their tests.
- [ ] `/workspace/enable`, `/auth/app-install-callback`, `/workspace/pod-token`,
      `/workspace/save`.
- [ ] `SG_POD_TOKEN`, `SG_POD_KEY`, `GIT_ASKPASS`, the `sg_launch` handoff, the
      proxy's cookie check.
- [ ] Deploy secrets `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`,
      `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_SLUG`,
      `SESSION_SECRET`, `_partial_app_creds()`. Only `PINATA_JWT` remains.
- [ ] `STARGAZER_SECURE_COOKIES` / `config.SECURE_COOKIES` — no cookie left
      to secure.
- [ ] The GitHub OAuth App and the GitHub App themselves (manual, after the
      cut-over is verified on the tenant).

## Piece 6 — Verify on the tenant

- [ ] Deploy to Union; sign in once; dashboard renders with no further
      GitHub step.
- [ ] Create a notebook, edit it in a pod, let the pod scale to zero, reopen:
      edits survive.
- [ ] A second org member gets 403 on the first user's notebook URL.
- [ ] Snapshot, copy, delete, settings round-trip through the store.

## Piece 7 — Docs

- [ ] `.opencode/reference/architecture/app_internals.md`: Workspace Opt-In,
      Credential Model, Deploy-Time Secret Contract, Working Branch & Sync,
      Snapshots, Copy, and the route table all describe the fork design and
      all change. Largest doc delta in the plan.
- [ ] `docs/architecture/app.md` and `docs/architecture/notebook.md` (the
      section table and Promotion Paths).
- [ ] `.env` template and `.opencode/reference/devbox_workarounds.md` (the
      deploy-secret table).
- [ ] Module docstrings on every module touched.
- [ ] Plan 24: strike Pieces 1–3 (settled here), keep the console-access grant.
- [ ] ROADMAP: mark ✅ and move to Complete; add the accepted-risk follow-ups.
