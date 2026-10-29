---
title: project-costs
status: doing
priority: normal
created: 2026-10-28
---

The account's Cost and Usage Report export (CUR 2.0 with split cost allocation, `s3://stargazer-per-project-costs/reports/PerProjectCosts/data/BILLING_PERIOD=<yyyy-mm>/`) splits the EKS nodes' cost across the pods on them, tagged with each pod's namespace and workload. Pulled by hand on 2026-10-28, the October report reconciled: the namespaces' split costs summed to $29.34 against $29.72 of node cost over the hours split allocation covered (from 2026-10-26 22:00 UTC). A user project (`<project>-<domain>`) showed as about 4% of node cost, beside Union's own platform namespace.

Make it a Flyte task in infra that an admin runs on the tenant: it reads the latest billing period and reports the split per namespace, with project namespaces apart from the platform's, each project's workloads, and the month's spend by service. Later it runs daily and feeds the dashboard (not this ticket).

## Plan

- [ ] IAM role `stargazer-costs-reader` in infra's `aws/` stack: read-only on the export's bucket, assumable only by the `default` service account of namespace `admin-development`, with its projected token, the way each user's index role is
- [ ] The split as plain SQL over the period's parquet files, tested on a small synthetic report
- [ ] The task, in a new `admin` project: assumes the role, finds the latest period, returns the split and renders it as a Flyte report
- [ ] A deploy command that makes the `admin` project if it's missing and deploys the task
- [ ] Run on the tenant against the October report, matching the hand-pulled numbers
