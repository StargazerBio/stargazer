---
title: free-tier-4cpu-16gi
status: done
priority: normal
created: 2026-11-22
pr: 52
---

The free tier let each user's project run 16 CPU and 64Gi in total, well above what the built-in tasks ask for (1 to 6Gi each) and above other free tiers. Infra PRs 51 (CPU and memory, merged) and 52 set it to 2 runs, 8 actions, 4 CPU, 16Gi and one `nvidia-t4` GPU in `tenant.env` and the `app.config` defaults. It merges after Union swaps the tenant's A10G pool for a `g4dn.xlarge` (T4) one, since the queue only caps the type it names; the on-demand G and VT quota is 8 vCPUs, two `g4dn.xlarge`, until a raise. Existing projects and the dashboards' notebook totals take it on the next `stargazer-users upgrade` and dashboard redeploy.

## Verification recipe

After `upgrade` on the test account, the project's queue shows `cpu: 4`, `memory: 16Gi`; run the germline workflow and open two notebooks, and nothing fails, only waits.


## Outcome

Shipped as StargazerBio/infra#51 and #52 (#52 merged 2026-11-23): the free tier is 2 runs, 8 actions, 4 CPU, 16Gi and one `nvidia-t4`, after Union added the `awsg4dnxlarge` pool (g4dn.xlarge, on-demand and spot) and the limits row in the app reference names the current pools. Existing projects and dashboards take it on the next `stargazer-users upgrade`. Left: the recipe's germline run and two notebooks on the T4 limits weren't rerun here.

Related: [[board]], [[notebook-scaledown-setting]].
