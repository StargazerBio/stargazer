---
title: union-volumes
status: doing
priority: normal
created: 2026-11-25
---

Union shipped Volumes: a durable, versioned filesystem a task or app mounts like a directory. It's JuiceFS over the cluster's bucket, plus a metadata store for versions and copy-on-write forks, mounted through a broker DaemonSet (`volumes.union.ai` CSI driver), so a pod needs no `CAP_SYS_ADMIN` or `/dev/fuse`. The aim: put the notebook workspace on volumes and delete the autosave and workspace-state code built around the object-per-file store.

**Where it stands (2026-11-25):** a spike on the tenant (below) showed volumes work on the cluster but no per-user role could write one, since a volume's chunks live at the bucket root. Infra PR 57 grants each role `vol-<subject>-*`; it waits on apply. Notebook environments stay in the image and its warm cache: a read-only volume can't hold one (pixi writes into it), and they build in 3 to 6 s anyway. Each notebook gets its own volume (decided, [Plan](#plan-the-workspace-on-volumes)).

## What it is

Read in the docs (`user-guide/tasks/task-programming/volumes/` and its `in-tasks`, `versions`, `local`, `performance`, `block-volumes` pages), PyPI and the client's source (`flyteplugins/union/io/_base_volume.py`, 0.26.2):

- `flyteplugins-union` (0.26.2) carries the client and needs `flyte>=2.13.4,<2.16`. Our lock has `flyte` 2.12.4, so using it starts with a Flyte bump. The Stargazer image's runtime venv already has 2.14.0.
- `Volume.new(name=, artifact=, bucket=, ...)` gives an `RWVolume`. `await vol.mount()` returns the path to use. `commit()` records a version and stays mounted, and `finalize()` commits and unmounts, returning an `ROVolume`. `fork()` makes a COW branch. A committed version has a `locator`, which `Volume.from_locator()` loads read-only from anywhere. Volumes are typed task inputs and outputs.
- **One writer at a time.** Mounting one volume read-write from two pods is unsupported, with no locking and no merge. Any number of pods can mount an `ROVolume`, and read-only mounts can share a node's chunk cache. Parallel writers each fork.
- **Chunks live at `<bucket root>/<volume name>/`.** JuiceFS's S3 driver takes the first path segment of the bucket URI as the bucket and drops the rest, and a volume's name is its JuiceFS format name, which can't hold a slash. A fork keeps writing under its ancestor's name. The default bucket is derived from the task's raw-data path, so on our tenant it's `stargazerbio-users`.
- No list or delete API in the SDK, versions are kept until pruned, and no pricing is published. The devbox has no mount broker. `flyte mount volume` mounts one on a laptop (NFS on macOS).

## What the spike found (measured 2026-11-25)

**The cluster is ready.** The `volumes.union.ai` CSI driver and the `union-uvol-broker` DaemonSet (worker nodes, 2/2 ready) are installed, and Knative's `config-features` has `kubernetes.podspec-volumes-csi` and `kubernetes.podspec-volumes-mount-propagation` enabled (read with `kubectl get`). An app pod with `allow_volumes()` was ready about 4 s after deploy.

**Per-user roles can't write a volume.** In `u-pryce`, as `stargazer-user-u-pryce`, `juicefs format` failed with S3 `AccessDenied` on `PutObject` to `s3://stargazerbio-users/volprobe-p1/`. The bucket policy gave each role only `users/${aws:PrincipalTag/stargazer-subject}/*`, and a volume's chunks land at the bucket root. Run `u5qpkqtbld7dq4nl4v6k`, aborted. Infra PR 57 adds `vol-${aws:PrincipalTag/stargazer-subject}-*` to the role's objects and listing: a fork's chunk branch is its own name's first 50 characters plus a random suffix (`_fresh_format_name`), so every volume and fork named `vol-<subject>-...` stays inside it.

**Volumes work under the shared role.** The rest ran in `flytesnacks`, as `union-us-west-2-stargazerbio-userflyterole`, with `bucket="s3://union-us-west-2-stargazerbio"`, 2 CPU and 4Gi:

- Writable (run `u5ctdb92j6bclbv8xjnb`): mount 0.92 s, a 50 MB write 0.11 s, `commit()` 1.05 s, `finalize()` 0.83 s. A file written after `commit()` was in the finalized version.
- Read-only from the locator in another pod (run `u28x5gs9ncnct94dlnnk`): mount 0.77 s, reading the 50 MB file 0.52 s, and a write failed with `Read-only file system`.

**The client is light at these sizes.** A mount adds about 90 MiB to the pod (two juicefs processes, about 54 and 48 MB RSS idle), read-only or writable. After committing 50 MB the client was 170 MB RSS and the pod peaked at 387 MiB; after reading 50 MB, 102 MB and 334 MiB. Copying 521 MB into a volume took the client to 531 MB RSS, with the pod at 2.16 GiB counting page cache. Nothing came near 1Gi, so the reported 4Gi floor isn't borne out for small volumes; large writes weren't tried.

**A notebook's environment can't open from a read-only volume.** Task C (run `ugxk224f6vrgcwv4k7pz`) built a header (the tutorials' plus `pyfiglet` and `jq`, both outside the warm cache) with `pixi install --script` and copied the environment into a volume. App `volprobe-vol` mounted it read-only at the environment's path and launched marimo through `launch-notebook.sh`:

- Mounted at the prefix, pixi failed in 0.92 s: `failed to acquire install lock on prefix ... Read-only file system`.
- With a writable prefix whose entries link into the mount, pixi failed after 11 s removing `bin/stargazer`: it reinstalls the `stargazer-bio` path dependency in a fresh pod (inferred from the error). marimo's sandbox runs the same command and exited 1.

**And the build it would save is short.** The same header built cold in 3.05 s in task C and 3.2 to 6.5 s in app `volprobe-novol`, which reached `/__sg__/ready` in 8.3 to 10.4 s and got `kernel-ready` 6 to 7 s later. A volume mount costs about 1 to 1.5 s, so even working it would save a few seconds on a header like this. Larger headers weren't measured.

## Plan: the workspace on volumes

### What it replaces

Today every file in a user's workspace is an object at `<STARGAZER_WORKSPACE_ROOT>/users/<subject>/workspace/<path>`, and each notebook pod copies the whole workspace in and syncs it back (line counts on `main`, 2026-11-25):

- `runtime/proxy.py`: hydrate and the prefix download (about 100 lines), and the save pass, sign-in save, save status and the shutdown flush (about 190): diffing by size and mtime, mirroring deletes, not resurrecting a file the dashboard deleted, never saving the blank of a notebook that didn't hydrate, the 100 MB cap. Plus `runtime/save_banner.html` (142 lines) and the save tests in `tests/unit/test_proxy.py`.
- Infra: `app/workspace_store.py` (128 lines, the object-per-file layout), the workspace store's layout in the pod contract, `SG_SAVE_INTERVAL_SECONDS`, and every dashboard route that reads or writes a notebook's object.
- The races they guard, each with a ticket: [[conditional-workspace-writes]], [[gear-save-race]], [[delete-running-notebook-resurrects]], [[unhydrated-notebook-banner]], [[save-status-poll]].

### What a volume gives, and what it doesn't

A pod mounts in about 1 s whatever the workspace's size, reads lazily, has no file-size cap, and every commit is a version a user could go back to. But a volume has **one writer**. JuiceFS keeps the filesystem's metadata on the pod's disk (`badger:///home/flyte/.flyte-volume/...`) until `commit()` uploads it, so:

- **Saving doesn't disappear, it shrinks.** A pod still commits on a timer and once more at shutdown (`finalize()`), or a crash loses everything since the last commit. That's a few lines in place of the diffing and mirroring above.
- **Something has to name the latest version.** A pod forks it to write, so each commit produces a new locator, recorded where the next pod and the dashboard read it: a row in the user's state table, updated only if it still names the version the pod forked (a compare-and-set, which turns today's silent last-writer-wins into a refusal).
- **Versions pile up.** Each commit is kept, with the chunks it wrote, and the SDK has no prune or delete. A fork or a new version costs only what it changes, since unchanged chunks stay shared (read in the docs and `chunk_branch`'s comment, not measured), so a notebook file's edits cost little. What lasts is a big file written into a notebook's folder: deleting it leaves its chunks in the versions that held it. Commit only when something changed.
- **Two writers can't share one volume.** Today a user with two notebooks open has two pods writing one workspace, and the dashboard writes notebooks (create, copy, open from GitHub, the gear, delete) while pods run. That's the decision below.

### Decision: who writes a workspace

**Decided 2026-11-25: B, one volume per notebook.**

- **A. One volume per user, one pod per user.** One workspace pod mounts it read-write and serves every notebook. The dashboard's notebook routes become file operations in that pod, or the dashboard joins it. Removes the most: the sync, and also per-notebook apps and their launch state. But it's a new pod model: one pod's memory for every open kernel, no per-notebook size (`main_env`), and run-mode pods that only read a version. Unknown whether marimo serves a directory with a pixi sandbox per notebook.
- **B. One volume per notebook (recommended).** A notebook's folder is its own volume. Its edit pod is the only writer, which the per-notebook app already guarantees (one replica per notebook and mode), and its run-mode pod mounts the latest version read-only, so it runs a consistent snapshot. The dashboard writes a notebook's volume only while no pod has it, as the gear already checks (`_notebook_running`): create, copy and open-from-GitHub make a new volume holding the file, and delete stops the pods and drops the pointer. Tiles read each notebook's name and description from the state table, written when the dashboard or the pod commits, so listing mounts nothing. The cost: a notebook sees only its own folder, so files shared between notebooks go, and data belongs in the asset store, as it already does across pods. Agent sign-ins are per user and written by every pod, so they keep today's small sync under `agents/`.

Forks don't make one workspace writable by several pods. A fork is a separate branch, and the client has no merge or diff (read in 0.26.2: its volume methods are `fork`, `clone`, `commit`, `finalize` and the like, nothing that combines two branches). Two pods forking the user's latest version end with two versions, each holding one pod's edits, and the pointer can name only one. Combining them means finding what each pod changed and copying it into a fresh fork of the latest, which is today's diffing and mirroring again, plus a mount and finalize per save. Forks do fit B: a pod's working copy is a fork of its notebook's latest version, copying a notebook is a fork of its volume (copy-on-write, nothing duplicated), and a built-in notebook could be a volume every user forks.

**A fork per pod, not per notebook.** Within one pod a fork commits as often as it likes, each commit a version on a linear history (`RWVolume.commit` docstring). It doesn't outlive the pod: its metadata index lives on the pod's disk until committed, a finalized branch comes back as an `ROVolume`, and the client's way to write a version again is `fork()` (its module example, `update(vol: ROVolume) -> RWVolume`). There's no reopening a branch from another pod. So each edit session is one fork with many versions, and a notebook's history is a chain of forks, one per pod start. Each fork's chunks are a new layer over its parent's (`juicefs config --push-layer`), with no documented depth limit or flattening (`clone` copies into a fresh family with no layers). Measured to 300 forks with no slowdown (see Pieces).

Both drop the devbox's persistence: it has no mount broker, and Union comes first. Locally nothing changes, since nothing is saved there today.

### The contract (decided 2026-11-25)

What the pod and the dashboard agree on, replacing the workspace store's layout in the pod contract:

- **A manifest per workspace notebook**, the object `<STARGAZER_WORKSPACE_ROOT>/users/<subject>/notebooks/<slug>.json`: `{"locator": <the latest version's locator>, "file": <the notebook's filename>, "source": <that file's text in that version>}`. It names the latest version and carries the notebook's source with it, so the dashboard's tiles, gear, download, publish and launch read one small object and never mount a volume to read. Every write is conditional: a new notebook's with `If-None-Match: *`, every other with `If-Match` on the ETag the writer last read or wrote (obstore's `put(mode=...)`). A refused write means someone else wrote it; the writer stops and says so, and its versions stay reachable by locator.
- **Volumes** are named `vol-<subject>-<8 hex>`, in the workspace root's bucket, with version metadata under `<root>/users/<subject>/volumes` (passed as `bucket=` and `metadata_prefix=` to `Volume.new`; forks inherit both, and their chunk branches extend the name, so they stay in `vol-<subject>-*`).
- **The pod** gets the manifest's URI in `SG_NOTEBOOK_MANIFEST` and the notebook's path as `/workspace/<slug>/<file>`, and mounts the notebook's volume at `/workspace/<slug>` before marimo starts (`/workspace` is `flyte`'s, so the client can make its link there; `/workspace/AGENTS.md` stays the agents' context, a parent of the notebook's folder). In edit mode it forks the latest version and mounts the fork read-write, commits every `SG_SAVE_INTERVAL_SECONDS` when a file changed since the last commit, finalizes at shutdown, and writes the manifest after each commit. In run mode it mounts the latest version read-only and writes nothing. With no `SG_NOTEBOOK_MANIFEST` (a built-in notebook, locally) it mounts nothing. The proxy holds the mount, since the process that mounts is the one that commits.
- **The dashboard** writes a notebook only while no pod has it (`_notebook_running`): create, copy and open-from-GitHub make a new volume holding the file, finalize it and create the manifest; the gear forks the latest version, writes the file, finalizes and updates the manifest; delete stops the pods and deletes the manifest.
- **Agent sign-ins** keep today's save under `users/<subject>/agents/`.
- **Not carried over:** the old `users/<subject>/workspace/` objects, and files a notebook shared with others. The devbox has no workspace notebooks (no mount broker).

### Pieces

- [ ] Infra PR 57: each role may write `vol-<subject>-*` (waits on apply), then a task in `u-pryce` creates, commits and remounts a `vol-<subject>-...` volume as the user's own role.
- [x] Fork depth: 300 forks in a row, each writing a small file (run `ulb92ltxksb7wpbcs487`, `flytesnacks`, 2026-11-25). Per session the read-write mount stayed 0.24 to 0.27 s and finalize went from 0.97 s (first 10) to about 1.3 s; a fresh read-only mount was 0.06 s at depth 1 and 0.10 s from depth 10 to 300, with the client flat at about 120 MB. A `clone` of the 300-deep version took 1.07 s and mounted no faster. No clone schedule needed at this write volume; larger writes per layer weren't tried.
- [ ] Stargazer: `flyte>=2.13.4` and `flyteplugins-union` in the runtime group; the proxy and launch script on the contract above; hydrate, the save pass, the save status, `save_banner.html` and `SG_UNSAVED_NOTEBOOK` gone; the pod contract in `docs/architecture/runtime.md` rewritten.
- [ ] Infra: `flyteplugins-union` bumped; `allow_volumes()` on notebook apps and the dashboard, merged with `SMALL_NODE`; the dashboard's notebook routes on manifests and volumes; `workspace_store.py` gone; the launch passing `SG_NOTEBOOK_MANIFEST` and the new path.
- [ ] End to end on the tenant as the test account: create a notebook, edit it, stop the pod, relaunch and find the edit; run mode shows it; the gear and delete work; the manifest's ETag refuses a stale write.

Retention waits for Union to ship one (decided 2026-11-25): until then every version is kept. The aim is a month, with each notebook's latest version kept however old. An S3 lifecycle rule can't do it, since an untouched notebook's only version would expire and an old chunk can back the newest version.

## Elsewhere

- **Environments the warm cache doesn't cover.** A pod would fork the header's volume and mount the fork read-write, so pixi can take its lock and relink the path dependency. Untested, and worth it only for headers that download a lot.
- **Reference data for task fan-outs.** A read-only volume of a reference and its companions, with a shared node cache, read once per node instead of downloaded by every task pod. Measure how long task pods spend fetching a full-size reference first.
- **Not the asset store or index.** An asset is a file named by its CID, listed and queried by the dashboard and every pod at once and published to Pinata by CID, and the index takes concurrent writes from parallel tasks.

## Gotchas

- `mount()` always mounts at `/uvol/mnt`; a `mount_path` is a symlink to it, not a mount point.
- Task pods run as uid 1000, so a `mount_path` must be somewhere `flyte` owns (`/home/flyte`, `/opt/pixi-cache`). `/mnt/...` fails with `PermissionError`.
- A task on the Stargazer image runs its `ENTRYPOINT` (`start-local.sh`), which ignores Flyte's arguments and fails on `flyte create config`. An app's entrypoint is replaced, so notebook pods are fine; a task on that image needs the entrypoint overridden (the spike linked `start-local.sh` to `/usr/bin/env`).
- A pixi environment holds about 15,500 symlinks into the uv cache. Copying it into a volume has to dereference them: a 192 MB environment became 521 MB and took 20 s.
- The spike's chunks (`volprobe-p1`, `volprobe-env`) are left in `union-us-west-2-stargazerbio`, and its images (`volprobe-img`) in ECR.

Related: [[board]], [[prebuilt-notebook-environment]], [[layered-notebook-image-cache]], [[header-declared-pod]], [[warm-uv-cache]], [[data-aware-caching]], [[conditional-workspace-writes]], [[flyte-apps]], [[flyte-io]], [[marimo-sandbox]].
