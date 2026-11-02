---
title: project-costs
status: done
priority: normal
created: 2026-10-28
pr: 12
---

The account's Cost and Usage Report export (CUR 2.0 with split cost allocation, `s3://stargazer-per-project-costs/reports/PerProjectCosts/data/BILLING_PERIOD=<yyyy-mm>/`) splits the EKS nodes' cost across the pods on them, tagged with each pod's namespace and workload. Pulled by hand on 2026-10-28, the October report reconciled: the namespaces' split costs summed to $29.34 against $29.72 of node cost over the hours split allocation covered (from 2026-10-26 22:00 UTC). A user project (`<project>-<domain>`) showed as about 4% of node cost, beside Union's own platform namespace.

Make it a Flyte task in infra that an admin runs on the tenant: it reads the latest billing period and reports the split per namespace, with project namespaces apart from the platform's, each project's workloads, and the month's spend by service. Later it runs daily and feeds the dashboard (not this ticket).

## Plan

- [x] IAM role `stargazer-costs-reader` in infra's `aws/` stack: read-only on the export's bucket, assumable only by the `default` service account of namespace `admin-development`, with its projected token, the way each user's index role is
- [x] The split as plain SQL over the period's parquet files, tested on a small synthetic report
- [x] The task, in a new `admin` project: assumes the role, finds the latest period, returns the split and renders it as a Flyte report
- [x] A deploy command that makes the `admin` project if it's missing and deploys the task
- [x] Run on the tenant against the October report, matching the hand-pulled numbers

Measured 2026-10-28: run `udfjxtnlj2xsnqmphb69` in `admin` succeeded on `2026-10` with the hand-pulled numbers (namespaces $29.33 of $29.72 node cost). A run before the role was applied was refused at `AssumeRoleWithWebIdentity`. That a user project can't assume the role is inferred from its trust policy, not run.

## Verification recipe

1. From infra's checkout, `AWS_PROFILE=claude ./stargazer-costs deploy` (the shell's profile wins over `tenant.env`'s admin one; the deploy makes no AWS call).
2. `AWS_PROFILE=claude ./stargazer-costs run`, and wait for the run to succeed (`flyte --config .flyte/union.yaml get logs <run> -p admin -d development`).
3. `Run.get(<run>).outputs()`: the namespaces' costs come to the node cost within a few cents, for the period the export's latest partition names.
4. `aws s3 cp --profile claude s3://union-us-west-2-stargazerbio/metadata/v2/stargazerbio/admin/development/<run>/a0/0/report.html .` has the same tables. The built-in browser's console session is the test account's, which can't open `admin`.
5. `flyte get run --in-phase running -p admin -d development` is empty.

## Outcome

Shipped in StargazerBio/infra#12 (merge `8097680`): the `project_costs`
task in the `admin` project, the `stargazer-costs-reader` role, and
`./stargazer-costs deploy|run`. Verified by run `udfjxtnlj2xsnqmphb69` on
the tenant, matching the hand-pulled October numbers (namespaces $29.33 of
$29.72 node cost); 332 tests pass. Left: running it daily and showing the
numbers on the dashboard, ticket [[project-costs-daily]].

Related: [[board]].
