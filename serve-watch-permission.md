---
title: serve-watch-permission
status: maybe
priority: low
created: 2026-11-01
---

The dashboard's serve watch fails straight away when it launches a notebook, because the project key is refused `ACTION_VIEW_FLYTE_EXECUTIONS`. [[launch-wait-route]] works around it: `_serve` falls back to polling `App.get`, and the tile waits on `/launch/status`. Granting the permission would let `serve.aio()` wait properly, but it's a Union permission change, and the fallback works without it, so this waits until the fallback causes trouble.
