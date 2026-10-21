---
title: Republish the stargazer image so the quickstart starts
status: done
priority: high
created: 2026-10-20
---

The README and Getting Started run `ghcr.io/stargazerbio/stargazer`. The
published `:latest` (built 2026-10-19) exits a second after it starts:
`FileNotFoundError: /usr/local/lib/save_banner.html` (measured 2026-10-20).
`main` has the fix since #56, but nothing publishes the image
automatically.

Rebuild both platforms from `main` and push, with the `docker buildx`
command in `docs/guides/contributing.md`, logged in to `ghcr.io` with a token
that has `write:packages`.

Verify by pulling the pushed image on a clean cache and running the README's
command: `http://localhost:8080` serves marimo's notebook list with
`notebooks/` in it. The amd64 build hasn't been run anywhere yet.

## Outcome

Pushed `ghcr.io/stargazerbio/stargazer:latest` on 2026-10-20, built from
`origin/main` at `2b96e0e` (the #56 merge) with the `contributing.md` buildx
command, unchanged, on Docker Desktop's default builder (containerd image
store, so it builds and pushes both platforms without a separate builder).

- Index: `sha256:c29589130f353ed1fedc66fc97e9353b09a06ec2b1963c501d685bed67e07764`
- linux/amd64: `sha256:f931b5e293e2455c993ff18a3fe967700359977baa210028fff9926aff1d717d`
- linux/arm64: `sha256:f89965990a76073a09c329caaba33f27f7d60271a6e2e9e13d0560d4ef6482be`

It replaces index `sha256:743c4d6e…` from 2026-10-19. The arm64 RUN layers
came from the local build cache, built from the same Dockerfile steps; every
COPY of `app/` and `src/` came from `main`. amd64 was built from scratch.

Verified (measured): ghcr serves the config and all 19 layers of both
platform manifests (HTTP 200 on each blob). With the local tag removed, each
platform was pulled and started with the README's command (host port 8081):
it stays up, `/` returns 200 with marimo 0.23.6 in `home` mode, and
`/api/home/workspace_files` lists `notebooks/` with its 7 files (templates,
tutorials, the scrna workflow), the same set as `main`. In both,
`/usr/local/lib/save_banner.html` is present and gatk 4.6.2.0, samtools 1.24,
bwa 0.7.19, bwa-mem2 2.2.1 and Claude Code 2.1.153 run. This was the first
run of the amd64 image anywhere (under emulation).

The package was `internal` at first, so an anonymous `docker run` got `401`
from ghcr. It was made public in its GitHub settings (there's no API for
it) on 2026-10-20. Then an anonymous token request and the `latest`
manifest request both returned 200, with digest `sha256:c2958913…`, and the
packages API reported `"visibility": "public"`. Nothing is left.
