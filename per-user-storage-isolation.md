---
title: Per-user storage isolation
status: backlog
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
