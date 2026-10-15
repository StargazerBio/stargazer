---
title: Notebook-declared pod image (main_img)
status: review
priority: low
created: 2026-08-21
pr: 28
---

A workspace notebook declares the image its own pod runs on, as a real
`flyte.Image` expression in its setup block:

```python
with app.setup:
    from stargazer.notebooks import notebook_base

    main_img = notebook_base.with_apt_packages("bcftools").with_commands(
        ["micromamba install -y -p /opt/conda -c bioconda vcftools"]
    )
```

At `/launch` the dashboard pulls the `main_img = ...` statement out of the
source, evaluates just that expression, and makes the result the notebook
AppEnvironment's image; the SDK's `serve` builds it on Union's remote builder
(or finds it built) before deploying. A notebook without `main_img` launches
exactly as before. Branch `feat/notebook-declared-image`.

**Why.** The notebook's environment is the user's to shape, and the SDK
already has a whole API for it. Real Python keeps that API (every `Image`
method that doesn't read local files), keeps layer order in the user's hands,
and keeps the notebook-to-production path a copy and paste into a
`TaskEnvironment`. The definition travels with the notebook through copy,
download and snapshot.

## Design decisions (2026-10-14)

- **Evaluate, don't parse.** The August plan read `main_img` statically
  (whitelisted methods, literal arguments) because the admin pod then held
  `SESSION_SECRET` and the GitHub App key. Both are gone: dashboards are
  per-user and hold no secrets, so running the owner's expression in the
  owner's dashboard is the same trust as their notebook pod. A static form is
  configuration dressed as Python; if it were static, the settings modal would
  be the honest surface. Rejected alternatives: a settings-modal/header form
  (loses the SDK idiom and most of the API), and evaluating in the notebook
  kernel then recording the built URI in the header (a relaunch dance plus a
  stored URI that can drift from the definition).
- **Only the expression runs.** The dashboard has `flyte` and `stargazer` but
  not each notebook's PEP 723 deps, so it can't run the whole setup block. The
  expression sees `flyte` and `notebook_base` only.
- **The image must derive from `notebook_base`.** The pod needs the proxy,
  launch script, marimo, uv and `/stargazer` from the notebook image. Checked
  after evaluation: the result's `base_image` must be the deployed notebook
  image.
- **Let `serve` build (simplified 2026-10-14).** The first cut evaluated and
  built in a subprocess with `flyte.build`, guarded the returned URI, kept a
  thread-pool registry of in-flight builds, and had `/launch` answer 202
  `building` while the tile polled. All of that reimplemented what `serve`
  already does (`build_images`: existence check, remote build, the builder's
  real URI). Now the evaluation runs in-process and `/launch` blocks on
  `serve`; the tile just spins. Given up: the "Building environment…" label,
  and dedup of a build that a reload relaunches mid-flight.
- **Union only.** The devbox has no remote builder (the SDK would assume the
  image exists and deploy a bare `name:tag`), so a declared image there is a
  clear error at launch.

## SDK facts the implementation leans on

- `Image.from_base(uri)` refuses extra layers until it's
  `.clone(name=..., extendable=True)`, so `notebook_base` is a named,
  extendable clone.
- The tag hashes `base_image` plus the layers, so the same expression on the
  same base resolves to the same image.
- `init_in_cluster` already defaults to `image_builder="remote"`, so the
  dashboard's init needs no change.
- `ImageBuildError` subclasses `RuntimeError`, so `/launch` catches it before
  its serve-watch recovery, which would otherwise reopen the old pod.

## Piece 0 — Verify a pod can build

- [x] From a task pod on Union (same org key as app pods), `flyte.build()` a
      clone of the current notebook image with one apt package; confirm it
      returns a registry-qualified URI.
- [x] Build it again; confirm the second call is an existence hit, not a
      rebuild.
- [x] Run a task on the built URI; confirm nodes pull it and the package is
      on PATH.
- [x] Tear down per AGENTS.md.

Measured 2026-10-14 in `u-pryce`. Run `ulgqkhjcs8422ffhs7vk` spawned two
fresh child processes, each `flyte.init_in_cluster()` then `flyte.build()` of
`from_base(<notebook-app-a2a77154…>).clone(name="nb-image-probe",
extendable=True).with_apt_packages("bcftools")`. The first built in 65.7 s
(build run `u8lszpczr275rgbj4lpl`, in `u-pryce`) and returned
`791359099513.dkr.ecr.us-west-2.amazonaws.com/union/stargazerbio:nb-image-probe-b78be645…`;
the second was an existence hit in 0.5 s with the same URI and no run.
`image.uri` was `nb-image-probe:b78be645…`, so the served URI must be the
build result. Run `udzpwpqlkrf24676ggbz`'s pod pulled the built image (a probe
bug failed it after start); the rerun on it printed `/usr/bin/bcftools`,
`bcftools 1.16`. Afterwards every app in `u-pryce` was stopped and no runs
were live.

## Piece 1 — `notebook_base` in the kernel

- [x] `stargazer.notebooks.notebook_base` (and `notebook_image_base(uri)`):
      the deployed image from `STARGAZER_NOTEBOOK_IMAGE` as a named,
      extendable clone.
- [x] `per_notebook_env` passes `STARGAZER_NOTEBOOK_IMAGE` into the pod env,
      always the deployed image.
- [x] Unset (a local `marimo edit`): a `notebook-app:local` placeholder.

## Piece 2 — Find and evaluate `main_img` (`app/notebook_image.py`)

- [x] `extract_main_img`: pure `ast`, inside the `with app.setup:` block
      only; cells ignored; never raises.
- [x] `evaluate_main_img`: in-process `eval` with `flyte` and
      `notebook_base`; `MainImgError` for a raising expression, a non-image,
      a foreign base, or a non-Union target.

## Piece 3 — Launch

- [x] `per_notebook_env(image=...)` takes the declared `flyte.Image`.
- [x] `/launch` evaluates, serves (which builds), and answers 422 for a
      `MainImgError` or an `ImageBuildError`. Workspace notebooks and own
      snapshots; shipped notebooks run on the deployed image.

## Piece 4 — Docs

- [x] `docs/architecture/notebook.md` (Notebook Environment: PEP 723 deps vs
      `main_img`), `docs/architecture/app.md`,
      `.opencode/reference/architecture/app_internals.md`, module docstrings.
      No new doc files.
- [x] The workspace template declares `main_img` (bcftools) with a section
      0 showing where it resolves: the pattern for users, and the notebook
      the Union recipe launches (no seeding script).
- [x] verify-stargazer feature `union-main-img` with
      `scripts/union_dashboard.py` (deploy, check, teardown of the test
      account's dashboard only).

## Piece 5 — Verify on Union

- [x] First design (`ebe1041`): the tile showed "Building environment…",
      build run `utrpzxkpgbd8vl9vvqct` (9.2 s), served on
      `…:notebook-custom-d5b18fe1…`, the cell found `/usr/bin/tabix`
      (htslib 1.16); stop and relaunch started no build.
- [x] Simplified (`9da05dc`): `/launch` for a notebook declaring `jq` took
      63.4 s end to end with no timeout (build run `uv6vw2jtlqnd5k98w256`,
      then the deploy), served on `…:notebook-custom-3a9899a3…`; the page
      read `PROBE-TOOL: /usr/bin/jq jq-1.6`, `PROBE-BASE:
      …:notebook-app-167c1aea…` (the deployed image), `PROBE-MAIN: Image`.
      Stop and Run from the tile started no build and served the same image.
- [x] Template (`83d4538`): created "image check" from the Template on the
      dashboard and ran it; build run `ugcdns9t7b5x2pv5hcdm`, served on
      `…:notebook-custom-603bea0c…`, section 0 read `bcftools →
      /usr/bin/bcftools`. Stop and Run started no build.
- [x] Torn down: every app in `u-pryce` stopped, no live runs in `u-pryce`
      or `flytesnacks`. The test dashboard runs `83d4538` and is stopped. The
      test account's workspace keeps "main_img probe" and "image check".

## Deferred

- Snapshots' image pinning (they rebuild on the current base), tutorials and
  workflows notebooks.
- Using `main_img` as the image for tasks defined in the notebook.
- A long build (bioconda) against the dashboard's request timeout is
  unmeasured. If one outlasts it, bring back a building state and polling.
- `main_resources`, retiring the cpu/memory header fields.
- A declared image rebuilds once per release, because the notebook image
  bakes `src/` and `app/` and gets a new hash whenever they change. The
  rebuild is per distinct declaration for the whole org, not per notebook or
  user: the existence lookup is org-wide (measured 2026-10-14, the
  template's `notebook-custom-603bea0c…` built in `u-pryce` was found from
  `flytesnacks`, runs `ubq794kxgkggfh7bsqfx` and `ucmqrmsdwdnxcgsmb5d4`).
  Builds measured 9.0 to 42.9 s. Baking less of `app/` would stop
  dashboard-only releases from changing the base; separate ticket if wanted.
