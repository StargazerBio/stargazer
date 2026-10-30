# Notebook Runtime

What runs in a notebook pod: one image holding the SDK, marimo, the bioinformatics tools and Claude Code, with a small proxy in front of marimo. The same image runs everywhere a notebook does. Locally `docker run` starts it on the notebooks it ships with; on a cluster a pod manager launches it once per notebook, signed in and saving to object storage. Stargazer's own pod manager is the hosted dashboard, kept in the infra repository; anything that keeps to [the pod contract](#the-pod-contract) can launch it.

For what the notebooks themselves are, see [Notebooks](notebook.md). For hydrate, save and the proxy's data path in detail, see the agent reference `.claude/reference/architecture/runtime_internals.md`.

## The Image

`runtime/Dockerfile` builds it, from the repository root. It holds:

- **The SDK's source at `/stargazer`.** Notebooks don't run in the image's Python: each notebook's PEP 723 header names `stargazer-bio` with `/stargazer` as its source, and marimo's sandbox builds the notebook a venv from that header when it opens. The built-in notebooks are under `/stargazer/src/stargazer/notebooks/`.
- **The runtime venv**: `flyte`, the launcher marimo (pinned, and put into every sandbox, so the kernel and the launcher are the same build) and the proxy's web packages.
- **The bioinformatics tools** (gatk, samtools, bwa, bwa-mem2), on every sandbox's path, so a notebook can run a tool on the pod's own data.
- **Claude Code**, pinned, for the terminal, with `/workspace/AGENTS.md` telling it where it is and how Stargazer notebooks, tasks and runs work.

The working directory is the flyte user's home, not `/workspace`: on a cluster Flyte unpacks the launching app's code into the working directory, and everything in `/workspace` is the user's.

**Run locally**, the image's entrypoint copies its notebooks into `/workspace` (a file already there is left alone, so a mounted directory keeps the user's edits) and opens the first tutorial in edit mode. Runs stay in the notebook's own process, with their records in SQLite. There's no sign-in and no store, so the proxy only forwards.

**Run on a cluster**, Flyte replaces the entrypoint with its own, which runs the launch command the pod manager gives it.

## Releases

Stargazer is released by calendar: the tag `v2026.10.28` is version `2026.10.28`, and a second release that day is `2026.10.28.1`. A release publishes the package to PyPI as `stargazer-bio` and the image to `ghcr.io/stargazerbio/stargazer` under the same tag (and `latest`), built from the same commit. So a pod manager pins one release and gets both halves, and a dashboard and the pods it launches agree on the asset keyvalues, the index and this contract.

## The Launch

A pod starts as `launch-notebook.sh <mode> <path>`: `edit` or `run`, and the notebook's path in the pod. It:

1. **Hydrates** the owner's workspace from the store into `/workspace`, when the pod has a store. A failure is logged and the pod starts with an empty workspace rather than not at all.
2. **Starts marimo** in `/workspace`, sandboxed, on a loopback port.
3. **Hands over to the proxy** on port 8080, as the same process, so the signal that stops the pod reaches the proxy and its last save runs. The launch command must start with `exec` for the same reason.

## The Proxy

`runtime/proxy.py` is the pod's public port. It imports no Stargazer code and runs in the runtime venv.

**It checks who's asking, when the pod has an issuer.** A cluster's login may sit in front of the pod, but an app's in-cluster address can skip it, so with `SG_AUTH_ISSUER` set every request must carry a token that issuer signed, for the owner or one of the admins: anyone else is turned away. Without an issuer (locally, the devbox) every request goes through.

**Notebook code never sees the visitor's credentials.** The login's cookies and identity headers are stripped before a request reaches marimo.

**Saving just works.** With a store (`STARGAZER_WORKSPACE_ROOT`), the proxy writes each changed file in `/workspace` back to the owner's workspace on an interval (`SG_SAVE_INTERVAL_SECONDS`, 30 by default, 0 for only at shutdown), deletes from the store what was deleted in the pod, and saves once more when the pod stops. A file deleted from the store while the pod holds it, as when its notebook is deleted from the dashboard, stays deleted: the pod doesn't save it back. Nor does a pod that starts after its notebook was deleted, or whose workspace failed to load, save the blank notebook it opens in its place. Dotfiles and Python's and marimo's caches aren't saved. A pod that dies without warning loses what changed since its last save.

**Big files belong in the asset store.** A file over 100 MB isn't saved with the workspace. A banner on the notebook page names it, with a cell that stores it as an asset instead, which has no size limit.

**A terminal rides along.** Every marimo page gets a dropdown terminal (Ctrl+`), a shell in `/workspace` with Claude Code on its path.

**It starts answering at once.** Until marimo is up, a browser gets a page that refreshes itself, and `/__sg__/ready` says when marimo answers. `/__sg__/dashboard` sends the browser to the pod manager's page.

## The Pod Contract

What a pod manager relies on from a release, and what it gives each pod. A change to any of it lands in a release and in the pod manager's pin bump together.

**The image and its command.** `ghcr.io/stargazerbio/stargazer:<tag>`, launched as `exec /usr/local/bin/launch-notebook.sh <mode> <path>` on port 8080. Built-in notebooks are under `/stargazer/src/stargazer/notebooks/`, the owner's at `/workspace/<file>`.

**The environment.** All optional: unset, the pod runs as it does locally.

| Variable | What it does |
|---|---|
| `SG_OWNER_SUBJECT` | The owner's subject: whose workspace the pod hydrates and saves, and who the gate lets in |
| `SG_ADMIN_SUBJECTS` | Comma-separated subjects the gate also lets in |
| `SG_AUTH_ISSUER` | The issuer whose signed token (`X-User-Token`) every request must carry; unset turns the gate off |
| `SG_SAVE_INTERVAL_SECONDS` | Seconds between saves; 0 saves only at shutdown |
| `STARGAZER_WORKSPACE_ROOT` | The workspace store's root; unset means nothing is hydrated or saved |
| `STARGAZER_ADMIN_URL` | Where `/__sg__/dashboard` sends the browser |
| `STARGAZER_INDEX_URL`, `STARGAZER_STORE_ROOT`, `STARGAZER_OWNER` | The owner's asset index and store, for the notebook and the runs it starts ([Configuration](configuration.md#environment-variables)) |
| `AWS_ROLE_ARN`, `AWS_WEB_IDENTITY_TOKEN_FILE` | The cloud role the pod, and every client in it, acts as: on Union the owner's, which reaches their files and index and no one else's ([Configuration](configuration.md)) |
| `STARGAZER_API_KEY_SECRET` | The secret holding the project's API key, which every task environment then declares ([Configuration](configuration.md#environment-variables)) |
| `STARGAZER_NOTEBOOK_IMAGE` | The image the pod runs, which `notebook_base` builds a notebook's declared image on ([Notebooks](notebook.md#notebook-environment)) |

**The workspace store's layout.** One object per file, at its path under `<STARGAZER_WORKSPACE_ROOT>/users/<subject>/workspace/`. The pod manager reads and writes the same objects, and nothing else coordinates the two, so the layout is part of the contract. A pod never writes back a file it hydrated or saved that the store no longer has, and one launched on a workspace notebook that isn't in the store when it starts opens it blank and never saves it, so the pod manager can delete a notebook from the store while its pod is still up or starting.

**The asset keyvalues and the index** are the package's: a pod manager that lists or uploads assets does it through the same release's `stargazer.utils` and `build_asset()`, so it accepts exactly what the SDK does ([Types → Serialization](types.md#serialization)).
