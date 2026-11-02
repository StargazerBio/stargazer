---
title: stored-builtin-slug-notebooks
status: maybe
priority: low
created: 2026-10-27
---

Create and Open from GitHub refuse a built-in notebook's name (ticket
[[workspace-slug-shadows-shipped]]), but a workspace notebook stored under one
before that, such as `assets.py`, keeps it. Its pod is still
`nb-<slug>-<mode>`, the same app as the built-in notebook's, so launching one
replaces the other. The user can download it, delete it and create it again
under another name; nothing renames it for them. Only worth doing if a real
workspace turns out to hold one.

Related: [[board]].
