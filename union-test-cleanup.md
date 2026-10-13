---
title: Tear down Union test deploys by hand
status: doing
priority: normal
created: 2026-10-13
---

Apps and runs that testing starts on the Union tenant get stopped by hand as soon as their
check is done, instead of idling until scale-to-zero (`scaledown_after` is an hour on the
dashboard, 30 minutes on notebook apps). The rule goes in AGENTS.md under Dev Process, with
the CLI commands to stop an app and abort a run, and a final listing of apps and live runs
before any report. Real users' dashboards are left alone. Branch `docs/union-test-cleanup`.

Prompted by the 2026-10-13 testing, which put several larger instances on the tenant. Among
them `nb-ceiling-probe-edit` asked for 4 CPU / 16Gi and `cap-probe` for 2 CPU / 2Gi. A sweep
of all six projects (archived included) × three domains at 22:15 UTC found every app stopped
and no runs queued, waiting, initializing, running or paused.
