---
title: per-user-run-metadata
status: maybe
priority: normal
created: 2026-10-29
---

Flyte's run records (each action's `inputs.pb`, `outputs.pb` and
`error.pb`) stay in Union's bucket under
`metadata/v2/stargazerbio/<project>/`, where every pod can read them
through the shared `userflyterole`. For Stargazer they hold asset metadata,
store URIs and small values; the files themselves are private since ticket
`per-user-storage-isolation`.

Moving them is one project setting, `run.run_base_dir`, pointed at the
user's `flyte/runs/` prefix. The bucket policy already lets Union's services
in there. **Measured 2026-10-29:** Union writes the records there, but its
output API reads the key from its own bucket
(`failed to get outputs: … 's3://union-us-west-2-stargazerbio/users/…/outputs.pb' not found`),
so the CLI, the console and `flyte run`'s image build step all fail. This
waits on Union reading from the bucket `run.run_base_dir` names; the user
raises it with them. Once they do, onboarding sets the setting, and the
user's role loses its write to Union's metadata prefix.
