---
title: The dashboard image carries the whole dev group
status: done
priority: low
created: 2026-10-27
---

Since PR #98 the task images (`gatk_env`, `scrna_env`) sync with `--no-dev`, which took about 200 MB and 33 packages out of each. The dashboard image (`app_env` in `app/admin_app.py`) still syncs without it, so it ships pytest, ruff, pre-commit and the docs tools. Pass `--no-dev` there too, check the dashboard still deploys and serves on the devbox, and measure the size difference.

## Outcome

Shipped with the split (StargazerBio/infra#4): the dashboard image now builds
from infra's own project with `extra_args="--no-dev"`. It deployed and served
on the devbox and on Union (ticket `split-app-repo`'s evidence). The size
difference wasn't measured.
