---
title: Notebooks with long names never launch
status: next
priority: normal
created: 2026-10-18
---

A workspace notebook with a long name is created fine but never launches, and
the dashboard says it's still starting forever.

## Measured (2026-10-18, Union, test account, dashboard at `d83b9b0`)

- Created "interval probe 20261018-180932" (slug
  `interval-probe-20261018-180932`, 30 characters). `/launch` answered 503
  "notebook is still starting; please retry in a moment" 31 times over about
  10 minutes.
- `App.get("nb-interval-probe-20261018-180932-edit")` in `u-pryce` failed:
  KService `nb-interval-probe-20261018-180932-edit-u-pryce-development` not
  found. The app was never created; `get app` doesn't list it.
- A notebook named "ivl", on the same dashboard straight after, launched on
  the first try.

## Cause (inferred, not confirmed)

The Knative service name is `nb-<slug>-<mode>-<project>-<domain>`, 58
characters here, and Knative names the first revision `<service>-00001`. That
makes 64, over Kubernetes' 63-character limit for a name. So the longest
slug that launches depends on the user's project name. Not checked: the
dashboard's log line for the serve error (`serve watch unconfirmed for ...`
in `/launch`), which should name the real failure.

## Fix

- The dashboard refuses a name at create whose app wouldn't fit, saying how
  long a name can be, in product terms. The limit comes from the user's
  project and domain, so it's checked in the dashboard, not the browser.
- `/launch` returns the serve error instead of "still starting" when the app
  doesn't exist, so a failure that won't clear isn't reported as one that
  will.
