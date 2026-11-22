---
title: free-tier-4cpu-16gi
status: review
priority: normal
created: 2026-11-22
pr: 51
---

The free tier let each user's project run 16 CPU and 64Gi in total, well above what the built-in tasks ask for (1 to 6Gi each) and above other free tiers. Infra PR 51 sets it to 4 CPU and 16Gi in `tenant.env` and the `app.config` defaults. Runs, actions and the GPU are unchanged. Existing projects and the dashboards' notebook totals take it on the next `stargazer-users upgrade` and dashboard redeploy.

## Verification recipe

After `upgrade` on the test account, the project's queue shows `cpu: 4`, `memory: 16Gi`; run the germline workflow and open two notebooks, and nothing fails, only waits.

Related: [[board]], [[notebook-scaledown-setting]].
