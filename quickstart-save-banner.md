---
title: The docker quickstart crashes on start and opens outside the workspace
status: done
priority: high
created: 2026-10-20
pr: 56
---

`docker run -p 8080:8080 -it ghcr.io/stargazerbio/stargazer`, the Getting
Started quickstart, exits with code 1 a second after it starts. The proxy
reads `save_banner.html` from its own directory at import, and the image
doesn't have it:

```
File "/usr/local/lib/sg_proxy.py", line 108, in <module>
    _SAVE_BANNER_INJECTION = (Path(__file__).parent / "save_banner.html").read_bytes()
FileNotFoundError: [Errno 2] No such file or directory: '/usr/local/lib/save_banner.html'
```

`d46d3a3` added the banner and baked it into the hosted notebook image
(`notebook_app_img_recipe` in `app/per_notebook.py`), but not into the
`Dockerfile`, which copies only `terminal_overlay.html` beside the proxy.
The published `:latest` (built 2026-10-19) has the new proxy without the file
(measured: the container's log above, reproduced with the published image).

With the banner in place the proxy got one line further and died on
`import jwt`: `1875752` added `pyjwt[crypto]` to the recipe's pip packages
for the token gate, and not to the `Dockerfile` (measured: built and ran it).

- [x] Copy `app/save_banner.html` to `/usr/local/lib/` in the `Dockerfile`
- [x] Install `pyjwt[crypto]>=2.8,<3` in the `Dockerfile`'s venv
- [x] `tests/unit/test_dockerfile.py`: the `Dockerfile` ships every file the proxy reads beside itself, and installs every pip package `notebook_app_img_recipe` pins. Each failed before its fix
- [x] Build the image and run the quickstart command against it: the notebook serves on 8080 with the banner spliced in
- [x] Don't advertise port 8081: marimo runs with `-q` (its banner named its own port, which only the proxy reaches) and the image prints `Stargazer notebook: http://localhost:8080`
- [x] Open the tutorial from `/workspace`: the image copies `assets.py` there unless one exists, so it shows in the Files sidebar and edits land in a mount. The Flyte config moves to `~/.flyte`, out of the sidebar and out from under a `/workspace` mount
- [x] Serve every SDK notebook: the tutorials and workflow notebooks are copied into `/workspace/{tutorials,workflows}/` (existing files kept) and marimo serves the directory, each notebook in a sandbox from its own header
- [x] The `blank` and `template` seeds land at the top of `/workspace`; Getting Started says to start notebooks from them
- [x] The SDK's seeds move to `notebooks/templates/` (`template.py` → `basic.py`, dashboard slug and option follow), and the image copies the whole `notebooks/` folder to `/workspace/notebooks/`
- [ ] Republish `ghcr.io/stargazerbio/stargazer:latest` (multi-arch, `docs/guides/contributing.md`)

## Verification

Measured 2026-10-20, arm64 build from the branch, tagged
`ghcr.io/stargazerbio/stargazer:latest` and run with
`docker run -d -it -p 8080:8080 ghcr.io/stargazerbio/stargazer`:
`GET /` served the Assets tutorial (200, `<title>assets</title>`) after the
sandbox venv built, with both `save_banner.html` and `terminal_overlay.html`
spliced into the page; `GET /__sg__/save-status` returned
`{"limit_bytes":104857600,"unsaved":[]}`; `import jwt` works in `/opt/venv`
(pyjwt 2.15.1); gatk, samtools, bwa and claude are on the `PATH`. The
amd64 build isn't run.

Second round, measured 2026-10-20 on the rebuilt image: the only URLs
printed are `Stargazer notebook: http://localhost:8080` and uvicorn's
`http://0.0.0.0:8080`; `/workspace` holds only `assets.py`, and marimo's
file API (`/api/files/list_files` through the proxy) returns root
`/workspace` with `assets.py`; `flyte get config` in `/workspace` reads
`/home/flyte/.flyte/config.yaml`. With a host directory mounted at
`/workspace`, the first start copied `assets.py` in beside the existing
file, and a line appended to it on the host survived a restart.

Third round, measured 2026-10-20: the server answers in ~4 s and marimo's
notebook list shows `tutorials/` and `workflows/`. In Chrome, Run all on
`tutorials/execution.py` ran with 0 errors (matplotlib imported, the local
run returned 3 `CohortSummary` results, local CIDs == remote CIDs, chart
cell rendered). Opening `workflows/scrna_pipeline.py` built its own
sandbox, which has scanpy and anndata; `execution.py`'s doesn't.

Fourth round, measured 2026-10-20: `/workspace` starts with `blank.py`,
`template.py`, `tutorials/` and `workflows/`. In Chrome, Run all on
`template.py` ran to its upload step with 0 errors and 0 warnings. A
notebook from marimo's "Create a new notebook" fails `import stargazer`
with `ModuleNotFoundError`, and marimo offers to install `stargazer` from
PyPI, which isn't this project.

Fifth round, measured 2026-10-20: `/workspace` starts with
`notebooks/{templates,tutorials,workflows}/` and nothing else; each
notebook serves by its new path. In Chrome, Run all on
`notebooks/templates/basic.py` rendered its first sections with 0 errors.
The dashboard's create flow is covered by the unit tests
(`test_create_from_basic_uses_the_basic_template`, reserved name `basic`),
not driven on a deployed dashboard.

## Outcome

Shipped in #56 (merged 2026-10-20, `2b96e0e`, the branch at `4b7bb01`). The
image starts: it ships `save_banner.html` and `pyjwt`, and
`tests/unit/test_dockerfile.py` fails when the `Dockerfile` misses a file
the proxy reads at startup or a pip package of the hosted recipe. marimo
runs with `-q` and the image prints `http://localhost:8080`. The Flyte
config is in `~/.flyte`. The SDK's notebooks folder is copied to
`/workspace/notebooks/` and marimo serves the directory, each notebook in a
sandbox from its own header. The create seeds moved to
`notebooks/templates/`, `template.py` renamed `basic.py`, and the dashboard
follows. Verified on local arm64 builds and in Chrome (rounds above).

Left:

- The published `:latest` still crashes on start until it's rebuilt and
  pushed (ticket `republish-stargazer-image`).
- `41c03a4`, staging the notebooks as `/opt/notebooks` without a wrapper
  folder, was committed after the branch was pushed and missed the merge. It
  is on `fix/notebooks-staging` (ticket `notebooks-staging`).
- The amd64 build wasn't run.
- marimo warns "Failed to add marimo to script metadata" on each notebook:
  the headers say `requires-python >=3.11`, stargazer needs 3.13.
- The README names opencode, which the image doesn't install.
- Ticket `top-level-notebooks` still plans moving the seeds to `app/` from
  `notebooks/workspace/`; left as is for now (2026-10-20).
