---
title: Launching a notebook whose image takes minutes to build
status: doing
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

## Approach: wait only when the image is already built

Read from the Flyte SDK (2.10.7) on 2026-10-26. `flyte.build.aio(image,
wait=False)` asks the image service whether the image exists
(`ImageBuildEngine.image_exists`, one `GetImage` call) and returns
`ImageBuild(uri=..., remote_run=None)` when it does. When it doesn't, it
submits the remote build and returns at once with `remote_run` set to the
build run. `serve` builds through the same `build` call, waiting.

So `/launch`, for a notebook that declares an image:

- `flyte.build.aio(image, wait=False)` first. `remote_run is None` means the
  image is built: serve and answer as now.
- Otherwise answer 202 with the build run's URL, and a background task on
  the dashboard waits for that run, then serves the pod. The tile shows the
  build as in progress, and `/launch/status` picks the pod up once it's
  served, as it does for a hydrated Open. A failed build is kept per
  notebook and mode and reported through `/launch/status`, as the 422 is
  now.
- A second `/launch` during the build answers 202 again and doesn't start
  another build.

The catch: `ImageBuildEngine.image_exists` and `ImageBuildEngine.build` are
cached per process with `async_lru`, which caches a `None` too (checked).
After an early return, the dashboard has "not built" cached for that image,
so the background task's serve, and every later launch, would submit
another build. The task has to drop that image's entries
(`ImageBuildEngine.image_exists.cache_invalidate(image)` and the `build`
entry) once the build succeeds, which reaches into `flyte._internal`. A
dashboard restart mid-build loses the background task. The build still
finishes, so the next launch serves straight away.
