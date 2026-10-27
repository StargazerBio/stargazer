---
title: Launching a notebook whose image takes minutes to build
status: backlog
priority: low
created: 2026-10-22
---

A notebook that declares its own image in `main_env` is built on Union's
remote builder while `/launch` waits. One apt package builds in about a
minute, but a bioconda layer could take several, and nobody has measured
what happens when the build outlasts the dashboard's request timeout (and
Cloudflare's in front of it). Measure a long build's launch end to end. If
the request dies first, the launch should return while the build continues
and the tile should pick the notebook up when it's served, the way a
hydrated Open does.

## Measured (2026-10-26)

A probe app in `u-pryce` (`timeout-probe`, plain HTTP server that sleeps
`?s=N` seconds, no request timeout set, as the dashboard sets none) was hit
through its public URL, behind Cloudflare (`server: cloudflare`):

- 50 s, 110 s and 200 s requests answered 200. Cloudflare's usual 100 s
  cutoff doesn't apply here.
- A 330 s request answered 504 at 300.2 s. That's the platform's default app
  request timeout (inferred: Knative's 300 s default, since the app set
  none).

So a build that finishes inside about five minutes launches as it does now.
A longer one gets a 504. Flyte apps take `timeouts=flyte.app.Timeouts(request=...)`
up to an hour, but whether Cloudflare lets a request run past 300 s is not
measured.

Not measured: what the dashboard's `/launch` handler does after its request
is cut. Starlette doesn't cancel a handler when the client goes away, so the
build and serve likely carry on and `/launch/status` would pick the pod up
(inferred), which would make the fix only the tile's handling of a 504.
