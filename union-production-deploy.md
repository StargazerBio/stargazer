---
title: Union production deploy
status: next
priority: high
created: 2026-10-04
---

Tenant: `stargazerbio.us-west-2.unionai.cloud`.

Done in PRs: per-pod session keys (#2), the `STARGAZER_TARGET`
devbox/union switch, a configurable domain, and a fixed per-deploy
notebook image (#3). Union fixed the remote builder's unpullable (Nydus)
images on 2026-10-06, so deploys are back on the remote builder and the
GHCR workaround is gone. Remaining:

- [ ] **Union-native app secrets.** Dashboards carry no secret today (the
      asset manager is off for that reason). When the asset manager returns, a
      Pinata key can't be baked into `env_vars`, where the owner sees it. Move to
      `flyte create secret` plus `secrets=[flyte.Secret(...)]`, after
      confirming Union injects app secrets at all.
- [ ] **`flyte.deploy` with commit-SHA versions** in place of `flyte.serve`
      for `stargazer-users upgrade`, run from CI with an org-admin API key.
- [ ] **Resource ceilings.** Notebook resources are honored as-authored. Cap
      them with `flyte edit settings --domain production` (`task_resource.max.*`),
      after checking that the cap applies to apps and not only tasks.
