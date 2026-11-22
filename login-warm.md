---
title: login-warm
status: review
priority: low
created: 2026-10-30
pr: 45
---

A cold login waited ~60 s on GitHub's page while the login app (infra `app/login.py`) started, against ~13 s for the dashboard behind it (measured in ticket [[login-cold-start]]), most of it an r7i.2xlarge coming up. Keeping one login replica up there would hold a whole user-workload node. Union is adding a t3a.large pool (requested 2026-11-21), and the login app moves onto it with one replica always up. Dashboards move onto it too (user's call, 2026-11-21), so one woken from idle can join the node the login replica holds.

## Plan

- [x] `Scaling(replicas=(1, 1))` on `login_env`, and a pod template whose node selector pins it to `node.kubernetes.io/instance-type: t3a.large` (StargazerBio/infra#45, draft). The selector names the instance type, which every node is labeled with, so it holds whatever Union calls the pool.
- [x] Union accepts pod templates on apps now (it refused them in May). Measured 2026-11-21 with a throwaway `pool-probe` app in `flytesnacks`: pinned to `r7i.2xlarge` it was scheduled on that pool. Pinned to `t3a.large` it stayed Pending, `incompatible requirements, key node.kubernetes.io/instance-type`, with no scale-up. Deactivated afterwards.
- [x] The pin moved to infra `app/small_node.py` (`SMALL_NODE`), shared by `login_env` and, on Union only, the dashboard's `app_env` (the devbox's node is another type). The login image now installs `kubernetes`: with only its packages, `import app.login` failed on the first commit with `No module named 'kubernetes'`, and imports now.
- [ ] Once the pool exists: deploy the login app and see it run on a t3a.large node, then merge. Not before, since `stargazer-users upgrade` redeploys the login app and every dashboard, and their pods couldn't schedule.

## Verification recipe

1. Read-only kubectl (kubeconfig through `stargazer-eks-access`): `kubectl get nodepools.karpenter.sh` lists a pool whose requirements allow `t3a.large`, on-demand, labeled `flyte.org/node-role: worker`.
2. From infra's worktree, deploy the login app (`deploy_login()`, or `stargazer-users upgrade`).
3. `kubectl get pods -n admin-development -o wide | grep login`, then `kubectl get node <node> -L node.kubernetes.io/instance-type`: `t3a.large`, and the pod stays up past an hour idle.
4. Wake the test account's dashboard (open it) and check its pod the same way in its project's namespace (`<project>-development`): `t3a.large`.
5. After the user dashboards have scaled to zero, open `stargazer.bio/login` as the test account: GitHub's page passes straight to "Opening your workspace", with no ~60 s wait.

Related: [[board]], [[login-cold-start]].
