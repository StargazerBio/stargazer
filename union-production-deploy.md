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

- [ ] **`flyte.deploy` with commit-SHA versions** in place of `flyte.serve`
      for `stargazer-users upgrade`, run from CI with an org-admin API key.
