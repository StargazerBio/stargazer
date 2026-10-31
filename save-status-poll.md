---
title: save-status-poll
status: review
priority: low
created: 2026-10-31
pr: 116
---

A local `docker run` logs `GET /__sg__/save-status 200` about every 5 s. The save banner on every marimo page polled it every 10 s, and two open pages doubled that. Poll every 30 s instead. The workspace save interval (`SG_SAVE_INTERVAL_SECONDS`) is a separate setting and already defaults to 30 s.

## Verification recipe

Run the image with the branch's `runtime/save_banner.html` mounted over `/usr/local/lib/save_banner.html` on a spare port, open the notebook in a visible tab, and read `docker logs --timestamps` for about 90 s: `save-status` every 30 s, marimo's `/api/usage` every 10 s (proof the tab isn't throttled). Measured 2026-10-31: 16:49:44, 16:50:14, 16:50:44, 16:51:14, 16:51:44.
