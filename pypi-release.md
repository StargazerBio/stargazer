---
title: pypi-release
status: done
priority: normal
created: 2026-05-20
pr: 5
---

Cut Stargazer's first release. The split (ticket [[split-app-repo]]) made the
package `stargazer-bio`, calendar-versioned, and added
`.github/workflows/release.yml`: a `v<version>` tag that matches
`pyproject.toml` publishes the package to PyPI by trusted publishing (GitHub
environment `pypi`) and the image to `ghcr.io/stargazerbio/stargazer:<tag>`
and `latest`. Infra pins a Stargazer commit's archive until then.

- [x] PyPI: a trusted publisher for `stargazer-bio` (owner `StargazerBio`,
      repo `stargazer`, workflow `release.yml`, environment `pypi`).
- [x] GitHub: the `pypi` environment exists on the repo (measured 2026-10-28).
- [x] Tag `v2026.10.28` on `main` (`e458f01`). Its Release run
      (actions run 40764559460) published `stargazer-bio 2026.10.28` to PyPI
      (wheel and sdist) and `ghcr.io/stargazerbio/stargazer:v2026.10.28` and
      `latest`, one index for amd64 and arm64 (measured).
- [x] Infra: `stargazer-bio==2026.10.28` pinned in StargazerBio/infra#5
      (`pr: 5` is infra's). The test account's dashboard, deployed from it,
      launched the Assets tutorial on the release image and ran its cells
      with no import errors; torn down after.

Later: notebook headers could pin a release (`stargazer-bio == <version>`)
instead of `/stargazer`'s source, for reproducible community notebooks.

## Outcome

Shipped: Stargazer `v2026.10.28`, the first release, on PyPI as
`stargazer-bio` and on GHCR as `ghcr.io/stargazerbio/stargazer:v2026.10.28`
and `latest`. Infra pins it (StargazerBio/infra#5, `1318008`). Verified by the
Release run's three jobs, the published files on both registries, and the test
account's dashboard on Union showing `2026.10.28-1318008` and running the
Assets tutorial on the release image. Left: notebook headers pinning a release
(above), and releases stay manual, a tag per release.
