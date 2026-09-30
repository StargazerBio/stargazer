# 24 — Union Console Handoff (per-user project access)

Let a dashboard user click through to the Union console and see the
executions in *their own* project, authenticated as themselves, without a
manual invite step.

**Why.** The Union console is a surface worth exposing rather than
re-implementing — execution graphs, logs, retries, and inputs/outputs are
already there. Today a user who landed on it would see nothing:
`provision_user()` creates the per-user Flyte project
(`app/provision.py:48`) and grants **no role binding to any Union
identity**. Executions run under the admin pod's in-cluster identity into a
project named for the GitHub user; the user themself has no Union principal
and no access.

## What Union confirmed

Answers from Union, which fix the shape of this plan:

| Question | Answer | Consequence |
|---|---|---|
| Can Stargazer be an OIDC relying party of Union (one grant total)? | **No** | Two GitHub OAuth Apps. Users consent to each once, ever; every later hop is a silent redirect. |
| Are users auto-provisioned on first IdP login? | **No** (planned, no timeline) | We must create the binding ourselves at signup. |
| Can role bindings be created programmatically? | **Yes** | `flyteplugins.union.remote` — `Role`, `Policy`, `Assignment`. Not CLI-only, so the admin pod can call it directly. |
| Do console deep links survive auth? | **Yes** | Link straight to the execution subpage; no landing-page bounce. |

The apparent contradiction between rows 2 and 3 resolves: **assignments
implicitly create the user record**, so a binding can be written for someone
who has never logged into Union. That is what closes the flow.

Row 1's "no" rules out Stargazer acting as an OIDC *client* of Union. It does
**not** rule out the single-OAuth-App outcome, which Piece 2 reaches from the
other direction — by putting the dashboard behind Union's auth rather than
by federating to it.

## Scope

**In:** the per-user access grant (role, policy, assignment) inside
`provision_user`, the dependency that provides it, and the dashboard link
out to the console.

**Also in:** collapsing the two GitHub OAuth Apps into one (Piece 2), if
Piece 0 shows it is possible.

**Out:** replacing any part of the dashboard with the console; changing how
executions are launched (still the admin identity, still into the per-user
project); where workspace state is stored (see the open question at the
bottom).

**Deferred:** moving project naming off the mutable GitHub login onto
`github_id` (see Piece 3 — decide, don't necessarily do).

---

## Piece 0 — Verify before building

Three unknowns can invalidate the rest of the plan. Settle all three first.

- [ ] **What identity does Union forward to an app behind
      `requires_auth=True`?** This is the most decisive question in the plan
      — it picks the branch in Piece 2. The SDK gives no answer: the flag
      only flips `allow_anonymous` in the app's `SecurityContext`
      (`flyte/app/_runtime/app_serde.py:331`), and there is no header
      contract, no `user_info`, nothing in `_context.py`. The gate is
      binary. Ask Union specifically:
      - Is a user identity injected into the request (header, JWT, or
        otherwise)?
      - Does it carry the **GitHub login**, or only an opaque subject?
        Project naming, fork naming, and `STARGAZER_OWNER` all derive from
        the username, so an opaque subject means maintaining a
        subject→login mapping.
- [ ] **Does the admin pod's identity have permission to create policies and
      assignments?** These are org-admin-level operations, and the in-cluster
      identity (`flyte.init_in_cluster()`, `app/init.py`) was only ever
      exercised for project creation and app serving. From an admin pod
      shell, attempt a `Policy.create` against a throwaway project. If it is
      denied, this whole flow needs a separately-credentialed path (a
      dedicated admin API key in `_RUNTIME_SECRETS`) and Piece 4 changes
      shape.
- [ ] **Do policy bindings accept a wildcard/pattern for `project`?** The
      documented shape names a concrete project:

      ```python
      Policy.create(
          "Team Prod Access",
          bindings=[{"role": "Production Runner",
                     "resource": {"project": "my-project",
                                  "domain": "production"}}],
      )
      ```

      With per-user projects that means **one policy per user** — N policies
      for N users, plus N assignments. Workable, but if a wildcard is
      supported, collapse to one shared policy + per-user assignments
      instead. Ask Union; the answer decides `_ensure_policy` below.

---

## Piece 1 — Create the Union OAuth App (manual)

Not code. Do this in parallel with the rest; nothing here blocks Piece 3+.

- [ ] Create a **new OAuth App** — not a GitHub App, and not the existing
      dashboard app — owned by the **Stargazer Bio org**, not a personal
      account.
- [ ] Authorization callback URL: `https://auth.hosted.unionai.cloud/idps/callback`
- [ ] Name it distinctly (e.g. "Union Hosted SSO") so it is never confused
      with the dashboard's app and nobody later "consolidates" the two.
- [ ] Send the Client ID over Slack (plaintext is fine).
- [ ] Send the Client Secret **PGP-encrypted**, and verify their key
      fingerprint out-of-band (read it on a call) before encrypting — Slack
      is the same channel the ciphertext travels over, so fetching the key
      over it alone proves nothing.
- [ ] Encrypt locally rather than in a web tool, so plaintext never enters a
      third-party page:

      ```bash
      gpg --import union-pubkey.asc
      gpg --fingerprint <keyid>          # compare against the out-of-band value
      pbpaste | gpg --encrypt --armor --recipient <keyid> | pbcopy
      pbcopy < /dev/null                 # clear the clipboard afterward
      ```

**Do not** repoint the existing dashboard OAuth App's callback at Union. An
OAuth App has exactly one callback URL; editing it breaks `/auth/callback`
(`app/admin_app.py:295`) and locks out every dashboard user.

---

## Piece 2 — Collapse to a single OAuth App

**Goal:** one GitHub OAuth App (Union's), one consent screen ever, and the
dashboard and console sharing a single Union session. Stargazer's own OAuth
App is deleted.

**Mechanism:** set `requires_auth=True` on the dashboard's `AppEnvironment`.
Union's serving layer then gates the endpoint behind Union's own auth, which
is GitHub-backed once the IdP is wired. Both surfaces sit behind the same
identity, so the hop to the console carries no second authorization.

This is roadmap item 2 ("Identity-gated production auth") arriving early.
Both app envs are `requires_auth=False` today — `app/admin_app.py:227` and
`app/per_notebook.py:253` — a devbox concession where the proxy's
session-cookie check is the only gate. `requires_auth` defaults to `True` in
the SDK (`flyte/app/_app_environment.py:145`).

**What this does not solve.** Sharing one OAuth App by URL is impossible and
should not be attempted. GitHub matches `redirect_uri` against the
registered callback on **exact host and port**, allowing only a subdirectory
of the registered path. Union's callback lives on
`auth.hosted.unionai.cloud`, a host we do not control, so no dashboard
deployment on any domain can ever match it. The collapse works only by
removing our OAuth flow entirely, not by sharing a registration.

### The branch

Gated on Piece 0's identity-forwarding answer:

- [ ] **Identity is forwarded, carrying the GitHub login** → do the collapse.
      Delete Stargazer's OAuth App, drop `GITHUB_CLIENT_ID` /
      `GITHUB_CLIENT_SECRET` from `_RUNTIME_SECRETS`, and read identity from
      whatever Union injects.
- [ ] **Identity is forwarded but opaque** → collapse is still possible, but
      add a subject→login mapping first, populated at the one moment we
      still know both. Weigh against just keeping two OAuth Apps.
- [ ] **No identity is forwarded** → collapse is impossible. Stay on two
      OAuth Apps and proceed with the rest of this plan unchanged. The user
      cost is one extra consent screen, once, ever.

### Consequences if we collapse

- [ ] **The fork loses its credential.** The OAuth token's real job is the
      one-time fork needing `public_repo` (`app/oauth.py:29`). With no
      GitHub token, the fork must move to a GitHub App installation token,
      flipping the handshake order: install the App on the account first,
      then fork upstream in with the App token. **Verify** that
      `POST /repos/{owner}/{repo}/forks` actually works with a user-account
      installation token before betting on it — if it does not, the
      workspace opt-in needs a different design entirely. (See the workspace
      storage question below, which may remove this problem rather than
      solve it.)
- [ ] **The session layer becomes subordinate.** The Fernet-encrypted
      cookie, `SessionData`, and the proxy's mirrored `_cookie_is_valid`
      check are all built around owning the OAuth flow. Per-notebook pods
      are `requires_auth=False` with that cookie as their only gate;
      flipping them changes the proxy's auth model too. Blast radius:
      `session.py`, `proxy.py`, `admin_app.py`, `per_notebook.py`.
- [ ] Decide whether per-notebook pods move to `requires_auth=True` in the
      same pass or stay on the cookie. Doing both at once is a larger
      change but avoids running two auth models side by side.

### Sequencing

Do this **before** Piece 5. It changes what `provision_user` receives and
whether Piece 3's subject question is ours to answer at all — under the
collapse, the subject comes from Union rather than from our own OAuth
callback.

---

## Piece 3 — Determine the subject format (empirical)

Blocked on Union finishing the IdP wiring. No round-trip with them needed.

- [ ] Log into Union once via GitHub, then call `User.get().subject()` —
      `flyte.remote.User` already ships in the installed SDK
      (`flyte/remote/_user.py:36`).
- [ ] Record what the GitHub connector emits: the **numeric id** (stable) or
      the **login** (mutable — users rename).
- [ ] Use `user_subject=`, **not** `email=`. The dashboard requests only
      `read:user` (`app/oauth.py:29`), which yields no verified email, and
      GitHub returns `null` for anyone with a private email — so
      email-keyed bindings would silently fail for a subset of users.
- [ ] **Decision, if the subject is the numeric id:** `sanitize_project_id`
      derives the project name from the mutable login
      (`app/provision.py:27`), while `github_id` is already captured into the
      session (`app/session.py:77`, set at `app/admin_app.py:693`) and never
      read. A rename would then desync the project name, the fork name, and
      the Union subject. Renaming projects later means migrating namespaces,
      so decide **now** whether to move project naming onto `github_id`
      while there are no users. Record the decision here either way.

---

## Piece 4 — Dependency + role definition

- [ ] `uv add "flyteplugins-union>=0.10.2,<0.11"` — the package providing
      `flyteplugins.union.remote` ("Union SDK — Proprietary extensions for
      Flyte"). Bounded per the project convention: it is pre-1.0 proprietary
      code whose API we import directly.
- [ ] Confirm it reaches the admin image. `app_env`'s image builds via
      `.with_uv_project(PROJECT_ROOT / "pyproject.toml",
      project_install_mode="install_project")` (`app/admin_app.py:211-213`),
      so a `pyproject.toml` dep should be baked in with no image change —
      verify rather than assume.
- [ ] Define the role **once**, at deploy time, not per user. Least
      privilege: users *view* executions in the console; they never launch
      from it (launches come from the dashboard under the admin identity).

      ```python
      Role.update("Stargazer Notebook Viewer",
                  actions=["view_flyte_inventory", "view_flyte_executions"])
      ```

      Tighter than built-in Contributor. Confirm these two action names
      cover the console's execution view — if logs or inputs/outputs render
      empty, widen deliberately and note why.
- [ ] Decide where role creation lives: a deploy-time step in `app:main`, or
      a one-shot script. It is not per-user work and must not sit in the
      login path.

---

## Piece 5 — Grant access in `provision_user`

### Tests first

`tests/unit/` against a faked `flyteplugins.union.remote`; assert on the
calls made, not on a live control plane.

- [ ] New user → project created, policy created, assignment created, in
      that order.
- [ ] Returning user → all three are no-ops; no duplicate assignment.
- [ ] Existing project but missing assignment (the state every user created
      before this ships is in) → assignment is created. This is the
      backfill path; it must work without deleting anything.
- [ ] Binding targets `domain="development"`.
- [ ] Assignment is keyed on `user_subject`, never `email`.
- [ ] Policy/assignment failure does **not** prevent login (see failure
      policy below) — the callback still completes and the session is
      issued.

### Implementation

- [ ] `_ensure_policy(project_id)` and `_ensure_assignment(subject,
      policy)`, mirroring the existing `_ensure_project` shape in
      `app/provision.py:38` — try a get, fall through to create. If the API
      has no get, catch the already-exists error rather than pre-checking.
- [ ] `provision_user()` grows a `github_subject` parameter; the caller at
      `app/admin_app.py:646` passes it from the session.
- [ ] **`domain="development"`** — the docs example uses `production`, but
      every call site in this codebase hardcodes `development`
      (`app/admin_app.py:1055`, `1271`, `1323`, …). A mismatched domain
      yields an empty console, which looks exactly like a broken login.

### Failure policy

- [ ] A failed grant must not block login. The user still gets a working
      dashboard; only the console hop degrades. Log the failure at ERROR
      with the subject and project — a silent "no access" is
      indistinguishable from "Union is down", and this codebase has already
      been bitten once by a silently-skipped auth step (the
      `GITHUB_APP_PRIVATE_KEY` incident, `app_internals.md`).
- [ ] Make the grant re-attempted on subsequent logins, so a transient
      failure self-heals rather than stranding the user permanently.

### Interaction with Roadmap #2

`provision_user()` runs **inline in the OAuth callback**, and Roadmap item 2
already flags that a slow provision can outlive the browser's redirect
window. This plan adds **two more control-plane round-trips** to that path,
making the existing problem materially worse.

- [ ] Measure the added latency on a cold signup before shipping.
- [ ] If it is significant, promote Roadmap #2 (async provisioning + status
      polling) to a prerequisite rather than a follow-up.

---

## Piece 6 — The link out

- [ ] Add a "View in Union console" link on the dashboard, deep-linked to
      the user's project rather than the console root — Union confirmed
      subpage links survive the auth redirect, so the user lands where they
      clicked.
- [ ] Resolve the target URL from the user's project id
      (`sanitize_project_id`) plus `development`.
- [ ] First click of a session bounces through GitHub for the consent screen
      (once ever, for Union's OAuth App); afterwards it is a silent
      redirect. No spinner or interstitial needed.
- [ ] Per AGENTS.md, keep the UI string in product terms — "View executions
      in the Union console", not a description of the binding mechanism.

---

## Piece 7 — Docs

- [ ] `app/provision.py` module docstring — it currently describes provision
      as "one idempotent step per login"; it becomes three.
- [ ] `.opencode/reference/architecture/app_internals.md` — the Credential
      Model table gains the Union identity; note that the admin still
      launches executions under its own identity and the user's binding is
      read-only.
- [ ] `docs/architecture/app.md` — the human-facing companion.
- [ ] If Piece 0 forces a dedicated admin API key, add it to the Deploy-Time
      Secret Contract table in `app_internals.md` **and** to
      `_partial_app_creds()`-style validation in `app/admin_app.py`, so a
      missing key fails loudly at deploy instead of silently degrading every
      user's console access.
- [ ] Mark this item ✅ and move it to Complete in `ROADMAP.md`.

---

## Related — workspace state moves off the fork

The fork is no longer the workspace storage backend; that work is
[`25_workspace_state_object_storage.md`](./25_workspace_state_object_storage.md).

It matters here because it removes this plan's hardest dependency. Piece 2's
collapse otherwise has to relocate the one-time fork onto a GitHub App
installation token, since the OAuth token that performs it today disappears
with our OAuth App. Once saving no longer requires a fork, that problem stops
existing rather than needing a solution — the fork happens only when someone
opts into publishing, on a path that still has its own credentials.

**Sequencing:** if both plans are in flight, land plan 25's Piece 6 (fork
demoted to opt-in) before this plan's Piece 2, and the fork-credential
checkbox there can be struck rather than solved.
