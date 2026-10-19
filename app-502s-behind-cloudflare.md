---
title: Dashboard errors sent as 502 never reach the page
status: backlog
priority: normal
created: 2026-10-19
blocked_by:
  - long-notebook-names
---

Cloudflare sits in front of every Union app and replaces the body of a 502
from the app with its own "Error 502: Bad gateway" JSON. The dashboard sends
its own failures as 502 with an `error` message, so on Union the page shows
Cloudflare's text instead of what went wrong.

## Measured (2026-10-19, test account's dashboard)

- `POST /stop` for a notebook with no app (the handler answers 502 "stop
  failed: …") reached the browser as Cloudflare's body:
  `"error_name":"origin_bad_gateway"`, `"cloudflare_error":true`.
- The same happened to `/launch` while it briefly answered 502. A 503 and
  4xx bodies from the same dashboard passed through untouched.

## Routes affected

All in `app/admin_app.py`, each a 502 with an `error` message: create, copy,
settings update, delete, stop and cleanup failures.

## Fix

Send these as a status Cloudflare passes through. 500 is the natural one
for "the store or control plane failed", but whether Cloudflare passes a 500's
body through is unmeasured: check it on the tenant first, and fall back to
503 if it doesn't. `/launch`'s refused deploy already went to 422 (ticket
`long-notebook-names`).
