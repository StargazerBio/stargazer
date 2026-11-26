---
title: union-volumes
status: later
priority: normal
created: 2026-11-25
---

Union shipped Volumes: a durable, versioned filesystem a task or app mounts like a directory. It's JuiceFS over the cluster's bucket, plus a metadata store for versions and copy-on-write forks, mounted through a broker DaemonSet (`volumes.union.ai` CSI driver), so a pod needs no `CAP_SYS_ADMIN` or `/dev/fuse`. This ticket weighs where it simplifies Stargazer's state and where it doesn't.

**Where it stands (2026-11-25):** nothing worth building yet. A spike on the tenant found that under our per-user roles no volume can be written at all, that a read-only volume can't hold a notebook's environment because pixi writes into it, and that the environment it would have saved builds in 3 to 6 s from the image's warm cache anyway. Revisit if Union lets a volume's chunks live under a prefix, or if notebooks start needing environments the warm cache doesn't cover.

## What it is

Read in the docs (`user-guide/tasks/task-programming/volumes/` and its `in-tasks`, `versions`, `local`, `performance`, `block-volumes` pages), PyPI and the client's source (`flyteplugins/union/io/_base_volume.py`, 0.26.2):

- `flyteplugins-union` (0.26.2) carries the client and needs `flyte>=2.13.4,<2.16`. Our lock has `flyte` 2.12.4, so using it starts with a Flyte bump. The Stargazer image's runtime venv already has 2.14.0.
- `Volume.new(name=, artifact=, bucket=, ...)` gives an `RWVolume`. `await vol.mount()` returns the path to use. `commit()` records a version and stays mounted, and `finalize()` commits and unmounts, returning an `ROVolume`. `fork()` makes a COW branch. A committed version has a `locator`, which `Volume.from_locator()` loads read-only from anywhere. Volumes are typed task inputs and outputs.
- **One writer at a time.** Mounting one volume read-write from two pods is unsupported, with no locking and no merge. Any number of pods can mount an `ROVolume`, and read-only mounts can share a node's chunk cache. Parallel writers each fork.
- **Chunks live at `<bucket root>/<volume name>/`.** JuiceFS's S3 driver takes the first path segment of the bucket URI as the bucket and drops the rest, and a volume's name is its JuiceFS format name, which can't hold a slash. A fork keeps writing under its ancestor's name. The default bucket is derived from the task's raw-data path, so on our tenant it's `stargazerbio-users`.
- No list or delete API in the SDK, versions are kept until pruned, and no pricing is published. The devbox has no mount broker. `flyte mount volume` mounts one on a laptop (NFS on macOS).

## What the spike found (measured 2026-11-25)

**The cluster is ready.** The `volumes.union.ai` CSI driver and the `union-uvol-broker` DaemonSet (worker nodes, 2/2 ready) are installed, and Knative's `config-features` has `kubernetes.podspec-volumes-csi` and `kubernetes.podspec-volumes-mount-propagation` enabled (read with `kubectl get`). An app pod with `allow_volumes()` was ready about 4 s after deploy.

**Per-user roles can't write a volume.** In `u-pryce`, as `stargazer-user-u-pryce`, `juicefs format` failed with S3 `AccessDenied` on `PutObject` to `s3://stargazerbio-users/volprobe-p1/`. The bucket policy gives each role only `users/${aws:PrincipalTag/stargazer-subject}/*`, and a volume's chunks land at the bucket root. Making it work would take a bucket-policy statement keyed on a name prefix (say `stargazerbio-users/v-${aws:PrincipalTag/stargazer-subject}-*`, with names to match), or a chunk prefix option from Union. Run `u5qpkqtbld7dq4nl4v6k`, aborted.

**Volumes work under the shared role.** The rest ran in `flytesnacks`, as `union-us-west-2-stargazerbio-userflyterole`, with `bucket="s3://union-us-west-2-stargazerbio"`, 2 CPU and 4Gi:

- Writable (run `u5ctdb92j6bclbv8xjnb`): mount 0.92 s, a 50 MB write 0.11 s, `commit()` 1.05 s, `finalize()` 0.83 s. A file written after `commit()` was in the finalized version.
- Read-only from the locator in another pod (run `u28x5gs9ncnct94dlnnk`): mount 0.77 s, reading the 50 MB file 0.52 s, and a write failed with `Read-only file system`.

**The client is light at these sizes.** A mount adds about 90 MiB to the pod (two juicefs processes, about 54 and 48 MB RSS idle), read-only or writable. After committing 50 MB the client was 170 MB RSS and the pod peaked at 387 MiB; after reading 50 MB, 102 MB and 334 MiB. Copying 521 MB into a volume took the client to 531 MB RSS, with the pod at 2.16 GiB counting page cache. Nothing came near 1Gi, so the reported 4Gi floor isn't borne out for small volumes; large writes weren't tried.

**A notebook's environment can't open from a read-only volume.** Task C (run `ugxk224f6vrgcwv4k7pz`) built a header (the tutorials' plus `pyfiglet` and `jq`, both outside the warm cache) with `pixi install --script` and copied the environment into a volume. App `volprobe-vol` mounted it read-only at the environment's path and launched marimo through `launch-notebook.sh`:

- Mounted at the prefix, pixi failed in 0.92 s: `failed to acquire install lock on prefix ... Read-only file system`.
- With a writable prefix whose entries link into the mount, pixi failed after 11 s removing `bin/stargazer`: it reinstalls the `stargazer-bio` path dependency in a fresh pod (inferred from the error). marimo's sandbox runs the same command and exited 1.

**And the build it would save is short.** The same header built cold in 3.05 s in task C and 3.2 to 6.5 s in app `volprobe-novol`, which reached `/__sg__/ready` in 8.3 to 10.4 s and got `kernel-ready` 6 to 7 s later. A volume mount costs about 1 to 1.5 s, so even working it would save a few seconds on a header like this. Larger headers weren't measured.

## Where it could still fit

- **Environments the warm cache doesn't cover.** Only if a writable mount works: a pod forks the header's volume and mounts the fork read-write, so pixi can take its lock and relink the path dependency, and the fork is thrown away. Untested, and worth it only for headers that download a lot.
- **Reference data for task fan-outs.** A read-only volume of a reference and its companions, with a shared node cache, read lazily once per node instead of downloaded by every task pod. It cuts across the asset model, so measure first how long task pods spend fetching a full-size reference.
- Both need the per-user write path above first.

## Where it doesn't

- **The asset store and index.** An asset is a file named by its CID, stored once per user, listed and queried by the dashboard and every pod at once, and published to Pinata by CID. The index takes concurrent writes from parallel tasks. A single-writer volume can do neither, and the SDK has to run the same locally and on the devbox, which have no broker.
- **The workspace.** A volume would replace hydrate and the save loop in `runtime/proxy.py` with `mount()` and a periodic `commit()`, with version history for free. But every notebook pod hydrates the owner's whole workspace and saves back to it, so a user with two notebooks open is two writers, and the dashboard deletes and uploads notebooks while pods are live. It fits only if a user's workspace has one writer, which is a change to the pod model.
- **Agent sign-ins and the state table.** Small, and fine as they are.

## Gotchas

- `mount()` always mounts at `/uvol/mnt`; a `mount_path` is a symlink to it, not a mount point.
- Task pods run as uid 1000, so a `mount_path` must be somewhere `flyte` owns (`/home/flyte`, `/opt/pixi-cache`). `/mnt/...` fails with `PermissionError`.
- A task on the Stargazer image runs its `ENTRYPOINT` (`start-local.sh`), which ignores Flyte's arguments and fails on `flyte create config`. An app's entrypoint is replaced, so notebook pods are fine; a task on that image needs the entrypoint overridden (the spike linked `start-local.sh` to `/usr/bin/env`).
- A pixi environment holds about 15,500 symlinks into the uv cache. Copying it into a volume has to dereference them: a 192 MB environment became 521 MB and took 20 s.
- The spike's chunks (`volprobe-p1`, `volprobe-env`) are left in `union-us-west-2-stargazerbio`, and its images (`volprobe-img`) in ECR.

Related: [[board]], [[prebuilt-notebook-environment]], [[layered-notebook-image-cache]], [[header-declared-pod]], [[warm-uv-cache]], [[data-aware-caching]], [[conditional-workspace-writes]], [[flyte-apps]], [[flyte-io]], [[marimo-sandbox]].
