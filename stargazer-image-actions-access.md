---
title: stargazer-image-actions-access
status: done
priority: high
created: 2026-10-21
---

The image workflow from ticket [[publish-stargazer-image]] builds, but its first run (`39662998285`, on the merge of #70) was refused at the push: `failed to push ghcr.io/stargazerbio/stargazer:latest: denied: permission_denied: write_package`. The package isn't linked to the repo (`"repository": null`), so `GITHUB_TOKEN` can't write it. So `:latest`, what the README and Getting Started `docker run`, is still the 2026-10-20 19:38 UTC build on Python 3.13, from before #63 and #68.

There's no API for the setting, so this one is the user's: package settings → **Manage Actions access** → add `StargazerBio/stargazer` with role **Write**.

- [x] Grant the repo write access to the package
- [x] Re-run it: the merge of #71 (`app/proxy.py`) ran it after the grant, so no by-hand run was needed
- [x] Verify: the run succeeds, `docker buildx imagetools inspect ghcr.io/stargazerbio/stargazer:latest` shows both platforms built that day on Python 3.14, and the README's `docker run` starts it from a clean cache

## Outcome

The user granted the repo write access to the package (`gh api /orgs/StargazerBio/packages/container/stargazer` → `"repository": "StargazerBio/stargazer"`). The next push that touched the image's files, the merge of #71, ran the workflow: run `39669931762`, success in 13m24s.

Verified 2026-10-22: `docker buildx imagetools inspect ghcr.io/stargazerbio/stargazer:latest` lists `linux/amd64` (built 2026-10-21 23:06 UTC) and `linux/arm64` (23:14 UTC), both `PYTHON_VERSION=3.14.8`. With the local copy removed, the README's `docker run` (on host port 18080) pulled it in 49 s and answered 200 about 10 s later, serving marimo on the Assets tutorial; `/workspace` holds `AGENTS.md` and `notebooks/` (templates, tutorials, workflows), as user `flyte`. Container removed afterwards.

Left: SDK and notebook changes don't trigger the workflow, so the image's SDK lags `main` until a by-hand `gh workflow run stargazer-image.yml` (by design, ticket [[publish-stargazer-image]]). Since #71 that's the DSQL index (#77) and the onboarding move (#76), neither of which the local image uses.
