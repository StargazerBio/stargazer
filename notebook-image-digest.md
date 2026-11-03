---
title: notebook-image-digest
status: backlog
priority: normal
created: 2026-11-02
---

Know the exact image a notebook ran in: launch its pod on a resolved
digest and remember it, so a run record (ticket `run-records`) can carry
it and a replay can pull it. The notebook keeps `main_env` as the author
wrote it: the recipe says what the environment is and why, which a digest
can't. The digest belongs to each run, not to the notebook. The digest is
the image's identity, the way a CID is a file's; whether its bytes are
public is a separate fact. A digest in a private registry is still a
byte-accurate commitment, and the image behind it can be made public
later. Copying an image between registries keeps its digest (inferred;
check with `crane copy`).

## Decided (2026-11-02)

- **A notebook runs from its own `main_env` by default.** Its image can be
  anything the author wants. Replaying a run can instead pull the image the
  run recorded.
- **The digest is recorded per run, beside the notebook, never in it.**
- **No asking authors to pin layers.** It won't stick.

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
2. **Make it readable in the pod**, e.g. an env var the dashboard sets at
   launch, so a run record built in the notebook can include it.
3. **Build or pull on replay.** Replaying a run offers **build** from the
   notebook's `main_env` or **pull** the recorded digest. Pull is offered
   only where the digest can be pulled (the same deployment); elsewhere it
   builds and says why. A build whose digest differs from the record's says
   so: results may differ.

## Open questions

- Task images a run uses (`gatk_env`, `scrna_env`, a notebook's own
  `TaskEnvironment`s) have the same tag problem. Resolve their digests when
  the run record is built (from the tags Flyte recorded), or leave them to
  the tags?
- Making a digest public: a later "publish environment" step copies the
  image to a public registry, digest unchanged. Not in this ticket.

## Pieces

- [ ] Experiment on the Union tenant, as the test account: the dashboard's
      role can `DescribeImages` on a Union-built tag and gets a digest; an
      `AppEnvironment` on `…@sha256:…` serves; `crane copy` to another
      registry keeps the digest.
- [ ] Infra: resolve and serve on the digest at launch; expose it in the
      pod.
- [ ] Build or pull, with ticket `run-records`' replay.

Related: [[run-records]], [[launch-build-state]], [[shared-image-repository]], [[board]].
