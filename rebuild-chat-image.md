---
title: Rebuild the stargazer-chat image with the new gateway default
status: backlog
priority: normal
created: 2026-10-15
---

The README quickstart runs `ghcr.io/stargazerbio/stargazer-chat` and asks
for the `scrna_demo` bundle. That image bakes in the source, so it still
defaults `PINATA_GATEWAY` to `https://dweb.link`, which answers every request
with 429 (measured 2026-10-15 in ticket `default-ipfs-gateway`). Until the
image is rebuilt from `main` and pushed, the quickstart's bundle download
fails on a default config (inferred from the baked-in default; not run
against the image).

The image is pushed by hand: `docs/guides/contributing.md` has the multi-arch
`docker buildx` command. Verify by running the pushed image as the README
says and fetching the bundle.

Found while closing ticket `default-ipfs-gateway`.
