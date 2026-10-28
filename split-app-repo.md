---
title: Move the dashboard and its deploy to infra
status: maybe
priority: low
created: 2026-10-27
---

Split this repo along the line between what a user runs and what operates
the platform. Stargazer keeps the SDK, the notebooks and the notebook runtime
(the proxy, the launch script, marimo, the notebook image). That's the
`docker run stargazer` image, a whole product on its own. The dashboard and
the code that deploys it move to `StargazerBio/infra`, beside onboarding and
the AWS stacks.

A split has come up four times, each from a different pain:

- **2026-10-14**, from notebook image rebuilds on every release: stay one
  repo and package only the SDK (ticket `sdk-package`). The import-layer rule
  already gives most of what a boundary would.
- **2026-10-21**, "getting out of hand for one repo", as AWS admin calls
  crept into onboarding: onboarding and the AWS stacks moved to infra, and
  `app/` stayed. The note then: once the app can pin a released SDK, the app
  and infra could share a repo as the deploy side.
- **2026-10-27**, while scoping `sdk-package`: shelved, because the SDK runs
  from source everywhere and splitting all of `app/` off would make an
  installed-SDK path mandatory in every place `app/` uses it.
- **2026-10-28**: the line above, which avoids most of that (below).

## What `app/` uses the SDK for

`app/` is three things:

- **The notebook runtime:** the proxy, the launch script, the overlays, the
  agent's `AGENTS.md`. None of it imports the SDK: the proxy needs only
  `flyte`, FastAPI and friends. It ships in two images carrying the SDK
  source at `/stargazer` for the notebooks' sandbox venvs: the hosted
  `notebook-app` image (`notebook_app_img_recipe`) and the `docker run`
  `stargazer` image (`Dockerfile`). Neither has the dashboard. On the local
  image the proxy does little: with no sign-in issuer and no store, its
  gate and its saving are off.
- **The deployer** (`app/deploy.py`, the deploy half of
  `app/per_notebook.py`): builds the notebook image from the SDK's source
  through `PROJECT_ROOT`, and deploys the dashboard from Flyte's code bundle.
- **The dashboard**, in its own image. It uses the SDK for real:
  - the asset browser and uploads (`app/assets.py`): the index
    (`make_index`), `StorageClient`, `PinataClient`, `CidBuilder`, and
    `build_asset`/`ASSET_REGISTRY` to validate keyvalues;
  - the shipped notebooks (`app/notebooks.py`), read from the installed
    `stargazer.notebooks` package;
  - publishing notebooks (`Notebook`, the TUS chunk size);
  - a notebook's `main_env`, evaluated against `notebook_image_base`;
  - constants from `stargazer.config`.

So the dashboard is the SDK's asset manager as much as a launcher, and
depends on it either way.

**Why this line avoids `sdk-package`'s problem.** That ticket stalled on task
images, which build from the SDK's `pyproject.toml` through `PROJECT_ROOT`.
The dashboard never builds or runs a task. Its `PROJECT_ROOT` uses are its
own image recipe, the `.flyte/` config path and `release_version`, all of
which become infra's own root. So the dashboard can install the SDK from a
git tag (`stargazer @ git+https://github.com/StargazerBio/stargazer@vX`),
no wheel or PyPI needed. The notebook image keeps building from the SDK's
source, in the SDK repo.

## Pros and cons

Measured 2026-10-28 unless marked.

| Area | For | Against |
|---|---|---|
| Change flow | Runtime-only and dashboard-only PRs (8 and 11 of the last 40 merged) stay in one repo each. | 17 of the last 40 touched the dashboard and the SDK or runtime. Each becomes an SDK PR, a tag, and an infra PR that bumps the pin. Most crossed through the storage and index layer (DSQL #77/#78/#60, TUS uploads #72/#80, launch state #99) or the pod contract (settings #71, notebook environment #79). |
| How the dashboard gets the SDK | A git-tag pin works: no task images, no wheel-without-source path. | The tag is a release step that doesn't exist today. |
| Infra | Infra imports `app.deploy`, `app.init` and `app.config` from a sibling checkout today; those become its own code, and the sibling dependency becomes a tag pin. The storage and index work that spans the SDK, the dashboard and infra (DSQL) touches two repos instead of three. | Infra's cross-repo costs carry over: testing against an SDK branch (`PYTHONPATH` or a branch pin), merge order between repos. |
| The SDK repo | Self-contained: the SDK, notebooks and the image a user runs. `pyproject.toml` loses `app*` and the `landing`/`app` extras. | — |
| Notebook image | Could collapse the hand-synced `Dockerfile` and `notebook_app_img_recipe` into one image per SDK tag, which the dashboard pins. That also fixes the 2026-10-14 rebuilds. | Publishing it per tag reverses "images build from their recipe" (decided 2026-10-27 for task images). The alternative, infra building it from an SDK checkout, keeps the sibling dependency. |
| Pod contract | — | Becomes cross-repo API: the dashboard-to-pod env vars (`SG_OWNER_SUBJECT`, `SG_ADMIN_SUBJECTS`, `SG_AUTH_ISSUER`, `SG_SAVE_INTERVAL_SECONDS`, `STARGAZER_ADMIN_URL`, `STARGAZER_WORKSPACE_ROOT`, `STARGAZER_INDEX_URL`, `STARGAZER_STORE_ROOT`, `STARGAZER_NOTEBOOK_IMAGE`), the workspace store layout (`app/workspace_store.py`, mirrored in the proxy), the launch script's `<mode> <path>` args. It's already mirrored by hand, since the proxy can't import `app`. |
| Compatibility | — | A dashboard pinned to SDK N launching an image from SDK M needs those contracts to match. Pinning both to one tag avoids it; anything else means compatibility windows, against "don't consider backwards compatibility" before 1.0. |
| Versioning | — | A dashboard reports one commit (`STARGAZER_VERSION`); split, it's an infra commit plus an SDK tag. |
| Devbox | — | `devbox/dashboard.py` deploys the dashboard, and infra's rules keep the devbox out. Either that rule changes or the devbox loses its dashboard. The devbox tier and `verify-stargazer` drive notebooks through the dashboard and would span both repos. |
| Tooling | Smaller context per repo (inferred). Infra already has its own AGENTS.md, skills and PR flow, so little doubles. | The docs site splits: `docs/architecture/app.md` and its companion move or link across. |
| Visibility | Infra's visibility is its own choice; the SDK repo stays public. A public SDK with a separate platform is the classic reason to split. | No current plan to treat them differently. |

## Before it could happen

- SDK releases as git tags (proposed 2026-10-27; none exist yet).
- A decision on the notebook image: published per tag, or built by infra
  from an SDK checkout.
- A decision on the devbox's dashboard.
- `per_notebook.py` split into the image recipe (SDK side) and the app
  deploy (infra side).

## When to revisit

- The platform should be operated or seen separately from the SDK.
- The share of PRs crossing the seam drops well below 17 in 40. To rerun
  (runtime files count as SDK side):

```bash
RT='^(app/(proxy\.py|launch-notebook\.sh|terminal_overlay\.html|save_banner\.html|notebook_agent\.md)|Dockerfile)$'
git log origin/main --merges --first-parent -n 40 --format=%H | while read h; do f=$(git diff --name-only "$h^1" "$h"); s=$(echo "$f" | grep -cE "^src/|$RT"); a=$(echo "$f" | grep -E '^app/' | grep -cvE "$RT"); echo "$s $a"; done | awk '{if($1>0&&$2>0)b++; else if($1>0)s++; else if($2>0)a++} END{print "both",b,"sdk+runtime only",s,"dashboard only",a}'
```
