---
title: save-status-poll
status: done
priority: low
created: 2026-10-31
pr: 116
---

A local `docker run` logs `GET /__sg__/save-status 200` about every 5 s. The save banner on every marimo page polled it every 10 s, and two open pages doubled that. Poll every 30 s instead, and leave the banner out of the page when the pod has no store (a local `docker run`): nothing is saved there, so its warning is wrong and its poll is only noise. The workspace save interval (`SG_SAVE_INTERVAL_SECONDS`) is a separate setting and already defaults to 30 s.

## Verification recipe

Run the image with the branch's `runtime/save_banner.html` mounted over `/usr/local/lib/save_banner.html` on a spare port, with a store (below) so the banner is there at all, open the notebook in a visible tab, and read `docker logs --timestamps` for about 90 s: `save-status` every 30 s, marimo's `/api/usage` every 10 s (proof the tab isn't throttled). Measured 2026-10-31: 16:49:44, 16:50:14, 16:50:44, 16:51:14, 16:51:44.

For the store check, run it twice on spare ports with both `proxy.py` (over `/usr/local/lib/sg_proxy.py`) and `save_banner.html` mounted: once as `docker run` runs it, and once with `STARGAZER_WORKSPACE_ROOT=/tmp/store` and `SG_OWNER_SUBJECT` set. `curl -H 'Accept: text/html'` the page from each: `sg-save-banner` only on the one with a store, and `/__sg__/agent/` on both.

## Outcome

Shipped in PR #116 (merge `1a2af3c`). The save banner polls `/__sg__/save-status` every 30 s instead of 10, and the proxy leaves it out of the page when the pod has no store (a local `docker run`); the agent redirect is still added everywhere. Verified with the recipe above: polls at 30 s intervals with the tab visible, no banner and no polls without a store, the banner with one, and a proxy test that failed before the change. Left: marimo's own `/api/usage` resource-meter poll still logs every 10 s; it's marimo's, so no ticket. No review comments.

Related: [[unhydrated-notebook-banner]], [[quickstart-save-banner]].
