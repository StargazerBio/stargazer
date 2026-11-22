---
title: small-node-pool
status: backlog
priority: low
created: 2026-11-22
---

Once Union adds a t3a.large node pool (requested 2026-11-21), turn infra's small-node pin back on: uncomment `pod_template=SMALL_NODE` on `login_env` (`app/login.py`) and on the dashboard's `app_env` (`app/admin_app.py`, Union only), with their `from app.small_node import SMALL_NODE` imports, and say in `docs/architecture/app.md` that both run on small nodes. Then consider one login replica always up (`Scaling(replicas=(1, 1))`), so a sign-in skips the ~60 s cold start ([[login-cold-start]]).

Deploy and check before merging, since `stargazer-users upgrade` redeploys the login app and every dashboard, and with no pool offering t3a.large their pods stay Pending. A soft preference (preferred node affinity) instead of the hard selector would be safe without the pool, but whether Union keeps a pod template's affinity beside its own is unchecked. The hard selector's behavior on the tenant is in [[login-warm]].

## Verification recipe

1. Read-only kubectl (kubeconfig `~/.kube/union`, `AWS_PROFILE=claude`): `kubectl get nodepools.karpenter.sh` lists a pool whose requirements allow `t3a.large`, on-demand, labeled `flyte.org/node-role: worker`.
2. From infra's worktree, deploy the login app (`deploy_login()`, or `stargazer-users upgrade`).
3. Open `stargazer.bio/login` to wake it, then `kubectl get pods -n admin-development -o wide | grep login` and `kubectl get node <node> -L node.kubernetes.io/instance-type`: `t3a.large`.
4. Wake the test account's dashboard and check its pod the same way in its project's namespace (`<project>-development`): `t3a.large`.
5. With login always up: after an idle hour its pod is still up, and opening `stargazer.bio/login` as the test account passes straight to "Opening your workspace".

Related: [[board]], [[login-warm]], [[small-node-off]], [[login-cold-start]].
