---
title: Union production deploy
status: review
priority: high
created: 2026-10-04
pr: 23
---

Tenant: `stargazerbio.us-west-2.unionai.cloud`.

Done in PRs: per-pod session keys (#2), the `STARGAZER_TARGET`
devbox/union switch, a configurable domain, and a fixed per-deploy
notebook image (#3). Union fixed the remote builder's unpullable (Nydus)
images on 2026-10-06, so deploys are back on the remote builder and the
GHCR workaround is gone. Remaining:

- [x] **Commit versions, and `upgrade` under an API key.** Each dashboard
      deploy is versioned with the deployer's commit, and `stargazer-users
      upgrade` runs from the admin's CLI under an API key in `FLYTE_API_KEY`
      (no GitHub Action yet, decided 2026-10-13). `feat/union-production-deploy`
      0a7a16a.

      Stays on `serve`, not `flyte.deploy` (decided 2026-10-13): in SDK 2.10.7
      both end in the same `App.create`, but `flyte.deploy` takes its project
      from init (each dashboard is in its user's project) and doesn't wait for
      the app to come up. `with_servecontext(version=...)` already takes a
      version. Measured 2026-10-13: redeploying under a version the app
      already has, with a changed env var, made a new revision serving the new
      value, so redeploying one commit is safe.

      Verified on the tenant 2026-10-13. `upgrade` under the admin's login from
      the branch: `u-pryce`'s dashboard spec has `fserve --version 0a7a16a`,
      `STARGAZER_VERSION` 0a7a16a, and its page footer shows 0a7a16a. Then
      under API key `stargazer-upgrade` (client 394987388058775823, org
      `admin`) from a fresh clone with no `.flyte/` config: init took the
      API-key path, resolved org `stargazerbio`, project `flytesnacks`, the
      remote builder, and the dashboard went from revision 165 to 174, still
      0a7a16a with `FLYTE_ORG` baked. The app record doesn't name who updated
      it, so that the key made the deploy is inferred from the config-free run.
