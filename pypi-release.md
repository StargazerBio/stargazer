---
title: Publish the SDK to PyPI as stargazer-bio
status: next
priority: normal
created: 2026-05-20
---

Cut Stargazer's first release. The split (ticket `split-app-repo`) made the
package `stargazer-bio`, calendar-versioned, and added
`.github/workflows/release.yml`: a `v<version>` tag that matches
`pyproject.toml` publishes the package to PyPI by trusted publishing (GitHub
environment `pypi`) and the image to `ghcr.io/stargazerbio/stargazer:<tag>`
and `latest`. Infra pins a Stargazer commit's archive until then.

- [ ] PyPI: a pending trusted publisher for `stargazer-bio` (owner
      `StargazerBio`, repo `stargazer`, workflow `release.yml`, environment
      `pypi`). The user's PyPI account exists (2026-10-28).
- [x] GitHub: the `pypi` environment exists on the repo (measured 2026-10-28).
- [ ] Set `version` to the release day if it isn't `2026.10.28`, then tag
      `main` and push the tag; the workflow's run publishes both halves.
- [ ] Infra: pin `stargazer-bio==<version>` in place of the archive URL,
      `uv lock`, and redeploy the test account's dashboard on the release
      image (infra's `verify-dashboard` skill) before upgrading users.

Later: notebook headers could pin a release (`stargazer-bio == <version>`)
instead of `/stargazer`'s source, for reproducible community notebooks.
