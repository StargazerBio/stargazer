---
title: Per-user storage isolation
status: maybe
priority: high
created: 2026-10-05
---

Every project on the tenant runs as one IAM role, so a notebook's own code can read and write every user's
workspace objects (and all task data). Needs per-project roles scoped to
each user's prefix. The roles and policies are ours to create in our AWS
account (attaching policies to the shared `userflyterole` needs no Union
step), but per Union's BYOC docs, Union binds a custom role to a
project-domain namespace. So each new user's project would need a Union
request unless that binding can be automated.
([Union BYOC: enabling AWS resources](https://www.union.ai/docs/v2/union/deployment/byoc/enabling-aws-resources.md))

The interim mitigation is [alpha-notice](alpha-notice.md): the dashboard and the
upload form tell users not to upload sensitive data.

## A bucket per user

Deferred on 2026-10-08, when this was the end of plan 28 (now
[asset-manager-on-index](asset-manager-on-index.md)). Recorded here so the
work can start from what's known.

**The idea.** Each user gets their own bucket, and their project runs as an
IAM role that reaches only that bucket; their asset files, index replica,
workspace notebooks and run data all move into it. A bucket alone isn't
isolation: while every project shares one role that can reach every bucket,
any pod still reads any bucket. The bucket gives the role's policy one thing
to name, and makes CORS, versioning, lifecycle, cost and deletion per user.

**Known (2026-10-07):**

- **Per-project settings exist for run data and pod identity** (measured).
  `flyte get settings` on the tenant lists `storage.raw_data_path`,
  `run.run_base_dir`, `security.service_account` ("Kubernetes service account
  for task pods") and `environment_variables`, settable per org, domain or
  project with `flyte edit settings --project … --from-file`. Not tried:
  whether they take effect, or whether they reach app pods.
- **We create custom roles; Union binds them** *(Union BYOC docs)*: "Create
  your own custom role … Provide the Union.ai team with the role ARN … and
  they will bind the role to those namespaces" (project-domain). Task S3
  access is a policy on the user role or on a custom role.

**Questions to settle first:**

- **D1. Can the role binding be automated per user?** If each new project
  needs a Union ticket, onboarding can't be self-serve. Ask about binding by a
  role-name template (`stargazer-u-{project}`), or a per-namespace service
  account named in `security.service_account`.
- **D2. Do app pods get the bound role?** The dashboard and notebook pods read
  the user's bucket too.
- **D3. What else does a user role need?** Union's own buckets (code bundles,
  run metadata, images). Start from the shared user role's policy, minus the
  tenant-bucket grant.
- **D4. Do per-project `storage.raw_data_path` and `run.run_base_dir` move all
  run data into the user's bucket?** Run inputs and outputs carry asset
  metadata and file paths.
- **D5. Who creates buckets and roles?** Onboarding runs on the admin's
  machine; it would also need AWS credentials for S3 and IAM.
- **D6. Keep `users/<subject>/` inside a per-user bucket?** Redundant there,
  but one layout for local and hosted.

**Measured 2026-10-20** (read-only, for ticket `dsql-asset-index`):

- **D2: yes.** Task pods and app pods (dashboard, notebooks) both run as their
  namespace's `default` service account. In every `u-*` namespace it is
  annotated with the shared `userflyterole`, and pods get the IRSA token
  (`AWS_ROLE_ARN`, `AWS_WEB_IDENTITY_TOKEN_FILE`).
- **A per-user role needs no Union step to exist.** A role trusting
  `system:serviceaccount:<project>-<domain>:default` can be assumed from that
  namespace's token, and only from there. That's how `dsql-asset-index` gets
  per-user database access. It doesn't isolate storage, though: pods keep
  the shared role as their default credentials, and that role reaches the
  whole bucket. Withdrawing the shared role's access is what needs Union,
  since the service-account annotation is theirs. So D1 stands.

**Outline:** by hand for the test account first (bucket with Block Public
Access, versioning, encryption, CORS and a noncurrent-version expiry; role;
Union binding), measure that its pods reach their bucket and get AccessDenied
on another user's prefix, then automate in `stargazer-users onboard` and
point `STARGAZER_STORE_ROOT` at the bucket.
