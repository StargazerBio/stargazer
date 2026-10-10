---
title: Local-to-cluster storage
status: backlog
priority: normal
created: 2026-10-07
---

A run submitted from this machine with the default local store and index has nowhere shared to write: those
defaults aren't forwarded into task pods (`_stargazer_env_vars` in
`config.py`), since a pod can't reach them. Today a remote run needs
`STARGAZER_STORE_ROOT` and `STARGAZER_INDEX_URL` exported to a store and
index pods can reach, as in the devbox recipe in
`docs/guides/contributing.md`. Inputs uploaded to the local store before
the switch point at paths no pod can read. On Union a local machine can't
write to the bucket, and `HttpIndex` sends no token to the dashboard's
public URL. [Plan 27](archive/27_asset_storage_index.md)'s open Q15 and Q21.
