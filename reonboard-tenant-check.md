---
title: reonboard-tenant-check
status: backlog
priority: normal
created: 2026-10-28
---

Ticket `reonboard-unarchive` made onboarding unarchive a returning user's project, and it was checked against infra's fakes only. On the tenant, with a second address (offboarding the test account takes down its dashboard): onboard, upload an asset, offboard, onboard, and the dashboard lists the asset.

The open question is DSQL. Offboarding deletes the index's IAM role, and onboarding recreates it under the same ARN. `_ensure_iam_mapping` then finds the old `sys.iam_pg_role_mappings` row with that ARN and skips `AWS IAM GRANT`. If DSQL matches the mapping by ARN, the pods log in. If it ties the mapping to the role's unique id, as IAM trust policies do, they're refused, and offboarding should `AWS IAM REVOKE` the mapping along with deleting the role.
