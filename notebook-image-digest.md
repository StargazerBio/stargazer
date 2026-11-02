---
title: notebook-image-digest
status: backlog
priority: normal
created: 2026-11-02
---

A published notebook names the exact image it runs in, inside the notebook
itself: its `main_env` declares the image by a fully qualified digest,
`flyte.Image.from_base("<repo>@sha256:<digest>")`. The notebook's CID then
covers its environment: change the image and the notebook's CID changes
with it, which is a new version of the notebook, as it should be. The
digest is the image's identity, the way a CID is a file's; whether its
bytes are public is a separate fact. A digest in a private registry is
still a byte-accurate, public commitment, and the image behind it can be
made public later. Copying an image between registries keeps its digest
(inferred; check with `crane copy`).

## Decided (2026-11-02)

- **A notebook always runs from its own `main_env`.** Its image can be
  anything the author wants. Nothing outside the file (the dashboard, the
  record's keyvalues) overrides it or stands in for it.
- **For publishing, strongly encourage a digest** in `main_env`. Don't
  require it, and don't ask authors to pin every layer (versioned apt and
  bioconda packages): that won't stick.
- **The notebook lives outside the environment it defines.** If the image
  contained the notebook, writing the image's digest into the notebook
  would change the image, and so its digest: a loop with no fixed point.

## The notebook outside its image

True today for the notebooks people publish, from the code:

- **Workspace notebooks** aren't in any image. A pod hydrates the owner's
  workspace into `/workspace` when it starts (`runtime/launch-notebook.sh`,
  step 1), and the notebook's tasks reach a cluster in the run's code
  bundle, not its image (inferred).
- **A declared image** is built from the setup block's recipe on the pod's
  image; its bytes don't contain the notebook file.
- **Built-in notebooks are the exception:** they're baked into the release
  image (`/stargazer/src/stargazer/notebooks`, copied to `/opt/workspace`
  by `runtime/Dockerfile`). They can't name that image by digest, so they
  keep `notebook_base`, which resolves to the release they ship in. A
  built-in notebook is pinned by its release; a published one by the
  digest in its file. A published copy of a built-in notebook names a
  digest like any other.

Keep it this way: nothing should bake a workspace notebook into the image
it declares, for example a code-bundle layer in the declared image.

## Why the declaration's tag isn't enough

Read in Flyte 2.10.7 (`flyte/_image.py`, `_internal/imagebuild/remote_builder.py`),
not measured. An image's tag is an md5 of its *declaration* (the base
image's name and each layer's text; only `with_uv_project` hashes real
contents, the lock file), so unversioned packages rebuild to new bytes
under the same tag. The remote builder returns only `<registry>/<name>:<tag>`.
And every project pushes to one shared ECR repository where any user's pod
can overwrite a tag (ticket `shared-image-repository`). A recipe in
`main_env` is fine for working; a digest is what makes a published one
exact.

## Making the digest easy to get

An author works with a recipe (`notebook_base.with_apt_packages(...)`),
then freezes it to the digest of what was built. The freeze is where help
is needed, since Flyte gives a tag, not a digest:

- After a launch builds a declared image, the dashboard resolves its tag to
  a digest (ECR `DescribeImages`, or the registry's manifest
  `Docker-Content-Digest`) and shows it on the tile's environment gear, with
  a one-click "freeze", which rewrites the `main_env` line to
  `from_base("<repo>@sha256:...")`. The gear already edits the setup block.
- Publishing a notebook whose `main_env` image isn't a digest warns, says
  what that means for anyone who opens it (their image is rebuilt from the
  recipe and may differ), and offers the same freeze.
- The same advice holds for the `TaskEnvironment`s a notebook declares
  (the template's `my_env`): their images are where its cluster runs
  happen.

## Open questions

- Does Flyte launch an `AppEnvironment` on `from_base("…@sha256:…")` as is,
  and does the dashboard's evaluation of the `main_env` line accept it?
  Read as yes (a non-cloned image's `uri` is the base string unchanged),
  not tried.
- A digest someone else can't pull (a private registry): the launch fails.
  The error should say the image isn't available to them and that the
  owner can make it public.
- Making a digest public: a later "publish environment" step copies the
  image to a public registry, digest unchanged. Not in this ticket.

## Pieces

- [ ] Experiment on the Union tenant, as the test account: launch a
      notebook whose `main_env` is `from_base("<repo>@sha256:...")` and see
      it serve on that image; the dashboard's role can `DescribeImages` on
      a Union-built tag; `crane copy` to another registry keeps the digest.
- [ ] Infra: the freeze on the gear, and the warning at publish.
- [ ] This repo: the template's `main_env` comment and
      `docs/architecture/notebook.md` (Notebook Environment) say how to pin
      for publishing; the `src/stargazer/notebooks/__init__.py` docstring
      for `main_env`.
