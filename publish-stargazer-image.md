---
title: publish-stargazer-image
status: done
priority: normal
created: 2026-10-21
pr: 70
---

`ghcr.io/stargazerbio/stargazer:latest` is what the README and Getting Started `docker run`, and nothing publishes it: it's pushed by hand (ticket `republish-stargazer-image`). So it lags `main` after every change to the image. Measured 2026-10-21: both platforms were built 2026-10-20 ~19:37 UTC on Python 3.13.16, before #65 moved the `Dockerfile` to 3.14. #63 (the Assets landing page, `/workspace/AGENTS.md`, Claude Code 2.1.304) widens the gap once it merges.

Don't rebuild on every merge. A GitHub Actions workflow on pushes to `main`, filtered by `paths:`, builds both platforms and pushes `:latest` only when the image's own files change, plus `workflow_dispatch` to republish by hand (for example, to pick up SDK or notebook changes, which the filter leaves out).

```yaml
on:
  push:
    branches: [main]
    paths:
      - Dockerfile
      - app/proxy.py
      - app/terminal_overlay.html
      - app/save_banner.html
      - app/launch-notebook.sh
      - app/notebook_agent.md
      - .github/workflows/stargazer-image.yml
  workflow_dispatch:
permissions:
  contents: read
  packages: write
concurrency:
  group: stargazer-image
  cancel-in-progress: true
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ghcr.io/stargazerbio/stargazer:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

## Open questions

- **Scope:** only the `Dockerfile` image, or also the Flyte images (`stargazer-gatk`, `stargazer-scrna`, the hosted `notebook-app`, the dashboard)? Those aren't pushed by hand today. Flyte builds them by content hash when a run, `onboard` or `upgrade` needs one, on Union's remote builder and into Union's registry. Building them in Actions would need a Union API key as a repo secret, and pre-building only saves the first run's build time.
- **Cost:** asked, not yet answered. Inferred, not checked against GitHub's current pricing: standard GitHub-hosted runners are free for public repos (this one is public), and ghcr storage and bandwidth are free for public packages. The real limits are time and disk. arm64 under QEMU on an amd64 runner is slow for the micromamba bioconda layer. A native `ubuntu-24.04-arm` runner per platform plus a manifest merge avoids emulation, but it's more workflow.

## Pieces

- [ ] Grant the repo write access to the package: package settings → Manage Actions access → `StargazerBio/stargazer`, role Write. Without it, `GITHUB_TOKEN` gets 403 on push. The packages API shows the package isn't linked to a repo (`"repository": null`), and there's no API for this setting.
- [x] `.github/workflows/stargazer-image.yml`, linted (`actionlint`)
- [x] `docs/guides/contributing.md` → Building Images and `docs/architecture/configuration.md` → Container Images: CI publishes it, and how to run it by hand. Both currently say nothing publishes it automatically.
- [ ] Verify: the merge of this PR touches the workflow file, so it triggers the first run. Check that the run succeeds, that `docker buildx imagetools inspect ghcr.io/stargazerbio/stargazer:latest` shows both platforms with today's build date on Python 3.14, and that the README's `docker run` starts it from a clean cache.

## Outcome

Shipped in PR #70 (merge `717dabe`): `.github/workflows/stargazer-image.yml` builds both platforms on pushes to `main` that touch the image's files, and on `workflow_dispatch`; the docs say so. Linted with `actionlint`.

The first run, on the merge (run `39662998285`), built both platforms in 11m38s and failed at the push: `denied: permission_denied: write_package`. The package's Actions access was never granted (`gh api /orgs/StargazerBio/packages/container/stargazer` still reads `"repository": null`), and `:latest` is still the 2026-10-20 19:38 UTC build. That grant, the re-run and the image check are ticket `stargazer-image-actions-access`. No comments on the PR.
