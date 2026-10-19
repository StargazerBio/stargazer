---
title: Old dashboard revisions keep running after a redeploy
status: review
priority: high
created: 2026-10-08
pr: 52
---

Each deploy makes a new Knative revision, and the old one keeps its pod for up to an
hour (`autoscaling.knative.dev/window: 1h`): three were running at once on
the devbox after three deploys (measured 2026-10-08). If each pod's
Litestream replicates its own copy of the index to the same bucket path,
that breaks Litestream's one-writer rule, and a restore could come back
from a stale copy (inferred; the restart test still found every row).
Applies to `upgrade` on Union too. The devbox tests deploy once per
session, so they add revisions quickly.

## Findings (2026-10-18)

- **No coordination between writers.** The dashboard runs Litestream 0.5.17
  (`_LITESTREAM` in `app/admin_app.py`), started as `litestream replicate
  -exec …` (`app/dashboard_launch.py`). 0.5.8 added an S3 leaser to the
  library: a `lock.json` written with `If-Match`/`If-None-Match`, with a 30 s
  TTL (litestream#1073). But nothing in `cmd/litestream` uses it at v0.5.17,
  so the `replicate` command takes no lease. Two dashboard pods running at
  once replicate to the same path without knowing about each other
  (inferred from the source).
- **What the replica looks like.** The test account's replica
  (`users/387300641116005877/index/`) held 27 LTX files across compaction
  levels 0–3 and 9. The newest files are from around each of that day's
  deploys. Levels 1–3 are rewritten by compaction, which each running
  Litestream process does on its own. So an old pod could rewrite compacted
  files even with no writes of its own (inferred, not observed).

## Controlled check (2026-10-19, before the fix)

The test account's dashboard, pointed at a throwaway root
(`stargazer-probe-revisions/`), deployed, written to, then redeployed:

- The tenant's revisions carry `autoscaling.knative.dev/window: 1h0m0s`, and
  the old revision's pod stayed Running after the new one took traffic.
- With no request reaching it, the old pod rewrote L0 transaction 2 at
  21:39:00, a minute after the new pod uploaded its own (S3 versions:
  21:38:28, 849 B; 21:39:00, 191 B).
- Both pods compacted the same files: `0001/01-02` and `0001/03-17` were each
  written twice a second apart, and the ranges overlapped (`18-34` and
  `18-41`; `01-34` and `01-3f` one level up).
- A row written straight to the old pod got a 200, overwrote transactions 3
  and 4, and was missing after a fresh restore, which held the other 62.
- `App.deactivate(wait=True)` returned at once, while both pods took another
  30–50 s to exit. So "stop, then deploy" can't tell from the Flyte API when
  the old pod's last sync is done.

## Fix

- [x] A lease beside the replica (`<root>/users/<owner>/index-lease/holder`
  and `released`, each a pod name), taken by the launcher before it
  restores. It waits for the displaced pod's release, or 60 s.
- [x] The launcher runs Litestream as a child, passes on SIGTERM, checks the
  lease every 2 s, and when it's taken over stops Litestream, releases, and
  idles. There's no liveness probe, so the idle pod isn't restarted.
- [x] Docs: `docs/architecture/app.md`, `app_internals.md`, and the
  `refuse_while_running` docstring.

## Verified (2026-10-19)

On Union, redeploying while a write went in every second: the old pod stood
down 2.6 s after the new launcher started, and the new one took over 1.7 s
later and was serving 11 s after that. 137 of 150 writes got a 200; the 13 in
between got 502s. No replica file was written twice, and compaction ranges
were contiguous. A clean stop wrote `released`, and the next cold start
restored exactly the 138 acknowledged rows without waiting. The test
account's real dashboard took its first lease without waiting and kept its
34 rows. The devbox dashboard and asset-storage tests (5) pass; in the
restart test the replacement took over 2.3 s after starting.

Left: the handover pause (ticket `index-writes-survive-redeploys`); a broken
release now takes the dashboard down (ticket
`failed-redeploy-keeps-dashboard`); the stood-down pod still lingers, idle,
for up to the hour. The first upgrade onto this runs old pods that don't
know the lease, so stop each dashboard a minute before it. Probe data is left
under `stargazer-probe-revisions/` and `stargazer-probe-revisions-2/` in the
bucket.
