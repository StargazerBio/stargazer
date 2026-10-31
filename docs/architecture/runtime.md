# Notebook Runtime

What runs in a notebook pod: one image holding the SDK, marimo, the bioinformatics tools and the agents (Claude Code and OpenCode), with a small proxy in front of marimo. The same image runs everywhere a notebook does. Locally `docker run` starts it on the notebooks it ships with; on a cluster a pod manager launches it once per notebook, signed in and saving to object storage. Stargazer's own pod manager is the hosted dashboard, kept in the infra repository; anything that keeps to [the pod contract](#the-pod-contract) can launch it.

For what the notebooks themselves are, see [Notebooks](notebook.md). The launch, signal and save protocols are in the agent reference `.claude/reference/architecture/runtime_internals.md`.

## The Image

`runtime/Dockerfile` builds it, from the repository root. It holds:

- **The SDK's source at `/stargazer`.** Notebooks don't run in the image's Python: each notebook's PEP 723 header names `stargazer-bio` with `/stargazer` as its source, and marimo's sandbox builds the notebook a venv from that header when it opens. The built-in notebooks are under `/stargazer/src/stargazer/notebooks/`.
- **The runtime venv**: `flyte`, the launcher marimo (pinned, and put into every sandbox, so the kernel and the launcher are the same build), `pydantic-ai-slim` with the OpenAI and Anthropic providers for marimo's AI chat and completions, and the proxy's web packages.
- **The bioinformatics tools** (gatk, samtools, bwa, bwa-mem2), on every sandbox's path, so a notebook can run a tool on the pod's own data.
- **Claude Code and OpenCode**, pinned, for marimo's agent panel, with `/workspace/AGENTS.md` telling them where they are and how Stargazer notebooks, tasks and runs work. marimo's user config turns the panel on.

**Run locally**, the image's entrypoint copies its notebooks into `/workspace` (a file already there is left alone, so a mounted directory keeps the user's edits) and opens the first tutorial in edit mode. Runs stay in the notebook's own process, with their records in SQLite. There's no sign-in and no store, so the proxy only forwards.

**Run on a cluster**, Flyte replaces the entrypoint with its own, which runs the launch command the pod manager gives it.

## Releases

Stargazer is released by calendar: the tag `v2026.10.28` is version `2026.10.28`, and a second release that day is `2026.10.28.1`. A release publishes the package to PyPI as `stargazer-bio` and the image to `ghcr.io/stargazerbio/stargazer` under the same tag (and `latest`), built from the same commit. So a pod manager pins one release and gets both halves, and a dashboard and the pods it launches agree on the asset keyvalues, the index and this contract.

## The Launch

A pod starts as `launch-notebook.sh <mode> <path>`: `edit` or `run`, and the notebook's path in the pod. It hydrates the owner's workspace from the store into `/workspace` and their agent sign-ins into the home directory (a failure starts the pod empty rather than not at all), starts marimo there in a sandbox on a loopback port (watching the notebook's file in edit mode, so an agent's edits reach the editor), and hands over to the proxy on port 8080. The launch command must start with `exec` so the signal that stops the pod reaches the proxy and its last save runs.

## The Proxy

`runtime/proxy.py` is the pod's public port. It imports no Stargazer code and runs in the runtime venv.

- **Auth.** With `SG_AUTH_ISSUER` set, every request must carry a token that issuer signed, for the owner or an admin, because an app's in-cluster address can skip the cluster's login. Without an issuer (locally, the devbox) every request goes through. The login's cookies and identity headers are stripped before a request reaches marimo, so notebook code never sees the visitor's credentials.
- **Saving.** With a store (`STARGAZER_WORKSPACE_ROOT`), the proxy writes each changed file in `/workspace` back to the owner's workspace every `SG_SAVE_INTERVAL_SECONDS` (30 by default, 0 for only at shutdown), mirrors deletes, and saves once more when the pod stops. A pod that dies without warning loses what changed since its last save. A notebook deleted from the dashboard stays deleted, and a pod whose notebook didn't load shows a banner instead of saving a blank one. The agents' sign-ins are saved the same way, beside the workspace, so a user signs in once and a sign-out lasts.
- **Big files.** A file over 100 MB isn't saved; a banner names it, with a cell that stores it as an asset instead.
- **The agents.** marimo's agent panel reaches each agent at a fixed port on the page's host, which a hosted pod doesn't serve, so a script the proxy adds to each page points Claude Code's and OpenCode's at `/__sg__/agent/<name>`, where the proxy runs that agent's Agent Client Protocol server for each connection, behind the same sign-in. The agents get the pod's env without its secrets. The terminal is marimo's own, in edit mode.
- **Starting.** Until marimo is up, a browser gets a self-refreshing page; `/__sg__/ready` says when marimo answers, and `/__sg__/dashboard` sends the browser to the pod manager's page.

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

**The workspace store's layout.** One object per file, at its path under `<STARGAZER_WORKSPACE_ROOT>/users/<subject>/workspace/`. The agents' sign-ins are under `users/<subject>/agents/`, at their paths in the home directory, which only the pod reads and writes. The pod manager reads and writes the same objects, and nothing else coordinates the two, so the layout is part of the contract. A pod never writes back a file it hydrated or saved that the store no longer has, and one launched on a workspace notebook that isn't in the store when it starts opens it blank and never saves it, so the pod manager can delete a notebook from the store while its pod is still up or starting.

**The asset keyvalues and the index** are the package's: a pod manager that lists or uploads assets does it through the same release's `stargazer.utils` and `build_asset()`, so it accepts exactly what the SDK does ([Types](types.md)).
