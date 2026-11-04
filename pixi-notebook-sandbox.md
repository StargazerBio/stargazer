---
title: pixi-notebook-sandbox
status: done
priority: normal
created: 2026-11-03
pr: 131
---

Notebooks build their environments with pixi instead of uv, so a notebook's header can declare conda packages (bioconda's tools) beside its PyPI ones, and the notebook image stops installing gatk4, samtools, bwa and bwa-mem2 with an unpinned `micromamba create` in `runtime/Dockerfile`. The second stage of [[pixi-dependencies]], which moved the task images to pixi.lock and holds what the docs and Flyte's code say about marimo's pixi sandbox.

- pixi in the notebook image, `--sandbox=pixi` in `runtime/launch-notebook.sh`.
- Notebook headers point at the SDK through `[tool.pixi.pypi-dependencies]` (pixi ignores `[tool.uv.sources]`).
- The warm cache redone for pixi (rattler's cache in place of `/opt/uv-cache`).
- The micromamba block in `runtime/Dockerfile` goes; the germline notebook declares its tools in its header.
- The notebook template's and the tasks tutorial's `with_uv_project` environments move to `with_pixi_project`, split the way `_task_image` in `config.py` builds the task images: the environment with `dependencies_only`, then the source installed on top without dependencies. With `install_project`, as both use today, any source change reinstalls the whole environment, and an editable path dependency on the SDK fails `pixi install --locked` without the source present ([[pixi-layer-cache]]).

Open questions, from [[pixi-dependencies]]: open times against uv for a core notebook and the germline notebook; the kernel's `--with marimo` overlay over a conda prefix; the conda-to-PyPI name mapping, which pixi fetches from the network; whether hosted pods still need a declared `main_env` image for tools.

Verify a core notebook and the germline notebook locally and hosted, timed against uv.

## Decisions

- The SDK stays editable from `/stargazer`, now through `[tool.pixi.pypi-dependencies]`. A non-editable install puts `config.py` in site-packages, so `PROJECT_ROOT` no longer finds `pyproject.toml` and `pixi.lock`, and a kernel can't build the task images. The released package becomes the source with [[release-task-images]].
- The notebook image carries its own pixi (0.83.0): marimo's pixi sandbox needs `pixi install --script`, which Flyte's builder's 0.72.2 lacks.
- Environments link the caches by symlink: hardlinks out of an image layer cost an overlayfs copy-up per file.
- Tools go in the header, not in `main_env`'s image: a hosted pod needs no declared image for them (germline ran its whole pipeline in the pod from its header).
- The micromamba prefix from [[warm-uv-cache]] goes with it: a notebook declares its tools rather than installing them by hand.

## Verification recipe: notebooks on pixi

A notebook's environment is built by pixi from its header, so a notebook that declares bioconda's tools runs them in its own process, hosted and locally, and the built-in notebooks open from the image's warm cache.

### Sub-features

- `pixi-local-core`: the Assets tutorial opens in the local image, its environment built from the cache, and every cell runs.
- `pixi-local-tools`: a community notebook mounted into `/workspace` and opened from the file explorer gets its own environment, with its header's tools on its kernel's path and not on another notebook's.
- `pixi-hosted-core`: the Assets tutorial opens on a Union pod from its prebuilt environment, with nothing installed, and every cell runs.
- `pixi-hosted-tools`: the germline notebook opened from GitHub runs the whole pipeline "On this machine", every tool from its header.
- `pixi-hosted-cluster`: the same notebook's "On the cluster" run builds and runs the gatk task image from the editable SDK at `/stargazer`.

### How to get to it (user POV)

Locally, `docker run -p 8080:8080 <image>` and the Assets tutorial, or a notebook in a mounted `/workspace` opened from marimo's file explorer. Hosted, the dashboard's tutorial tiles and **Open from GitHub**.

### Driving it

Preconditions: docker; the community notebooks repo at a commit whose headers declare pixi dependencies; for Union, infra's `verify-dashboard` preconditions and a read-only kubeconfig (`aws eks update-kubeconfig --profile claude ... --role-arn arn:aws:iam::791359099513:role/stargazer-eks-access --kubeconfig <scratch>`).

- **Local core.** `docker build -f runtime/Dockerfile -t sg-pixi:dev .`, `docker run -d --name sgpixi -p 8080:8080 sg-pixi:dev`, open `http://localhost:8080`, run all cells: the footer shows 0 errors (`pixi-local-core`). `docker logs -t sgpixi` dates the kernel from the websocket to the first `datasources/discover`.
- **Local tools.** Copy the community germline notebook into a directory, `chmod -R a+rwX` it, run the image with `-v <dir>:/workspace`, open `/?file=%2Fworkspace%2Fshort-variant-discovery.py`. For each kernel process (`/opt/uv-cache/builds-v0/*/bin/python -m marimo._ipc.launch_kernel`), its environ's `PATH` resolves `gatk`, `samtools`, `bwa-mem2` and `java` for germline's and none for Assets' (`pixi-local-tools`).
- **Hosted.** Push the image to `ghcr.io/stargazerbio/debug:<slug>`, deploy the test account's dashboard with `STARGAZER_NOTEBOOK_IMAGE` set to it, `POST /launch` `slug=assets mode=edit section=tutorials`, open the app, run all cells: 0 errors, an asset CID in the round trip, and the pod log (`kubectl logs <nb-assets-edit pod> -c nb-assets-edit --timestamps`) shows no install before the kernel (`pixi-hosted-core`). Open germline with `POST /workspace/github` (its `main_name` names the copy, so a taken name is a 409), launch it in edit mode, run all, press **Run the pipeline** "On this machine" and run the stale cells: the run cell's console logs a `Running:` line per tool (`samtools faidx` through `gatk GenotypeGVCFs`) and the cohort VCF's summary renders (`pixi-hosted-tools`). Switch to "On the cluster" and run again: the console shows the `stargazer-gatk` image found or built and the run's URL, and the run succeeds (`pixi-hosted-cluster`).
- **Teardown.** infra's `union_dashboard.py teardown` prints `live runs: []`.

### Gotchas

- Flyte's image builder pins pixi 0.72.2, which has no `pixi install --script`; the notebook image carries its own pixi.
- A hardlink from an image layer into a new environment is an overlayfs copy-up, synced per file: a core notebook's first environment at a new path took 15 to 20 s that way, 3 s with pixi's hardlinks and reflinks disallowed (symlinks for PyPI files, copies for conda's).
- Copy-only linking fails: conda packages that contain symlinks need symlinks allowed.
- pixi keys a script's environment on its path, like uv: the tutorials' prebuilt environments serve only `/stargazer/src/...`. The templates are opened as copies, so the image keeps their packages but not their environments.
- Without `python = "3.14.*"` in the header pixi takes Python 3.15.
- pixi needs the network to install a script environment at a new path (offline it fails), and retries a channel request for 48 s offline even for a prebuilt one.
- marimo's edit mode here is lazy: a run button marks its cells stale, so run the stale cells after pressing it.
- `marimo export` has no pixi option; drive notebooks through the server.

## Outcome

Shipped in PR 131 (merged 2026-11-04). Notebook environments are built by pixi from each notebook's PEP 723 header. The tutorials' environments come prebuilt in the image, and a notebook's tools (germline's gatk4, samtools, bwa-mem2) come from its own header rather than the image. pixi 0.83 is in the notebook image because marimo's sandbox runs `pixi install --script`, which 0.72.2 lacks. The MCP server installs from pixi.lock's `mcp` environment with that pixi.

Verified on Union with `ghcr.io/stargazerbio/debug:pixi-notebook-sandbox` before 130 merged into the branch:
- Hosted Assets: from proxy up to kernel ready dropped from 49.5 s to 4–6 s.
- Hosted germline ran to 47 sites, both On this machine and on the cluster.
- The Execution tutorial's CIDs matched between local and remote.

After the merge (`d64dc50`), pre-commit, the unit tier (263) and a local arm64 image build passed. The Union rerun after the merge was skipped when the PR merged. There were no review comments.

Left:
- The community catalog's headers and infra's notebook docs: [[community-catalog-pixi-headers]].
- A non-editable SDK in notebook environments: [[release-task-images]].
- Offline, a notebook at a new path can't build its environment, and a prebuilt one opens after 48 s of retries.

Related: [[board]], [[pixi-dependencies]], [[marimo-sandbox]], [[local-notebook-images]], [[warm-uv-cache]], [[community-catalog-pixi-headers]].
