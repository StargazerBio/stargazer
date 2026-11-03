---
title: community-explorer-listing
status: backlog
priority: high
created: 2026-11-03
---

The dashboard's explorer lists `StargazerBio/community-notebooks`, the
notebooks in its `catalog.yaml` first and the rest behind a filter, from a
cached copy of the repo's tree (GitHub's anonymous API allows 60 requests an
hour). Copying one into a workspace is Open from GitHub at its commit.

The scRNA pipeline tile moves with it: infra lists it as a built-in at its
in-image path, and that file is gone from the image from the first release
after v2026.10.30 (stargazer PR 124). This has to land before infra's
`stargazer-bio` pin moves to such a release, or the tile breaks.

The infra piece of ticket [[notebooks-in-git]], left from [[publish-to-git]].

Related: [[board]], [[notebooks-in-git]], [[publish-to-git]].
