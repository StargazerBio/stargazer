---
title: Open a notebook from GitHub together with its folder
status: maybe
priority: low
created: 2026-10-26
---

Opening a notebook from GitHub (ticket `open-from-github`) brings in one file.
A notebook that imports modules or reads data files beside it won't run
without them. Bringing in its folder raises questions the one-file version
avoids: where the sibling files land in the workspace, since the dashboard
shows only top-level `.py` files as notebooks and a sibling `.py` would show
up as one; what happens when two imported folders have files with the same
name; and how big a folder is allowed to be. Wait until someone needs it.
