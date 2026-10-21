---
title: Let CI push the stargazer image to ghcr
status: next
priority: high
created: 2026-10-21
---

The image workflow from ticket `publish-stargazer-image` builds, but its first run (`39662998285`, on the merge of #70) was refused at the push: `failed to push ghcr.io/stargazerbio/stargazer:latest: denied: permission_denied: write_package`. The package isn't linked to the repo (`"repository": null`), so `GITHUB_TOKEN` can't write it. So `:latest`, what the README and Getting Started `docker run`, is still the 2026-10-20 19:38 UTC build on Python 3.13, from before #63 and #68.

There's no API for the setting, so this one is the user's: package settings → **Manage Actions access** → add `StargazerBio/stargazer` with role **Write**.

- [ ] Grant the repo write access to the package
- [ ] Re-run it: `gh workflow run stargazer-image.yml`
- [ ] Verify: the run succeeds, `docker buildx imagetools inspect ghcr.io/stargazerbio/stargazer:latest` shows both platforms built that day on Python 3.14, and the README's `docker run` starts it from a clean cache
