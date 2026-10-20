---
title: Republish the stargazer image so the quickstart starts
status: doing
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
