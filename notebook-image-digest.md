---
title: notebook-image-digest
status: backlog
priority: normal
created: 2026-11-02
---

A published notebook records the digest of the exact image it ran in, so
anyone can know the bytes it ran on. The digest is the image's identity,
the way a CID is a file's. Whether its bytes are public is a separate fact:
a private digest is still a byte-accurate, public commitment, and the image
behind it can be made public later. Copying an image between registries
keeps its manifest, and so its digest (inferred; check with `crane copy`),
just as an asset keeps its CID when it's published.

**Decided (2026-11-02):** fetch the digest of the image the notebook ran
in. Not asking authors to pin layers: it won't stick. Not the SDK release
alone: a notebook's `main_env` layers its own tools on the release image.

## Why Flyte's tag isn't enough

Read in Flyte 2.10.7 (`flyte/_image.py`, `_internal/imagebuild/remote_builder.py`),
not measured:

- An image's tag is an md5 of its *declaration*: the base image's name and
  each layer's text (apt package names, command strings, pip requirement
  strings). Only `with_uv_project` hashes real contents (`uv.lock`,
  `pyproject.toml`). An unversioned apt or bioconda package rebuilds to new
  bytes under the same tag.
- The remote builder returns only `<registry>/<name>:<tag>`, no digest.
- Every project pushes to one ECR repository, and any user's pod can push
  to it (ticket `shared-image-repository`), so a tag can also be
  overwritten.

## Shape

1. **Resolve, then launch on the digest.** When a launch's image is ready,
   the dashboard resolves its tag to a digest (ECR `DescribeImages`, or the
   registry's manifest `Docker-Content-Digest`) and serves the pod on
   `flyte.Image.from_base("<repo>@sha256:<digest>")`. It already serves on
   `from_base(<uri>)` once a build finishes (ticket `launch-build-state`).
   Resolving first makes the digest the pod runs by construction, with no
   race against a tag moving between the lookup and the pull. A notebook
   with no declared image resolves the release image the same way.
2. **Remember it.** The digest a notebook last launched on goes in the
   user's state table, beside the launch rows (`image:<slug>` or on the
   launch row itself).
3. **Publish it.** Publishing a notebook stamps that digest on its
   `Notebook` record as `image`, the full `<repo>@sha256:<digest>`
   (about 140 characters, under the public tier's 250; the record goes
   from 5 keyvalues to 6 of 9). The `release` label is derivable from the
   base and isn't stored.
4. **Launch a published notebook on it** where the digest can be pulled
   (the same deployment). Where it can't, rebuild from `main_env` and say
   the image differs from the one it was published with.

## Open questions

- A notebook that was never launched (created, or opened from GitHub, and
  published straight away): publish with no `image`, or require a launch
  first? Leaning to publish without it and showing that it has none.
- Edits after the last launch: those edits ran in that pod, so the
  recorded digest stays true for them. Edits made outside a pod (an upload
  over the workspace file) would not have run in it.
- Making a digest public: a later "publish environment" step copies the
  image to a public registry with its digest unchanged. Not in this ticket.
- Task images a notebook's runs use (`gatk_env`, `scrna_env`, its own
  `TaskEnvironment`s) have the same tag problem. Recording their digests
  belongs to run provenance, a separate ticket if wanted.

## Pieces

- [ ] Experiment on the Union tenant, as the test account: the dashboard's
      role can `DescribeImages` on a Union-built tag and gets a digest; an
      `AppEnvironment` on `…@sha256:…` serves; `crane copy` of that image
      to another registry keeps the digest.
- [ ] Infra: resolve and serve on the digest at launch; store it per
      notebook; stamp it at publish; honour it at launch of a published
      notebook.
- [ ] This repo: `image` on `Notebook` (`src/stargazer/assets/notebook.py`),
      and `docs/architecture/notebook.md` on what a published notebook
      records.
