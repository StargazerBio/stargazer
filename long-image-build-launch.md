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

- [x] `/launch` checks the image with `flyte.build(wait=False)`, answers 202 while it builds, serves in a background task
- [x] `/launch/status` reports building and failed launches; the tile shows the build and picks the pod up
- [x] Unit tests (`tests/unit/test_app.py`, real `ImageBuildEngine` and its caches over a fake builder)
- [x] Verified on Union (below)

Decisions (2026-10-26, implementation): `/launch` answers `{"building": <build run URL>}` with 202; `/launch/status` adds `building` and `failed` lists beside `running`, and a building notebook isn't reported running. A failed build is reported until the notebook is launched again. The tile links to the build run while it builds, polls `/launch/status` every 5 s, and gives Edit/Run back after 5 minutes with no build, pod or failure reported.

## Verification recipe: Launch while a notebook's image builds

A workspace notebook whose declared image isn't built yet launches without waiting: `/launch` answers at once, the tile shows the image building with a link to the build run, and when the build finishes the dashboard serves the notebook and the tile turns to Open and Stop by itself. Launching again once it's built serves straight away. Runs on the Union tenant as the test account, since only Union has the remote builder.

### Sub-features

- `build-202` answers `/launch` for an unbuilt image at once with 202 and the build run's URL.
- `build-tile` shows the build on the tile, and its link opens the build run.
- `build-pickup` serves the notebook after the build and flips the tile to Open and Stop with no second click.
- `build-again` answers a second launch during the build with the same build run and no new build.
- `built-serve` serves a launch of the built image straight away (200 with the notebook URL).

### How to get to it (user POV)

On the dashboard, a workspace notebook whose `main_env` declares an image layer not built before (gear → setup block), then Edit or Run.

### Driving it

Preconditions: as in ticket `notebook-environment`'s Union recipe (`.flyte/union.yaml` linked, `STARGAZER_TARGET=union`, infra's `tenant.env` exported for the deploy, the built-in browser signed in to the console as the test account).

- **Deploy.** `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy` from the branch's worktree; it prints the dashboard URL.
- **Notebook.** Create a workspace notebook from **Basic**, open its gear, and set `main_env`'s image to a layer no one has built, so the build is short and certainly new: `notebook_base.with_apt_packages("jq").with_env_vars({"SG_BUILD_PROBE": "<timestamp>"})`. Save.
- **Launch.** Click **Edit** on its tile. Pass: the tile shows **Building image** within a second or two (`build-202`, `build-tile`); its link opens a `build-image` run in the console. From the dashboard page, `fetch("/launch", …)` for the same slug and mode answers 202 with the same URL, and `union_dashboard.py check` shows one new `build-image` run, not two (`build-again`).
- **Pickup.** Wait without clicking. Pass: after the build succeeds the tile shows **Open: Edit Mode** and **Stop** on its own (`build-pickup`), and `check nb-<slug>-edit` shows the served image is `…:notebook-custom-<hash>`.
- **Built.** Click **Stop**, then **Edit** again. Pass: Open and Stop with no building state, `fetch("/launch", …)` answers 200 with the notebook URL, and no new `build-image` run (`built-serve`).
- **Teardown.** `union_dashboard.py teardown`: every app stopped, `live runs: []`.

### Evidence (2026-10-26, u-pryce, dashboard at 4017ff3)

Notebook `build-probe-1026`, image `notebook_base.with_apt_packages("jq").with_env_vars({"SG_BUILD_PROBE": "1793063198291"})`.

- `build-202`, `build-tile`: Edit click → `/launch` 202 in 3.3 s, `{"building": ".../runs/uwwmxx47v5rzxlclfjm8"}`; the tile showed **Building image**.
- `build-again`: a second `/launch` 6 s later → 202 in 0.27 s, same run URL; only one `build-image` run (`uwwmxx47v5rzxlclfjm8`).
- `build-pickup`: build succeeded by 01:07:57Z; `/launch/status` reported the notebook running at 01:08:07Z, and the tile showed **Open: Edit Mode** and **Stop** with no click. Served image `…:notebook-custom-5a07699571cd3d296fa2c36484b90d43`.
- `built-serve`: Stop, then Edit → `/launch` 200 in 3.0 s with the notebook URL, no building state, no new `build-image` run.
- Teardown: `union_dashboard.py teardown` stopped `nb-build-probe-1026-edit` and `dashboard`; `get app` shows all 28 apps STOPPED, live runs `[]`.

Not driven on Union: a failed build (covered by `test_a_failed_build_is_reported_through_status`).
