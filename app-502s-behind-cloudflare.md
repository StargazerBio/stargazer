---
title: Dashboard errors sent as 502 never reach the page
status: done
priority: normal
created: 2026-10-19
pr: 57
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

## Measured (2026-10-20, probe app `cf-status-probe` in `u-pryce`)

A FastAPI probe on the dashboard image answered `GET /status/<code>` with
that status and `{"error": "probe says <code>: the app's own message"}`,
fetched through its public URL with the admin's bearer token:

| Status | What arrived |
|---|---|
| 500 | the app's JSON, untouched (`content-type: application/json`, `content-length: 49`, `x-envoy-upstream-service-time` present) |
| 502 | Cloudflare's HTML "unionai.cloud \| 502: Bad gateway" page (6641 bytes, `retry-after: 60`) |
| 503 | the app's JSON, untouched |
| 504 | Cloudflare's HTML "504: Gateway time-out" page (`retry-after: 120`) |

A plain-text 500 and an unhandled exception's "Internal Server Error" also
passed through. So 500 it is.

## Routes affected

All in `app/admin_app.py`, each a 502 with an `error` message: create, copy,
settings update, delete, stop and cleanup failures.

## Fix

Send these as a status Cloudflare passes through. 500 is the natural one
for "the store or control plane failed", but whether Cloudflare passes a 500's
body through is unmeasured: check it on the tenant first, and fall back to
503 if it doesn't. `/launch`'s refused deploy already went to 422 (ticket
`long-notebook-names`).

## Verification (2026-10-20, PR #57)

Deployed the branch (`c0e3f25`) to the test account's dashboard with
`stargazer-users onboard --email pryce@stargazer.bio`. `POST /stop` for a
notebook with no app, through the public URL, answered `500` with
`{"error":"stop failed: entry not found"}`, both with the admin's bearer
token and from the test account's browser session. The probe app and the
dashboard were deactivated afterwards.

## Outcome

PR #57 (`c0e3f25`, merged 2026-10-20). The dashboard's own failures on
create, copy, settings update, delete, stop and cleanup answer 500, whose
body Cloudflare passes through (measured with `cf-status-probe` above). On
the test account's dashboard, `POST /stop` for a notebook with no app
answered 500 with `{"error":"stop failed: entry not found"}` through the
public URL. Nothing left.
