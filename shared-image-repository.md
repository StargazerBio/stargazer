---
title: shared-image-repository
status: maybe
priority: normal
created: 2026-10-29
---

Every project's images go to one ECR repository,
`791359099513.dkr.ecr.us-west-2.amazonaws.com/union/stargazerbio`, and any
user's pods can push to it: the shared `userflyterole` always could
(Union's `imagebuilder` policy), and each user's role must, since Union's
image builder runs as a task in the user's project (measured 2026-10-29,
ticket `per-user-storage-isolation`). Image tags are content hashes, so one
user could push a different image under a tag another user's tasks pull,
and run their code as that user.

Questions to settle: whether Union's builder can push to a per-project
repository (its target is the org's `union/<org>` repository), whether ECR
tag immutability on the shared repository would stop the overwrite without
breaking rebuilds, and whether pods need push at all if images are built
only by the dashboard's deploys.
