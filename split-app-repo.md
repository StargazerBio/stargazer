---
title: Move the dashboard and its deploy to infra
status: next
priority: low
created: 2026-10-27
---

Split this repo into the pod side and the pod manager side:

- **Stargazer** (this repo): the SDK and the notebook runtime, released
  together. A release is what runs in a pod.
- **Infra** (`StargazerBio/infra`): what manages pods and the clusters they
  run on. The dashboard, its deploy, onboarding, the AWS stacks and the
  devbox. One dashboard manages many pods across many users.

## Stargazer

- **The SDK package**: tasks, workflows, assets, storage and index,
  notebooks, with marimo as a dependency. Installed by infra and by anyone
  writing workflows in an IDE.
- **The runtime**, in a top-level `runtime/` folder: the proxy, the launch
  script, the save banner and the image recipe. It's image content, never
  part of the package. The proxy already runs in its own venv and imports
  neither the SDK nor `app`, so nobody installing the SDK gets FastAPI,
  websockets or jwt, or proxy code to import by mistake. It can't live
  under a folder named `app/`: Flyte's code bundle unpacks an `app/`
  package that would shadow it, which is why it's baked as `sg_proxy`.
- **One image** for Union, the devbox and local use, replacing the two
  hand-synced recipes (`notebook_app_img_recipe` and `Dockerfile`). Only
  the entrypoint and the env differ.

**Releases are calendar-versioned**: tag `v2026.11.27`, package version
`2026.11.27` (valid PEP 440; a second release that day is `2026.11.27.1`).
Each release publishes the package to PyPI (`stargazer-bio`, since
`stargazer` is taken) and the image to GHCR under the same tag.

## Infra

Infra pins one Stargazer release and gets both halves from it: the package
for the dashboard, the image for the pods it launches. So a dashboard and its
pods always agree on the index, the asset keyvalues and the pod contract.

The dashboard installs the package because it is the SDK's asset manager,
not only a notebook launcher:

- the asset browser and uploads (`app/assets.py`): the index
  (`make_index`), `StorageClient`, `PinataClient`, `CidBuilder`, and
  `build_asset`/`ASSET_REGISTRY` to validate keyvalues;
- the built-in notebooks (`app/notebooks.py`), listed from the installed
  `stargazer.notebooks` package;
- publishing notebooks (`Notebook`, the TUS chunk size);
- a notebook's `main_env`, evaluated against `notebook_image_base` and
  `notebook_environment`;
- constants from `stargazer.config`.

Its `PROJECT_ROOT` uses (its own image recipe, the `.flyte/` config path,
`release_version`) become infra's own root.

## The devbox

The devbox moves to infra whole: `devbox/setup.sh`, its Kubernetes YAML
(`postgres.yaml`, `coredns-custom.yaml`) and `devbox/dashboard.py`. It's a
cluster stand-in for Union, which is infra's side, and its dashboard deploy
needs the dashboard code anyway. Infra's AGENTS.md rule keeping the devbox
out goes.

Stargazer still runs tasks on it. Of `setup.sh`'s steps, the storage signed
URLs, the `PINATA_JWT` task secret and the index's Postgres serve task runs;
the serving domain and the CoreDNS wildcard serve apps (dashboards and
notebook pods). So the devbox test tier splits:

- **Stays in Stargazer**, assuming a devbox infra set up:
  `test_germline.py`, and `test_asset_storage.py` except the dashboard test.
  `pod_tasks.py` with them.
- **Moves to infra**: `test_dashboard.py` and
  `test_asset_storage.py::test_dashboard_lists_the_rows`.

Setting up a devbox then needs an infra checkout, including for someone
working only on Stargazer.

### Stargazer stops naming its clusters

`stargazer.config` knows two targets, `devbox` and `union`, and defaults to
`devbox` (measured 2026-10-28). So a package installed from PyPI starts with
the devbox's registry (`localhost:30000`) and its `--provenance=false` build
flag. The target does three things in the SDK, and each moves to whoever
sets up the cluster:

- **The push registry.** Flyte already reads one from the config file's
  `image.registry` (or `FLYTE_IMAGE_REGISTRY`) when an image is defined
  (`flyte._image._get_push_registry`), so infra's devbox setup writes it into
  the devbox's `.flyte/config.yaml`. Whether it reaches images that
  `config.py` defines at import, with `registry=None` passed explicitly, is
  unmeasured.
- **The build flag**, which only an arm64 devbox needs. `FLYTE_DOCKER_BUILD_EXTRA_ARGS`
  is Flyte's own variable, so infra sets it for the devbox.
- **The project key secret** declared on Union. That's a property of the
  backend, not a devbox detail, but it doesn't need the target's name: one
  variable naming the secret, set by infra on Union and forwarded into pods
  as `STARGAZER_TARGET` is today (inferred).

`STARGAZER_TARGET` then leaves the SDK, along with `tests/unit/test_deploy_target.py`'s
SDK half. The dashboard's own uses (which Flyte config to deploy with, the
sign-in issuer, the console link, the stand-in subject) go to infra with
`app/`, where naming clusters belongs. `gatk_env`'s 1Gi request, sized so
three pods fit the devbox node, is the one devbox tuning left in the SDK.

## The interface between them

What infra relies on from a Stargazer release, written down in one place:

- the image URI, its entrypoint and its `<mode> <path>` args;
- the env vars infra sets on a pod: `SG_OWNER_SUBJECT`, `SG_ADMIN_SUBJECTS`,
  `SG_AUTH_ISSUER`, `SG_SAVE_INTERVAL_SECONDS`, `STARGAZER_ADMIN_URL`,
  `STARGAZER_WORKSPACE_ROOT`, `STARGAZER_INDEX_URL`,
  `STARGAZER_STORE_ROOT`, `STARGAZER_NOTEBOOK_IMAGE`. Locally they're
  unset, which is why the proxy's sign-in gate and saving are off there;
- the workspace store layout, mirrored by hand between the proxy and the
  dashboard (`app/workspace_store.py`), since the proxy imports nothing;
- through the package: the asset keyvalues, the index table, storage.

## One image: what differs today (2026-10-28)

Measured from the two recipes; whether each matters is unmeasured.

- **Base and platform**: the hosted image is `flyte.Image.from_debian_base`,
  amd64 only, with Flyte's runtime; the `Dockerfile` is `python:3.14-slim`,
  multi-arch, with `flyte` installed in `/opt/venv`. Whether Union's app
  runner (`fserve`) runs on the `Dockerfile`'s base is untested.
- **Flyte config**: the local image writes a local-persistence config to
  `~/.flyte`, which in a Union pod could win over the in-cluster setup. It
  belongs in the local entrypoint.
- **`uv.lock`**: the hosted image copies it to `/stargazer` (Union's builder
  skips a uv project layer without one); the `Dockerfile` doesn't.
- **Workspace**: seeded from the image's notebooks locally, hydrated from
  the store on Union. That's the entrypoint's job.
- `main_env` layers already take the base as a URI
  (`notebook_image_base(config.NOTEBOOK_IMAGE)`), so a published image fits.

## Pros and cons

Measured 2026-10-28 unless marked.

| Area | For | Against |
|---|---|---|
| Change flow | Runtime-only and dashboard-only PRs (8 and 11 of the last 40 merged) stay in one repo each. | 17 of the last 40 touched the dashboard and the SDK or runtime. Each becomes a Stargazer PR, a release, and an infra PR that bumps the pin. Most crossed through storage and the index (DSQL #77/#78/#60, TUS uploads #72/#80, launch state #99) or the pod contract (settings #71, notebook environment #79). |
| Versioning | One pin in infra fixes both the dashboard's SDK and its pods' image. Every deploy names the release it ran. | A dashboard reports an infra commit plus a Stargazer release, not one commit. Releases are a step that doesn't exist yet. |
| Images | One image instead of two recipes kept in step by hand. Pods rebuild only when the pin moves, which fixes the per-release notebook image rebuilds raised 2026-10-14. | Published images reverse "images build from their recipe" for the pod image. |
| Infra | `app.deploy`, `app.init` and `app.config`, which infra imports from a sibling checkout today, become its own code. DSQL work spanning SDK, dashboard and infra touches two repos instead of three. | Testing infra against an unreleased Stargazer branch needs a path or branch source in place of the pin. |
| Stargazer | Self-contained: the SDK and the image a user runs. `pyproject.toml` loses `app*` and the `landing`/`app` extras. The package stops defaulting to the devbox. | — |
| Compatibility | — | Releases are public, so outside users can pin them. Before 1.0-style stability there's no compatibility promise, and AGENTS.md's "don't consider backwards compatibility" stands. |
| Devbox | The cluster, its setup and its dashboard live together in infra, beside the dashboard code they deploy. | Stargazer's devbox tests and anyone running tasks on a devbox need infra to set it up. `verify-stargazer` drives notebooks through the dashboard and would span both repos. |
| Tooling | Smaller context per repo (inferred). Infra already has its own AGENTS.md, skills and PR flow. | The docs split: `docs/architecture/app.md` and its companion move to infra or link across. |

## Pieces, if it goes ahead

- [ ] `runtime/` holds the proxy, launch script, save banner and the one
      image recipe; `per_notebook.py`'s deploy half goes to infra.
- [ ] One image for all three places; the differences above resolved.
- [ ] Release workflow: a calendar tag publishes the package to PyPI and the
      image to GHCR. Reopens tickets `pypi-release` and `sdk-package`'s
      SDK-only package piece.
- [ ] The interface above written down in Stargazer's docs.
- [ ] `STARGAZER_TARGET` leaves the SDK as above. It needs nothing else
      from the split, so it can ship first as its own PR.
- [ ] `app/` and `devbox/` move to infra, pinned to a release; the devbox
      test tier splits as above, and infra's devbox rule goes.

## Revisit when

The share of PRs crossing the seam drops well below 17 in 40, or releases
are wanted for their own sake. To rerun the count (runtime files count as
Stargazer):

```bash
RT='^(app/(proxy\.py|launch-notebook\.sh|terminal_overlay\.html|save_banner\.html|notebook_agent\.md)|Dockerfile)$'
git log origin/main --merges --first-parent -n 40 --format=%H | while read h; do f=$(git diff --name-only "$h^1" "$h"); s=$(echo "$f" | grep -cE "^src/|$RT"); a=$(echo "$f" | grep -E '^app/' | grep -cvE "$RT"); echo "$s $a"; done | awk '{if($1>0&&$2>0)b++; else if($1>0)s++; else if($2>0)a++} END{print "both",b,"stargazer only",s,"dashboard only",a}'
```

## History

- **2026-10-14**, from notebook image rebuilds: stay one repo, package only
  the SDK (ticket `sdk-package`).
- **2026-10-21**, as AWS admin calls crept into onboarding: onboarding and
  the AWS stacks moved to infra; `app/` stayed until it could pin a
  released SDK.
- **2026-10-27**: `sdk-package` shelved, since splitting all of `app/` off
  would need an installed-SDK path everywhere `app/` uses it.
- **2026-10-28**: this line. The dashboard builds no images from the SDK's
  source, so it can install a release; the runtime stays with the SDK.
