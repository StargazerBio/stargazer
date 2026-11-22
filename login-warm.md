---
title: login-warm
status: review
priority: low
created: 2026-10-30
pr: 45
---

A cold login waited ~60 s on GitHub's page while the login app (infra `app/login.py`) started, against ~13 s for the dashboard behind it (measured in ticket [[login-cold-start]]), most of it an r7i.2xlarge coming up. Keeping one login replica up there would hold a whole user-workload node. Union is adding a t3a.large pool (requested 2026-11-21), and the login app and every dashboard move onto it (StargazerBio/infra#45). Login keeps scaling to zero for now (user's call, 2026-11-21); one replica always up on the t3a pool is the step after.

## Plan

- [x] A pod template on `login_env` whose node selector pins it to `node.kubernetes.io/instance-type: t3a.large` (StargazerBio/infra#45, draft). The selector names the instance type, which every node is labeled with, so it holds whatever Union calls the pool.
- [x] Union accepts pod templates on apps now (it refused them in May). Measured 2026-11-21 with a throwaway `pool-probe` app in `flytesnacks`: pinned to `r7i.2xlarge` it was scheduled on that pool. Pinned to `t3a.large` it stayed Pending, `incompatible requirements, key node.kubernetes.io/instance-type`, with no scale-up. Deactivated afterwards.
- [x] The pin moved to infra `app/small_node.py` (`SMALL_NODE`), shared by `login_env` and, on Union only, the dashboard's `app_env` (the devbox's node is another type). The login image now installs `kubernetes`: with only its packages, `import app.login` failed on the first commit with `No module named 'kubernetes'`, and imports now.
- [ ] Once the pool exists: deploy the login app and see it and a woken dashboard run on t3a.large nodes, then merge. Not before, since `stargazer-users upgrade` redeploys the login app and every dashboard, and their pods couldn't schedule.
- [ ] Later: `Scaling(replicas=(1, 1))` on `login_env`, so a sign-in skips the cold start. Tried on infra#45's first commit and taken back out.

## Verification recipe

1. Read-only kubectl (kubeconfig through `stargazer-eks-access`): `kubectl get nodepools.karpenter.sh` lists a pool whose requirements allow `t3a.large`, on-demand, labeled `flyte.org/node-role: worker`.
2. From infra's worktree, deploy the login app (`deploy_login()`, or `stargazer-users upgrade`).
3. Open `stargazer.bio/login` to wake it, then `kubectl get pods -n admin-development -o wide | grep login` and `kubectl get node <node> -L node.kubernetes.io/instance-type`: `t3a.large`. Once always up, the pod also stays up past an hour idle.
4. Wake the test account's dashboard (open it) and check its pod the same way in its project's namespace (`<project>-development`): `t3a.large`.
5. Once always up, after the login app's idle hour, open `stargazer.bio/login` as the test account: GitHub's page passes straight to "Opening your workspace", with no ~60 s wait.

Related: [[board]], [[login-cold-start]].
