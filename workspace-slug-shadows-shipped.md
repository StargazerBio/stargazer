---
title: A workspace notebook can share a shipped notebook's app name
status: doing
priority: normal
created: 2026-10-26
---

A notebook's pod is named `nb-<slug>-<mode>` whatever its section, and
`_notebook_slug` in `app/admin_app.py` reserves only the seed slugs. So a
workspace notebook named `assets`, `tasks`, `workflows`, `execution` or
`scrna-pipeline` (by Create, or by Open from GitHub, where a shipped
tutorial's file stem is exactly its slug) gets the same app names as the
shipped notebook. Launching one serves over the other's app, and the launch
status hydrates both tiles as running. Pick one: reserve the shipped slugs
too, or give workspace apps a distinct name.
