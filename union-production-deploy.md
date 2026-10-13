---
title: Union production deploy
status: doing
priority: high
created: 2026-10-04
---

Tenant: `stargazerbio.us-west-2.unionai.cloud`.

Done in PRs: per-pod session keys (#2), the `STARGAZER_TARGET`
devbox/union switch, a configurable domain, and a fixed per-deploy
notebook image (#3). Union fixed the remote builder's unpullable (Nydus)
images on 2026-10-06, so deploys are back on the remote builder and the
GHCR workaround is gone. Remaining:

- [ ] **Commit versions, and `upgrade` from CI.** Each dashboard deploy is
      versioned with the deployer's commit, and `stargazer-users upgrade` runs
      from a manual GitHub Actions workflow with an API key.

      Stays on `serve`, not `flyte.deploy` (decided 2026-10-13): in SDK 2.10.7
      both end in the same `App.create`, but `flyte.deploy` takes its project
      from init (each dashboard is in its user's project) and doesn't wait for
      the app to come up. `with_servecontext(version=...)` already takes a
      version. Measured 2026-10-13: redeploying under a version the app
      already has, with a changed env var, made a new revision serving the new
      value, so redeploying one commit is safe.
