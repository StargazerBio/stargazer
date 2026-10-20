---
title: The docker quickstart crashes on start and opens outside the workspace
status: doing
priority: high
created: 2026-10-20
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
