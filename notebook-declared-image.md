---
title: Notebook-declared pod image (main_img)
status: doing
priority: low
created: 2026-08-21
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
source, evaluates just that expression in a subprocess, submits the image to
Union's remote builder, and serves the notebook on the result. A notebook
without `main_img` launches exactly as today. Branch `feat/notebook-declared-image`.

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
- **Only the expression runs, in a subprocess.** The dashboard has `flyte`
  and `stargazer` but not each notebook's PEP 723 deps, so it can't run the
  whole setup block. The expression sees `flyte` and `notebook_base` only;
  it can't reference other setup-block names. The subprocess (with a timeout)
  keeps a hang or crash in user code from taking the dashboard down.
- **The image must derive from `notebook_base`.** The pod needs the proxy,
  launch script, marimo, uv and `/stargazer` from the notebook image. Checked
  after evaluation: the result's `base_image` must be the dashboard's
  `STARGAZER_NOTEBOOK_IMAGE`.
- **Builds go to Union's remote builder.** Measured in the SDK source
  (flyte 2.10.7): `flyte.build()` uploads the image spec (plus a context
  tarball for any copied-in files) and starts `system/build-image` as a run in
  the caller's project; the caller needs only Flyte API access, no Docker.
  `init_in_cluster` already defaults to `image_builder="remote"`, so the
  dashboard's init needs no change. An unchanged recipe is an existence
  lookup (`image_service.get_image`), not a rebuild.
- **Union only.** The devbox has no remote builder; a notebook that declares
  `main_img` there gets a clear error at launch.

## SDK facts the implementation leans on

- `Image.from_base(uri)` refuses extra layers until it's
  `.clone(name=..., extendable=True)`, so `notebook_base` is a named,
  extendable clone.
- The tag hashes `base_image` plus the layers, so the same expression on the
  same base resolves to the same image.
- The built image's real URI is the builder's fully qualified name (`fqin`,
  with the registry host), not `image.uri` (`name:tag`, no registry). Serve
  the URI `flyte.build()` returns.
- **Trap:** if every existence checker raises (remote builder missing, a
  transient API error), `ImageBuildEngine.image_exists` logs "assuming it
  exists" and returns the bare `name:tag`. Serving that is an
  `ImagePullBackOff`. Treat a returned URI without a registry host as a
  failure.
- `ImageBuildEngine.build` is `@alru_cache`d per process, so a long-lived
  process gets a stale `wait=False` result on a second call. A fresh
  subprocess per build sidesteps it.

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

- [ ] `stargazer.notebooks.notebook_base`: `flyte.Image.from_base(<base>)
      .clone(name=..., extendable=True)`, the base read from
      `STARGAZER_NOTEBOOK_IMAGE`, so the setup block runs in the kernel and
      `main_img` is a real `Image` there.
- [ ] `per_notebook_env` passes `STARGAZER_NOTEBOOK_IMAGE` into the pod env.
- [ ] Decide what `notebook_base` is when the env var is unset (a local
      `marimo edit`).

## Piece 2 — Evaluate `main_img` (`app/notebook_image.py`)

- [ ] `extract_main_img(source) -> str | None`: pure `ast`. Finds the
      `with app.setup:` block (marimo writes the setup cell there, not at
      module level) and returns the source of the `main_img = <expr>`
      right-hand side. Assignments inside cell functions are ignored. Never
      raises.
- [ ] Subprocess entry (`python -m app.notebook_image`): reads the
      expression and base URI, evaluates with `flyte` and `notebook_base` in
      scope, checks the base, initializes Flyte, `flyte.build(wait=True)`,
      prints a JSON result (URI or error).
- [ ] Tests: extraction cases (absent, present, inside cells ignored,
      unparseable source); evaluation cases that need no network (a wrong
      base and a raising expression both come back as errors).

## Piece 3 — Launch

- [ ] `per_notebook_env` takes the image URI to serve (default: the base).
- [ ] `/launch`: no `main_img` → today's path. Otherwise one background
      build per (base, expression), held in the dashboard process; while it
      runs `/launch` answers `building`; on success it serves the built URI;
      on failure it refuses with the error (no silent fallback: a pod missing
      the tools its notebook declares is worse than a clear error).
- [ ] Dashboard tile: "Building environment…" and re-POST `/launch` until it
      returns a URL or an error.

## Piece 4 — Docs

- [ ] `docs/architecture/notebook.md`: the boundary, in product terms. PEP
      723 deps → the kernel venv, installed at start with no rebuild.
      `main_img` → system level (apt, conda tools, binaries), changing it
      rebuilds.
- [ ] `docs/architecture/app.md` and
      `.opencode/reference/architecture/app_internals.md`: launch can build.
- [ ] Module docstrings (`app/per_notebook.py` says the image is shared and
      static).
- [ ] A guide example if a notebook guide exists; `zensical.toml` nav if any
      doc is added.

## Piece 5 — Verify on Union

- [ ] Deploy the test account's dashboard from the branch, create a
      notebook declaring `main_img`, launch it: building state, then the
      notebook opens and the declared tool runs in its terminal.
- [ ] Relaunch: no rebuild.
- [ ] Tear down per AGENTS.md.

## Deferred

- Snapshots, tutorials and workflows notebooks.
- Using `main_img` as the image for tasks defined in the notebook.
- Reporting in-flight builds through `/launch/status` across a dashboard
  reload (a reload loses the "building" tile; relaunching reattaches).
- `main_resources`, retiring the cpu/memory header fields.
