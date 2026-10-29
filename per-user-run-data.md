---
title: per-user-run-data
status: maybe
priority: normal
created: 2026-10-28
---

Flyte's run data (task inputs and outputs, offloaded literals, code
bundles) lives in the tenant bucket `union-us-west-2-stargazerbio`, which
every project's pods reach through the shared `userflyterole`. Any user's
notebook code can read any other user's run data. For Stargazer that's
asset metadata and store URIs rather than file bytes, which move behind
per-user roles in ticket `per-user-storage-isolation`, but a task that
returns a Flyte `File` or `DataFrame` of its own puts the bytes there too.

Isolating it means each project's pods run as their own role, which Union
binds to the project-domain namespace
([Union BYOC: enabling AWS resources](https://www.union.ai/docs/v2/union/deployment/byoc/enabling-aws-resources.md)).
The service-account annotation is Union's, so taking the shared role away
from a namespace needs them.

**Questions to settle first:**
- **D1. Can the binding be automated per user?** If each new project needs
  a Union request, onboarding can't be self-serve. Ask about binding by a
  role-name template (`stargazer-index-{project}`), or a per-namespace
  service account named in the `security.service_account` setting.
- **D4. Do per-project `storage.raw_data_path` and `run.run_base_dir` move
  all run data into a prefix the user's role reaches?** Measured
  2026-10-07: `flyte get settings` on the tenant lists both, plus
  `security.service_account` and `environment_variables`, settable per
  org, domain or project with `flyte edit settings --project … --from-file`.
  Not tried: whether they take effect, or whether they reach app pods.
- **What the user's role would need** beyond its own prefix: Union's
  buckets (code bundles, run metadata, the fast-registration bucket) and
  ECR pulls. Start from the shared role's policies, minus the tenant
  bucket grant.
