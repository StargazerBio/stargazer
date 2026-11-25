---
title: union-volumes
status: later
priority: normal
created: 2026-11-25
---

Union shipped Volumes: a durable, versioned filesystem a task or app mounts like a directory. It's JuiceFS over the cluster's bucket, plus a metadata store for versions and copy-on-write forks, mounted through a broker DaemonSet (`volumes.union.ai` CSI driver), so a pod needs no `CAP_SYS_ADMIN` or `/dev/fuse`. This ticket weighs where it simplifies Stargazer's state and where it doesn't.

## What it is (read 2026-11-25, not measured)

From the docs (`user-guide/tasks/task-programming/volumes/` and its `in-tasks`, `versions`, `local`, `performance`, `block-volumes` pages) and PyPI:

- `flyteplugins-union` (0.26.2 on PyPI) carries the client and needs `flyte>=2.13.4,<2.16`. Our lock has `flyte` 2.12.4, so using it starts with a Flyte bump. Apps need `flyte>=2.12.2`.
- `Volume.new(name=, artifact=)` gives an `RWVolume`. `await vol.mount()` returns the path to use. `commit()` records a version and stays mounted, and `finalize()` commits and unmounts, returning an `ROVolume`. `fork()` makes a COW branch. A committed version has a `locator`, which `Volume.from_locator()` loads read-only from anywhere. Volumes are typed task inputs and outputs, so an `RWVolume` returned from one task arrives as an `ROVolume` in the next.
- **One writer at a time.** Mounting one volume read-write from two pods is unsupported, with no locking and no merge. Any number of pods can mount an `ROVolume`, and read-only mounts can share a node's chunk cache (`allow_volumes(shared_node_cache=True)`). Parallel writers each fork.
- Every pod that mounts one needs `pod_template=allow_volumes(...)`, and memory for the client: JuiceFS, the metadata store and tmpfs staging count against the pod's limit. Its Go client's soft limit defaults to ~2 GiB. Reported: 1Gi OOMs, 4Gi is the floor.
- Apps can mount one, but the docs cover only a read-only version passed in as a locator parameter, and Knative must allow inline CSI volumes and mount propagation. Not confirmed on our tenant.
- No list or delete API in the SDK, versions are kept until pruned, and no pricing is published. The devbox has no mount broker, and the docs say nothing of local task runs. `flyte mount volume` mounts one on a laptop (NFS on macOS).

## Where it fits

**1. Notebook environments built once, mounted read-only.** Strongest fit. A hosted notebook builds its header's environment in the pod at every cold open, and anything its header adds beyond the image's warm cache is fetched again on each new pod. Ticket [[prebuilt-notebook-environment]] plans an image layer per header, built at launch, which brings Union's image builder and its cache questions along ([[layered-notebook-image-cache]]). A volume does the same with no image build: a task in the Stargazer image runs pixi on the header into a new volume mounted at the path the pod opens the notebook from (a pixi environment's prefix is baked in), finalizes it, and its artifact is named by the header's hash. The launch passes the locator to the notebook app, which mounts it read-only before marimo starts. An unchanged header reuses its volume, and every pod on a node shares one chunk cache. This also fits [[header-declared-pod]], which drops launch-time image builds: the environment would come from a volume instead of an image. The warm cache itself could move out of the image the same way.

**2. Reference data for task fan-outs.** Each task pod `fetch()`es its inputs into its own disk, so a per-sample fan-out downloads the reference and its aligner index once per pod. A read-only volume of a reference and its companions, with a shared node cache, would be read lazily and fetched once per node. It cuts across the asset model (an asset is a CID-named file in the store, and its companions are found by query), and the tutorials' references are small, so measure first how long task pods spend fetching a full-size reference before designing it.

## Where it doesn't

- **The asset store and index.** An asset is a file named by its CID, stored once per user, listed and queried by the dashboard and every pod at once, and published to Pinata by CID. The index takes concurrent writes from parallel tasks. A single-writer volume can do neither, and the SDK has to run the same locally and on the devbox, which have no broker.
- **The workspace.** It looks like the obvious target: a volume would replace hydrate and the save loop in `runtime/proxy.py` with `mount()` and a periodic `commit()`, and add version history for free. But every notebook pod hydrates the owner's whole workspace and saves back to it, so a user with two notebooks open is two writers, and the dashboard deletes and uploads notebooks while pods are live. A volume fits only if a user's workspace has one writer: one pod per user, or the dashboard never writing. That's a change to the pod model, not to storage.
- **The dashboard and login apps.** They run at 1Gi and 256Mi, under the client's floor.
- **Agent sign-ins and the state table.** Small, and fine as they are.

## Costs either fit carries

- Notebook pods default to 2 CPU and 4Gi (infra's `app/notebook_environment.py`), so a mounted volume's client takes much of a pod's memory. A read-only mount may use less than a writable one; measure before sizing.
- `allow_volumes()` is a pod template, and infra's apps already pass one (`SMALL_NODE`), so the two need merging.
- Works only on Union, so each fit needs today's path kept for local and devbox runs.

## To settle before it's `backlog`

Run as the test account in its own project; nothing here has run yet:

- [ ] A task with `allow_volumes()` creates, commits and remounts a volume under the per-user role (`stargazer-user-<project>`). The chunks go to a bucket path that role may not reach.
- [ ] A notebook app mounts a volume read-only from a locator parameter on our tenant (Knative's CSI flags), at a fixed mount path.
- [ ] A pixi environment built into a volume at the notebook's path opens with marimo's sandbox, and how long a cold open takes against today's warm-cache open.
- [ ] The pod's memory with a read-only mount mounted, at idle and while marimo builds.

Related: [[board]], [[prebuilt-notebook-environment]], [[layered-notebook-image-cache]], [[header-declared-pod]], [[warm-uv-cache]], [[data-aware-caching]], [[conditional-workspace-writes]], [[flyte-apps]], [[flyte-io]], [[marimo-sandbox]].
