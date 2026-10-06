# 26 — Per-User Dashboards in Project-Isolated Projects

Replace the one shared admin app with **one dashboard app per user, deployed
into that user's own project**. An org admin runs an onboarding command that
creates the user, their project, their access grant, and their dashboard in
one pass. Nothing that runs on the tenant needs more than the access it
already has.

Builds on [plan 25](./25_workspace_state_object_storage.md): Union auth as
the only login, workspace notebooks on object storage, no GitHub in the app
tier. Plan 25's admin work (identity from Union headers, the workspace store,
the deletions) is the starting point; this plan turns that multi-user admin
into a single-owner dashboard.

## Why

Measured on the tenant (2026-10-05/06) with a test account:

- **Union's app gate needs view permission on the app's project.** A
  signed-in org member with no role on the app's project gets **403**; with
  `viewer` on that project they get in. Org membership alone isn't enough.
- **Viewer exposes the whole project in the console.** A shared admin would
  force every user to have `viewer` on its project. They then see every app in
  it, and probably its spec and env vars too. They can't stop or scale it,
  but it's poor UX and leaks whatever is baked into the spec.
- **Gate decisions are cached per browser session** for several minutes.
  Granting or revoking access only takes effect on a fresh session or after
  the cache expires.
- **Project creation needs org admin.** The admin app's in-cluster identity
  can't create projects, and giving an internet-facing app that permission is
  the wrong trade.

A per-user dashboard sits in the one project each user needs anyway. No
front-door grant, no shared service, no runtime provisioning.

## What the user sees

1. An admin onboards them: they get Union's invite email.
2. They sign in with GitHub (the only login) and open **their** dashboard URL.
3. Everything works as in plan 25: run tutorials, author and save notebooks,
   launch them. In the Union console they see only their own project.

## Settled design decisions

- **One dashboard app per user, in `u-<handle>`.** Readable, unique project
  ids; the user's subject rides on a project label and is what onboarding
  looks projects up by. Same app definition for
  everyone. The owner is baked into the app's env at deploy, not derived from
  the request.
- **Owner check in the dashboard.** Union proves the visitor can view the
  project; the dashboard additionally 403s anyone whose `X-User-Subject`
  isn't the owner (org admins can view every project). Same rule the notebook
  proxy already applies.
- **Onboarding is a manual admin command.** Union requires a manual invite
  anyway, so provisioning rides on it. Runs locally with the admin's own CLI
  identity. No privileged credential is deployed anywhere.
- **Users get built-in `contributor` on their own project only, nothing
  org-wide.** They can run, deploy and stop things in their project from the
  console (it's theirs), and see nothing else.
- **Notebooks launch into the same project as the dashboard.** The dashboard
  serves per-notebook apps with the platform's in-cluster identity, which
  already has contributor rights.
- **Images are built once per release**, not per user. The deployer builds
  the dashboard and notebook images, and onboarding/upgrade deploy those
  exact URIs (the same pattern plan 25 uses for the notebook image).
- **Stable URLs via `flyte.app.Domain(subdomain=…)`**: the subdomain is the
  project id, so it's unique and readable, and users can bookmark it.
- **Pinata is not baked into dashboards.** A per-user app's spec is readable
  by its owner, so a shared Pinata key would leak to every user. The Assets
  page is disabled until the storage plan lands (storage is tabled).

## Accepted risks and open questions

Recorded, not solved here. Each has (or gets) a ROADMAP entry.

- **The platform key is org-wide.** Every app and task pod authenticates as
  `stargazerbio-EAGER_API_KEY-union-us-west-2`, bound to org-wide
  `contributor`. Code in a user's notebook can read it and act in any
  project. Ask Union: can an app run without `EAGER_API_KEY`, or with a key we
  supply?
- **Shared IAM role** for object storage (already on the ROADMAP).
- **Revocation lag** from the per-session gate cache. Offboarding should
  also stop the user's apps rather than rely on the gate alone.
- **Unverified, checked in Piece 0:** that `Domain(subdomain=…)` works on
  the tenant; that `User.create` returns the subject before first sign-in;
  that an invited user's GitHub sign-in maps to that same subject.

---

## Piece 0 — Verify before building

- [x] `flyte.app.Domain(subdomain="…")` gives a stable, predictable URL on
      the tenant, and survives a redeploy. *(2026-10-06: a probe app with
      `subdomain="sg-probe-pryce"` in `u-387300641116005877` served at
      `https://sg-probe-pryce.apps.stargazerbio.us-west-2.unionai.cloud`, the
      same URL after a redeploy; 302 to sign-in anonymous, 200 signed in.
      **A second app asking for a taken subdomain, in another project, is
      not rejected: it hangs at "App created" with no endpoint**, so
      onboarding must detect collisions itself.)*
- [ ] `User.create(...)` returns a subject immediately (it does, per the
      plugin source: the create response carries the id), and it is the subject
      the user's first GitHub sign-in arrives with (`X-User-Subject`). Use a
      real second address for this one test.
- [x] `flyte create user` without `--policy` attaches no org-wide policy (or
      record which one it attaches so onboarding can remove it).
      *(`User.create` sends only the user spec; `--policy` is a separate
      `Assignment.create` afterwards (plugin 0.15.1 source). The invited test
      account's assignment has no roles and only the three policies we added
      by hand, so the server adds nothing either.)*
- [x] An app in `u-<subject>` is reachable by that user with only
      `contributor` on `u-<subject>/development`, and refused (403) for a user
      with no role there. *Half measured (2026-10-06, plan 25's tenant
      run): the test account, whose only grant on `u-387300641116005877` is
      `contributor` via policy `stargazer-user-387300641116005877`, reached
      its notebook app there. The no-role 403 was measured earlier the same
      day on the front-door probe (no role on the project → 403).*
- [x] Measure a dashboard cold start after scale-to-zero. If it's bad, decide
      on `min_replicas=1` per user versus accepting it. *(Plan 25's admin,
      same image recipe: 19.6s for the first request after scale-to-zero,
      0.2s warm. **Accepted for now**: a warm replica per user costs a pod
      each, all day. Revisit if users complain.)*

## Piece 1 — Single-owner dashboard

Turn plan 25's multi-user admin into a dashboard that serves exactly one
owner.

### Tests first

- [x] Owner's subject in `X-User-Subject` → dashboard renders.
- [x] Any other subject → 403. Missing header → 403. Unset owner env → 403
      (fail closed).
- [x] Workspace routes act on the owner's notebooks only, regardless of what
      the request claims.
- [x] `/launch` serves into the dashboard's own project and passes the owner
      to the per-notebook env.

### Implementation

- [x] Owner from env (`SG_OWNER_SUBJECT`, the same name the notebook proxy
      uses), project from `FLYTE_PROJECT`. Delete `provision_user`,
      `project_id` derivation from the request, and the provisioning-failed
      notice.
- [x] `require_user` becomes an owner check that returns the owner's display
      details from the claim headers.
- [x] ~~`_launched` becomes a flat per-dashboard map (one owner).~~ Already
      gone: plan 25 reads running notebooks live from the control plane.
- [x] Assets page and routes: disabled with a product-terms notice; no
      Pinata key in the env.
- [x] Rename the app env from `admin-app` to `dashboard` and update module
      docstrings. (The module stays `app/admin_app.py` until Piece 3 replaces
      its deploy entrypoint.)
- Done as one app-wide middleware so static files and the asset routes are
  gated too; only `/health` is open. Measured: a local uvicorn with
  `SG_OWNER_SUBJECT` set returns 200 for the owner and 403 for another
  subject or none, on `/`, `/assets` and `/static/*`.

## Piece 2 — The onboarding command

`app/onboard.py` (the `stargazer-users` project script; deploy entrypoints live in `app/` per AGENTS.md), run by an org admin.

### Tests first

Against a faked `flyteplugins.union.remote` and `flyte.remote`, asserting the
calls and their order. Small and explicit; no live control plane.

- [x] New user → user created, project created, policy bound to that
      project only, assignment by `user_subject`, dashboard deployed with
      `SG_OWNER_SUBJECT` and the subdomain. In that order.
- [x] Existing user (found by email) → no create, the rest is idempotent.
- [x] Re-running for an onboarded user is a no-op apart from redeploying the
      dashboard.
- [x] Handle collisions get a suffix, never overwrite another user's
      subdomain.

### Implementation

- [x] `onboard --email … --first-name … --last-name … [--handle …]`:
      1. `User.listall(email=…)` → existing subject, else `User.create(...)`.
      2. Ensure the user's project: the active project labeled
         `managed-by=stargazer`, `union-subject=<subject>` if there is one,
         else a new `u-<handle>` (suffixed `-2`, `-3`… past any taken id,
         archived ones included). **Readable ids** replace `u-<subject>`:
         nothing keys on the project id, so the subject label is the real
         key and the id only has to be unique.
      3. Ensure policy `stargazer-<project>` binding `contributor` on
         `<project>/<domain>`; assign it by `user_subject`. Invites attach
         nothing org-wide (Piece 0), so there's nothing to remove.
      4. Deploy the dashboard into the project from the release's image URI,
         with `SG_OWNER_SUBJECT`, `STARGAZER_WORKSPACE_ROOT`, `FLYTE_ORG`, and
         subdomain `<project>` (unique because project ids are; Union
         won't reject a taken subdomain, per Piece 0).
      5. Print the dashboard URL.
- [x] `upgrade`: redeploy every active `managed-by=stargazer` project's
      dashboard. (No `--email` form until it's needed.)
- [x] `offboard --email …`: stop the user's apps, unassign their policy.
      Projects can only be archived, never deleted; archive it. Workspace
      objects are left in place.
- [x] Add `flyteplugins-union` with a bounded pin (`>=0.15.1,<0.16`, in the `landing` extra), per AGENTS.md.

## Piece 3 — Release flow

- [ ] Replace `python -m app.admin_app`'s deploy with a release command:
      build the dashboard and notebook images, record their URIs, then
      `upgrade --all`. No shared admin is deployed.
- [ ] Retire the shared `admin-app` deployment on the tenant once dashboards
      are verified.

## Piece 4 — Verify on the tenant

Using `pryce@stargazer.bio` as the durable test account.

- [ ] Clean up the front-door probes: role `frontdoor-probe-exec`, policies
      `frontdoor-probe-*`, apps `front-door-probe` and `auth-probe`.
- Already in place from plan 25's tenant run: project
  `u-387300641116005877` (labels `managed-by=stargazer`,
  `union-subject=387300641116005877`) and policy
  `stargazer-user-387300641116005877` (contributor on its development domain),
  assigned to the test account. Onboarding's existing-user path should find
  both and leave them alone. Also leftover: the `project-create-probe` task
  in `flytesnacks`.
- [ ] Onboard the test account (existing-user path). Fresh session → its
      dashboard loads at the stable URL; the console shows only
      `u-387300641116005877`.
- [ ] Signed in as the admin account (who can view every project), the test
      account's dashboard → 403 from the owner check.
- [ ] Create, edit, scale to zero, reopen a notebook: edits survive (plan 25's
      flow, now from a per-user dashboard).
- [ ] `upgrade --all` redeploys without changing the URL.

## Piece 5 — Docs

- [ ] `docs/architecture/app.md` and `app_internals.md`: topology (no shared
      admin), the onboarding flow, the owner check, the release flow.
- [ ] The deploy-secret table in `.opencode/reference/devbox_workarounds.md`.
      If the README's deploy notes go stale, flag it (the README is
      human-owned).
- [ ] Plan 24: mark the console-access grant as delivered by onboarding.
- [ ] ROADMAP: move to Complete; keep the Union questions and risks as
      entries.
