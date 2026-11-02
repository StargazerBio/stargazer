---
title: notebook-image-digest
status: backlog
priority: normal
created: 2026-11-02
blocked_by:
  - notebooks-in-git
---

A published notebook records the digest of the image it ran in, so anyone
can know the exact bytes it ran on. The file keeps `main_env` as the
author wrote it: the recipe says what the environment is and why, which a
digest can't. The digest goes in the publish commit as a trailer:

```
Add a TP53 variant QC notebook

Image: <repo>@sha256:<digest>
```

Code lives in git (ticket `notebooks-in-git`), so the commit is the
notebook's metadata: the recipe in the file, the digest beside it, a
message saying why, and every earlier version with its own. The digest is
the image's identity, the way a CID is a file's; whether its bytes are
public is a separate fact. A digest in a private registry is still a
byte-accurate, public commitment, and the image behind it can be made
public later. Copying an image between registries keeps its digest
(inferred; check with `crane copy`).

## Decided (2026-11-02)

- **A notebook runs from its own `main_env` by default.** Its image can be
  anything the author wants. A published notebook can also be launched on
  its recorded image (build or pull, below).
- **The digest goes beside the file, not in it.** Writing it into the file
  would lose the recipe, or tie the notebook's bytes to the image it runs
  in.
- **No asking authors to pin layers.** It won't stick.
- **The trailer is ordinary commit metadata.** Its author can change it
  with another commit; nothing guards it specially.

## Why Flyte's tag isn't enough

Read in Flyte 2.10.7 (`flyte/_image.py`, `_internal/imagebuild/remote_builder.py`),
not measured. An image's tag is an md5 of its *declaration* (the base
image's name and each layer's text; only `with_uv_project` hashes real
contents, the lock file), so unversioned packages rebuild to new bytes
under the same tag. The remote builder returns only `<registry>/<name>:<tag>`.
Every project pushes to one shared ECR repository where any user's pod can
overwrite a tag (ticket `shared-image-repository`).

## Shape

1. **Resolve, then launch on the digest.** When a launch's image is ready
   (built, or found), the dashboard resolves its tag to a digest (ECR
   `DescribeImages`, or the registry's manifest `Docker-Content-Digest`)
   and serves the pod on `flyte.Image.from_base("<repo>@sha256:<digest>")`.
   It already serves on `from_base(<uri>)` once a build finishes (ticket
   `launch-build-state`). This still runs `main_env`'s image, resolved, and
   makes the digest exactly what the pod runs, with no race against a tag
   moving between the lookup and the pull.
2. **Remember it** per notebook in the user's state table, beside the
   launch rows: the digest it last ran on.
3. **Stamp it at publish** as the commit's `Image:` trailer.
4. **Build or pull.** Opening a published notebook whose commit has an
   `Image:` trailer offers both: **build** from its `main_env`, as any
   launch does, or **pull** the recorded image. Pull is offered only where
   that digest can be pulled (the same deployment); elsewhere the launch
   builds and says why. A build whose resolved digest differs from the
   trailer's says so: the image differs from the one it was published
   with, so results may differ.

## Open questions

- A notebook published without ever being launched has no digest. Commit
  without the trailer and show that, or ask for a launch first?
- Edits made outside a pod (an upload over the workspace file) never ran
  in the recorded image.
- Making a digest public: a later "publish environment" step copies the
  image to a public registry, digest unchanged. Not in this ticket.
- Task images a notebook's runs use (`gatk_env`, `scrna_env`, its own
  `TaskEnvironment`s) have the same tag problem; recording their digests
  belongs to run provenance, a separate ticket if wanted.

## Pieces

- [ ] Experiment on the Union tenant, as the test account: the dashboard's
      role can `DescribeImages` on a Union-built tag and gets a digest; an
      `AppEnvironment` on `…@sha256:…` serves; `crane copy` to another
      registry keeps the digest.
- [ ] Infra: resolve and serve on the digest at launch; remember it; the
      `Image:` trailer at publish; build or pull when opening a published
      notebook.
- [ ] Docs: `docs/architecture/notebook.md` on what a published notebook
      records.
