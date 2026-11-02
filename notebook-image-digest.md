---
title: notebook-image-digest
status: backlog
priority: normal
created: 2026-11-02
---

A published notebook records the digest of the image it ran in, on its
`Notebook` record, beside the recipe that built it. The file keeps
`main_env` as the author wrote it: the recipe says what the environment is
and why (which tools, layered on what), which a digest alone can't. The
record's `image` says exactly which bytes that recipe produced when the
notebook ran. The digest is the image's identity, the way a CID is a
file's; whether its bytes are public is a separate fact. A digest in a
private registry is still a byte-accurate, public commitment, and the image
behind it can be made public later. Copying an image between registries
keeps its digest (inferred; check with `crane copy`).

## Decided (2026-11-02)

- **A notebook always runs from its own `main_env`.** Its image can be
  anything the author wants: a recipe, or a digest if they like.
- **The digest goes in the record, not the file.** The recipe stays
  readable in the file, and the record carries what it built. Metadata
  isn't part of the notebook's bytes, so there's no loop: stamping a digest
  never changes the notebook's CID, even for a notebook baked into the
  image it names (the built-in notebooks).
- **No asking authors to pin layers.** It won't stick.

## Why the recipe's tag isn't enough

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
   it makes the digest exactly what the pod runs, with no race against a
   tag moving between the lookup and the pull.
2. **Remember it** per notebook in the user's state table, beside the
   launch rows: the digest it last ran on.
3. **Stamp it at publish.** The `Notebook` record gains `image`, the full
   `<repo>@sha256:<digest>` (about 140 characters, under the public tier's
   250), and `image_tag`, the recipe's Flyte tag, which ties the digest to
   the recipe that built it. The record goes from 5 keyvalues to 7 of 9.
4. **Compare on launch.** Someone launching a published notebook runs its
   `main_env` as always. When the digest their launch resolves differs from
   the record's `image`, say so: same recipe, different image, so results
   may differ. When the record's digest can be pulled (the same
   deployment), offer to run on it.

## Open questions

- Metadata isn't covered by the CID, and an owner can edit their public
  records. The digest is the owner's statement, not a commitment the bytes
  make. Good enough? An edit could be refused for `image` once published,
  so a new digest means republishing.
- A notebook published without ever being launched has no digest. Publish
  without `image` and show that, or ask for a launch first?
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
- [ ] Infra: resolve and serve on the digest at launch; remember it; stamp
      `image` and `image_tag` at publish; compare on launch.
- [ ] This repo: `image` and `image_tag` on `Notebook`
      (`src/stargazer/assets/notebook.py`), and
      `docs/architecture/notebook.md` on what a published notebook records.
