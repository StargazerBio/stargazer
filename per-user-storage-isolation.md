---
title: per-user-storage-isolation
status: done
priority: high
created: 2026-10-05
pr: 14
---

Every project on the tenant runs as one IAM role, the shared
`userflyterole`, which reaches the whole tenant bucket. So a user's own code,
in a notebook or a task, can list, read, overwrite and delete every other
user's asset files, workspace notebooks and run data (task inputs and
outputs, and files Flyte uploads). Union's RBAC doesn't help: it guards
Union's API, and pods talk to S3 directly.

This makes everything a user's project writes land, by default, in a
bucket only that user's role can reach:

- **A bucket the shared role can't reach**, `stargazerbio-users`, with each
  user's files under `users/<subject>/`.
- **One IAM role per user**, holding everything that's theirs alone.
- **Their project's pods run as that role by default**, and the project's
  Flyte settings point the files Flyte uploads into their prefix.

No Union step is needed. The shared role stays, but nothing in the user
bucket is in its reach.

## Outcome

Shipped in StargazerBio/infra#14 (merge `7df1664`) and
StargazerBio/stargazer#104 (merge `4119cd9`). Each user has one IAM role,
`stargazer-user-<project>`, which every pod in their project runs as: the
dashboard and notebook pods from their deploys, task pods from the
project's settings. It reaches their prefix of the user bucket
`stargazerbio-users` (granted by its `stargazer-subject` tag in the
bucket's policy, which denies Union's shared role), their DSQL index, and
their project's run metadata in Union's bucket. Files Flyte uploads go to
the user's prefix; run metadata stays in Union's bucket. All of it is code:
the bucket and the shared policy in infra's tofu, the role, tags and
project settings in onboarding.

Verified on the tenant as the test account: the probe's refusals from both projects, the test
account's 80 files migrated as its own role, the dashboard's list, download
and upload, a notebook's save and restart, a run storing an asset, and the
germline workflow end to end with every output in the user's prefix. Unit
tier 343 and Postgres tier 19 in infra; the docs build clean. The old
`stargazer-index-u-pryce` role and the old prefix are deleted. No comments
on either PR.

Left: the hang in `upgrade` (ticket [[deploy-watch-timeout]]).

Related: [[board]].
