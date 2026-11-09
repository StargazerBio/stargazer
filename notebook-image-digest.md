---
title: notebook-image-digest
status: done
priority: normal
created: 2026-11-02
pr: 31
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

Read in Flyte 2.12.4 (`flyte/_image.py`, `_internal/imagebuild/remote_builder.py`),
not measured. An image's tag is an md5 of its *declaration* (the base
image's name and each layer's text), plus real contents for the layers
that hash them: `with_uv_project` and `with_pixi_project` hash the lock
file and manifest (`dependencies_only`) or the project's files, and
`with_source_folder` the folder's files. So a notebook's `main_env` that
installs unversioned packages rebuilds to new bytes under the same tag.
The task images (`_task_image` in `config.py`) are a pixi.lock environment
plus the source, so their tags follow the locked packages and the source;
the Debian base layer is still unpinned. The remote builder returns only
`<registry>/<name>:<tag>`.
Every project pushes to one shared ECR repository where any user's pod can
overwrite a tag (ticket `shared-image-repository`).

## Shape

1. **Resolve, then launch on the digest.** When a launch's image is ready
   (built, or found), the dashboard resolves its tag to a digest and serves
   the pod on `flyte.Image.from_base("<repo>@sha256:<digest>")`. An ECR tag
   resolves through `ecr:BatchGetImage`, which the user's role already has
   for builds; it can't `DescribeImages` (measured, below). Any other
   registry resolves through the registry API's manifest `HEAD`
   (`Docker-Content-Digest`), anonymously, which GHCR's public packages and
   the devbox's registry answer. The release image is pinned once, at
   deploy, into the dashboard's `STARGAZER_NOTEBOOK_IMAGE`: the deployer
   can reach the devbox's `localhost:30000` registry, which a devbox pod
   can't, and a dashboard and its pods then agree on bytes, not just a tag.
   So a default launch makes no registry call, and a declared image's
   launch makes one `BatchGetImage`. This still runs `main_env`'s image,
   resolved, and makes the digest exactly what the pod runs, with no race
   against a tag moving between the lookup and the pull.
2. **Make it readable in the pod**: the dashboard sets `STARGAZER_POD_IMAGE`
   (`<repo>@sha256:<digest>`, what the pod runs) at launch, so a run record
   built in the notebook can include it. Stargazer's pod contract
   (`docs/architecture/runtime.md`) lists it when `run-records` first reads
   it.
3. **Build or pull on replay.** Replaying a run offers **build** from the
   notebook's `main_env` or **pull** the recorded digest. Pull is offered
   only where the digest can be pulled (the same deployment); elsewhere it
   builds and says why. A build whose digest differs from the record's says
   so: results may differ.

## Open questions

- Task images a run uses (`gatk_env`, `scrna_env`, a notebook's own
  `TaskEnvironment`s): `gatk_env`'s and `scrna_env`'s tags follow pixi.lock
  and the source, but any pod can still overwrite a tag in the shared
  repository, and a notebook's own `TaskEnvironment` can install unversioned
  packages. Resolve their digests when the run record is built (from the
  tags Flyte recorded), or leave them to the tags?
- Making a digest public: a later "publish environment" step copies the
  image to a public registry, digest unchanged. Not in this ticket.

## Pieces

- [x] Experiment on the Union tenant, as the test account: the dashboard's
      role can resolve a Union-built tag to a digest; an `AppEnvironment` on
      `…@sha256:…` serves; `crane copy` to another registry keeps the digest.
- [x] Infra: pin the release image at deploy, resolve the served image at
      launch, serve on the digest, set `STARGAZER_POD_IMAGE` (infra PR 31).
- [ ] Build or pull, with ticket `run-records`' replay.

## Verification recipe

From an infra worktree on the branch, with `.flyte/union.yaml` linked,
`tenant.env` loaded and the built-in browser signed in to the console as the
test account. The `u-pryce` dashboard is shared, so check nobody else is
testing on it first.

1. `uv run python .claude/skills/verify-dashboard/scripts/union_dashboard.py deploy`.
   Then `App.get("dashboard", project="u-pryce")`'s served env should show
   `STARGAZER_NOTEBOOK_IMAGE=ghcr.io/stargazerbio/stargazer@sha256:…`, and
   `crane digest ghcr.io/stargazerbio/stargazer:v<release>` should print the
   same digest.
2. From the dashboard page, `fetch` `POST /launch` with `slug=assets`,
   `mode=edit`, `section=tutorials`. `union_dashboard.py check nb-assets-edit`
   should show the served image and its `STARGAZER_POD_IMAGE` as that same
   digest.
3. `POST /workspace/create` with `name=Digest probe`, then `POST
   /workspace/setup` with a `main_env` whose image is
   `notebook_base.with_apt_packages("tabix")`, then `POST /launch`. It answers
   202 with the build run. Once the build succeeds, `GET /launch/status`
   serves the pod. `nb-digest-probe-edit`'s served image should be
   `…/union/stargazerbio@sha256:…`.
4. Open its URL. A cell `import os, shutil;
   (os.environ['STARGAZER_POD_IMAGE'], shutil.which('tabix'))` should return
   that digest reference and `/usr/bin/tabix`.
5. Teardown: `POST /stop` for both apps, `POST /workspace/delete
   slug=digest-probe`, then `union_dashboard.py teardown`. Live runs should
   be `[]`.

On the devbox: `uv run python devbox/dashboard.py`, `curl -X POST <url>/launch
-F slug=assets -F mode=edit -F section=tutorials`. Then `kubectl get pod -n
flyte <nb-assets-edit pod> -o yaml` should show the image, `imageID` and
`STARGAZER_POD_IMAGE` as `ghcr…@sha256:…`; `kubectl exec` can print the env.

## Evidence (2026-11-07, infra PR 31)

Measured unless labeled.

- Tenant, dashboard `2026.10.30-5564662`:
  - `STARGAZER_NOTEBOOK_IMAGE` is
    `ghcr.io/stargazerbio/stargazer@sha256:5b3a040b4f5790195049a3bf08f0eea289db0466b8a10990650e499757ceef8b`.
  - `nb-assets-edit` is served on it, with `STARGAZER_POD_IMAGE` equal.
  - The declared `tabix` image built (run `unjp7nx9hktjl6v92s7s`) on the
    digest-named base. `nb-digest-probe-edit` was served on
    `791359099513.dkr.ecr.us-west-2.amazonaws.com/union/stargazerbio@sha256:51ba2f69425071691baa1075330ebc244dff2b73e964f8e01b6acee23f8daa54`,
    resolved by the dashboard's role. In the pod, a marimo cell read that
    reference and found `/usr/bin/tabix`.
  - All torn down.
- Devbox: the pod spec, `imageID`, and `STARGAZER_POD_IMAGE` read inside the
  pod were all `ghcr…@sha256:5b3a040b…`.
- The tenant run was on the commits before the rebase onto infra #30, which
  conflicted on one import line. The rebased code behaving the same is
  inferred.

## Experiment (2026-11-07)

All measured, in project `u-pryce`, as an org admin's Flyte login.

- **The role resolves through `BatchGetImage`, not `DescribeImages`.** A task
  (run `umjvd4jtvf7nv6489n4x`) on the Union-built
  `791359099513.dkr.ecr.us-west-2.amazonaws.com/union/stargazerbio:dashboard-84c314bd159ea69b027be4ed16713d64`
  ran as `assumed-role/stargazer-user-u-pryce`. `ecr:DescribeImages` on
  `union/stargazerbio`: `AccessDeniedException`, "no identity-based policy
  allows the ecr:DescribeImages action" (the managed
  `stargazer-user-union-read` grants pull and push only). `ecr:BatchGetImage`
  on the same tag: `sha256:76b3f73475e1237ae7bc7293807c2f89a454fdd74c28d754ffcdfc346f402b24`.
  So no policy change: the dashboard resolves with what builds already need.
- **An app on `…@sha256:…` serves.** `AppEnvironment` `digest-probe` on
  `…/union/stargazerbio@sha256:76b3f734…` (`python -m http.server`): the
  console's served image is the digest form, `is_active()` True, its URL
  answered 200 on the first try. Deactivated after.
- **`crane copy` keeps the digest.** `crane` (`gcr.io/go-containerregistry/crane@sha256:61bc7169…`)
  copied `ghcr.io/stargazerbio/stargazer:v2026.10.30`, a multi-arch index, to
  a throwaway `registry:2`: `crane digest` gave
  `sha256:5b3a040b4f5790195049a3bf08f0eea289db0466b8a10990650e499757ceef8b`
  on both sides. An ECR-to-elsewhere copy wasn't run (the read-only AWS
  login had expired); it's the same property, since a digest is the hash of
  the manifest bytes `crane` copies verbatim (inferred).
- Seen in passing: Union's image service (`GetImage`) returns an image's
  `fqin` and build run, no digest, so the registry is the only source.


## Outcome

Infra PR 31 merged on 2026-11-09. Notebook pods launch on `<repo>@sha256:<digest>`, resolved when the image is ready, and read it as `STARGAZER_POD_IMAGE`. Verified on the tenant and the devbox (recipe and evidence above). The tenant run predates the rebase onto infra PR 30, which touched one import line.

Left: build or pull on replay lives in ticket [[run-records]], which already plans it.

Related: [[run-records]], [[launch-build-state]], [[shared-image-repository]], [[board]].
