---
title: launch-row-unresolvable-run
status: doing
priority: low
created: 2026-10-27
---

A pending launch in the state table (ticket `launch-build-state`) is settled by looking up its build run with `Run.get`. A lookup that fails with anything but a Flyte runtime error, such as a run that no longer exists, is treated as a transient error and reported as building. If the run can never be found, the launch shows as building forever: `/launch` keeps answering 202 with the same build link, and neither Stop nor a redeploy clears the row.

Seen only by reading the code, not on the tenant. A fix could treat NOT_FOUND as a failure with its own reason, or let a pending row expire after some time since `updated_at`.
