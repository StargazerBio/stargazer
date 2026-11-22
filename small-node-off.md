---
title: small-node-off
status: done
priority: high
created: 2026-11-22
pr: 46
---

StargazerBio/infra#45 merged with the login app's t3a.large pin commented out (655babe), but the dashboard's was still live on Union, and the cluster has no t3a.large pool yet. The next `stargazer-users upgrade` would have left every dashboard Pending. StargazerBio/infra#46 comments out the dashboard's pin the same way, drops the unused `SMALL_NODE` imports (ruff failed on infra `main` with F401) and takes the small node out of the docs.

Verified: infra tests pass (438) and ruff is clean; `app_env.pod_template` and `login_env.pod_template` are `None` under both `STARGAZER_TARGET=union` and `devbox`. Upgrade only after it merges.

## Outcome

Shipped as StargazerBio/infra#46 (merged 2026-11-22, 3d7eb2d): both apps' pins are commented out on `main` and ruff passes there. Verified as above, before the merge. Turning them back on is ticket [[small-node-pool]].

Related: [[board]], [[login-warm]], [[small-node-pool]].
