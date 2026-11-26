# Notebook Runtime

What runs in a notebook pod: one image holding the SDK, marimo and the agents (Claude Code and OpenCode), with a small proxy in front of marimo. The same image runs everywhere a notebook does. Locally `docker run` starts it on the notebooks it ships with; on a cluster a pod manager launches it once per notebook, signed in, with the notebook's own volume mounted. Stargazer's own pod manager is the hosted dashboard, kept in the infra repository; anything that keeps to [the pod contract](#the-pod-contract) can launch it.

For what the notebooks themselves are, see [Notebooks](notebook.md). The launch, signal and save protocols are documented where they're implemented: the volume, saving and the `/__sg__/*` endpoints in `runtime/proxy.py`, the signal chain in `runtime/launch-notebook.sh`, the working directory and `AGENTS.md` seeding in `runtime/Dockerfile`.

## The Image

`runtime/Dockerfile` builds it, from the repository root. It holds:

- **The SDK's source at `/stargazer`.** Notebooks don't run in the image's Python: each notebook's PEP 723 header installs `stargazer-bio` from `/stargazer` as a package, not editable, and marimo's pixi sandbox builds the notebook an environment from that header when it opens, conda packages and PyPI ones. So a notebook's kernel runs the image's release, the SDK's tasks on images built from their domains' headers with that release on top, and a notebook's own tasks on an image built from its header. The built-in notebooks are under `/stargazer/src/stargazer/notebooks/`.
- **pixi**, which builds those environments, newer than the pixi Flyte's image builder uses, since marimo needs its `install --script`.
- **A warm cache** at `/opt/pixi-cache` and `/opt/uv-cache`: the built-in notebooks' packages, each domain's packages and tools (in the `amd64` image), and the marimo layer marimo puts over the server. A notebook's environment is built from it where the notebook is opened, tutorials included, so it downloads only what its header adds. How the cache is built and kept matching is commented in `runtime/Dockerfile`.
- **The runtime venv**: `flyte` and its volume plugin `flyteplugins-union`, the launcher marimo (pinned, and put into every sandbox, so the kernel and the launcher are the same build), `pydantic-ai-slim` with the OpenAI and Anthropic providers for marimo's AI chat and completions, and the proxy's web packages.
- **No bioinformatics tools installed.** A task run on the cluster gets its tools from its own environment's image. A notebook that runs a tool in its own process, in a cell or in a task run on its own machine, declares it in its header ([Notebook Environment](notebook.md#notebook-environment)).
- **Claude Code and OpenCode**, pinned, for marimo's agent panel, with `/workspace/AGENTS.md` telling them where they are and how Stargazer notebooks, tasks and runs work. marimo's user config turns the panel on, and OpenCode's gives an MCP request an hour, since a run's tools answer when the run ends.
- **The [MCP server](mcp-server.md)** in a venv of its own, built from the lock and installed from `/stargazer`, for the agents in the panel.

### Where a notebook's packages come from

A notebook's header is the only thing that says what it runs on. When it opens, its environment is built from that header, and each package comes from the nearest of three places:

1. **The release's SDK, in the image.** `stargazer-bio` is installed from `/stargazer`, so the SDK is never downloaded and always matches the image.
2. **The warm cache.** The packages the built-in notebooks list, and each domain's (GATK and its tools, scanpy) in the `amd64` image, are already on disk. Building an environment from them is a copy and a link, with nothing fetched.
3. **The network.** Anything else a header lists, including a package a user installs from marimo's interface, is fetched when the environment is built. marimo adds an installed package to the header, so it's fetched again whenever that notebook's environment is rebuilt, for example on a new pod.

No environment is prebuilt, tutorials included, because a header can change at any time: an environment kept for a header would serve only a notebook nobody has edited, at the one path it was built for. The cache holds packages, so a header that adds one package to a cached set still downloads only that one. A new domain's packages join the cache through its `env.py` header, and the notebooks themselves never grow the image.

**Run locally**, the image's entrypoint copies its notebooks into `/workspace` (a file already there is left alone, so a mounted directory keeps the user's edits) and opens the first tutorial in edit mode. Runs stay in the notebook's own process, with their records in SQLite. There's no sign-in, no volume and no store, so the proxy only forwards.

**Run on a cluster**, Flyte replaces the entrypoint with its own, which runs the launch command the pod manager gives it.

## Releases

Stargazer is released by calendar: the tag `v2026.10.28` is version `2026.10.28`, and a second release that day is `2026.10.28.1`. Merging a version bump to `main` tags it and publishes the package to PyPI as `stargazer-bio` and the image to `ghcr.io/stargazerbio/stargazer` under the same tag (and `latest`), built from the same commit. So a pod manager pins one release and gets both halves, and a dashboard and the pods it launches agree on the asset keyvalues, the index and this contract.

## The Launch

A pod starts as `launch-notebook.sh <mode> <path>`: `edit` or `run`, and the notebook's path in the pod. It puts the owner's agent sign-ins back in the home directory (a failure starts the pod without them rather than not at all), starts the MCP server in edit mode over HTTP on a loopback port, with the pod's whole env so it can start runs in the owner's project, and hands over to the proxy on port 8080, whose startup mounts the notebook's volume. marimo starts in the background once the notebook's file exists, which for a workspace notebook is when the mount is up. Before it does, the launch pins Python in the notebook's header to the image's Python version when the header pins none, since pixi would otherwise install the newest Python, and copies a header's `[tool.uv.sources]` path for `stargazer-bio` to the table pixi reads, so a notebook saved with one runs the image's SDK. marimo then starts in a sandbox on a loopback port, in the notebook's folder, watching the notebook's file in edit mode so an agent's edits reach the editor. The launch command must start with `exec` so the signal that stops the pod reaches the proxy and its last commit runs.

## The Proxy

`runtime/proxy.py` is the pod's public port. It imports no Stargazer code and runs in the runtime venv.

- **Auth.** With `SG_AUTH_ISSUER` set, every request must carry a token that issuer signed, for the owner or an admin, because an app's in-cluster address can skip the cluster's login. Without an issuer (locally, the devbox) every request goes through. The login's cookies and identity headers are stripped before a request reaches marimo, so notebook code never sees the visitor's credentials.
- **The volume.** With `SG_NOTEBOOK_MANIFEST`, the proxy's startup reads the notebook's manifest and mounts its volume at the notebook's folder before marimo starts. In edit mode it forks the latest version and mounts the fork read-write. Every `SG_SAVE_INTERVAL_SECONDS` (30 by default, 0 for only at shutdown) it commits a new version if a file changed since the last commit, and writes the manifest to name it. When the pod stops it finalizes the volume, which commits and unmounts, and writes the manifest once more; if nothing changed since the last commit it abandons the volume instead, so a session that only looked at a notebook adds no version. A pod that dies without warning loses what changed since its last commit. In run mode it mounts a throwaway fork of the latest version read-write, since the launch's header fixes and marimo's session caches write beside the notebook. It never commits or writes the manifest, and its edits, the caches included, are thrown away when the pod stops. The proxy holds the mount because the process that mounts is the one that commits. Without a manifest nothing is mounted, and the notebook is a plain file, as locally.
- **A refused manifest write.** The manifest is written only if it is still the version the pod last read or wrote. If the dashboard or another pod wrote it since, the write is refused: the pod stops writing the manifest for the rest of its life, keeps committing so every version exists, logs each by locator, and the page shows a banner saying changes made there no longer save to the notebook.
- **Sign-ins.** The agents' sign-ins are saved to the store under the owner's `agents/` prefix, which every pod of the user shares, on the same interval and at shutdown, so a user signs in once and a sign-out lasts.
- **Big files.** The volume holds any size a notebook writes, so there is no cap and no banner. Data worth sharing is still better stored as an asset.
- **The agents.** marimo's agent panel reaches each agent at a fixed port on the page's host, which a hosted pod doesn't serve, so a script the proxy adds to each page points Claude Code's and OpenCode's at `/__sg__/agent/<name>`, where the proxy runs that agent's Agent Client Protocol server for each connection, behind the same sign-in. The agents get the pod's env without its secrets. marimo opens each session with no MCP servers, so the proxy adds the pod's MCP server to every session request before it reaches the agent. The terminal is marimo's own, in edit mode.
- **Long-lived connections.** The platform cuts every request to the pod at its request timeout, and counts an open websocket as one request. Only the browser's connection to the proxy is cut, so the proxy keeps each socket's other end (marimo's socket, an agent process) apart from the connection carrying it, and the same script hands each of the page's sockets over to a new connection every 19 minutes, inside the 20-minute timeout the pod contract asks for. The proxy moves the socket once it has every frame the page sent on the old connection, then closes the old one, so nothing is lost or reordered, and the editor's session, its terminal and the agent panel stay up for as long as the page is open. A connection the network drops still closes, as it did.
- **Starting.** Until marimo is up, a browser gets a self-refreshing page; `/__sg__/ready` says when marimo answers, and `/__sg__/dashboard` sends the browser to the pod manager's page.

## The Pod Contract

What a pod manager relies on from a release, and what it gives each pod. A change to any of it lands in a release and in the pod manager's pin bump together.

**The image and its command.** `ghcr.io/stargazerbio/stargazer:<tag>`, launched as `exec /usr/local/bin/launch-notebook.sh <mode> <path>` on port 8080, with a request timeout of at least 20 minutes: the page hands its sockets over every 19, so a shorter one cuts them first. Built-in notebooks are under `/stargazer/src/stargazer/notebooks/`, a workspace notebook at `/workspace/<slug>/<file>`, its own volume's mount.

**The environment.** All optional: unset, the pod runs as it does locally.

| Variable | What it does |
|---|---|
| `SG_OWNER_SUBJECT` | The owner's subject: whose sign-ins the pod keeps, and who the gate lets in |
| `SG_ADMIN_SUBJECTS` | Comma-separated subjects the gate also lets in |
| `SG_AUTH_ISSUER` | The issuer whose signed token (`X-User-Token`) every request must carry; unset turns the gate off |
| `SG_NOTEBOOK_MANIFEST` | The URI of a workspace notebook's manifest; unset mounts no volume |
| `SG_SAVE_INTERVAL_SECONDS` | Seconds between commits of the notebook's volume and saves of the sign-ins; 0 saves only at shutdown |
| `STARGAZER_WORKSPACE_ROOT` | The workspace store's root, where the owner's sign-ins are kept; unset means none are |
| `STARGAZER_ADMIN_URL` | Where `/__sg__/dashboard` sends the browser |
| `STARGAZER_INDEX_URL`, `STARGAZER_STORE_ROOT`, `STARGAZER_OWNER` | The owner's asset index and store, for the notebook and the runs it starts ([Configuration](configuration.md#environment-variables)) |
| `AWS_ROLE_ARN`, `AWS_WEB_IDENTITY_TOKEN_FILE` | The cloud role the pod, and every client in it, acts as: on Union the owner's, which reaches their files and index and no one else's ([Configuration](configuration.md)) |
| `STARGAZER_API_KEY_SECRET` | The secret holding the project's API key, which every task environment then declares ([Configuration](configuration.md#environment-variables)) |
| `STARGAZER_NOTEBOOK_IMAGE` | The image the pod runs, which `notebook_base` builds a notebook's declared image on ([Notebooks](notebook.md#notebook-environment)) |

**A workspace notebook's manifest and volume.** A notebook is its own volume, and one small object names its latest version: the manifest, at `<STARGAZER_WORKSPACE_ROOT>/users/<subject>/notebooks/<slug>.json`, holding the latest version's `locator`, the notebook's `file` name and that file's text as `source`. The dashboard's tiles, download, publish and launch read the manifest and never mount a volume. A volume is named `vol-<subject>-<8 hex>`, in the workspace root's bucket, with its version metadata under `<root>/users/<subject>/volumes`, so each user's role can write only their own. The pod gets the manifest's URI as `SG_NOTEBOOK_MANIFEST` and the notebook at `/workspace/<slug>/<file>`: it mounts the volume at `/workspace/<slug>`, which must not exist beforehand, since the mount is a link made there. `/workspace/AGENTS.md`, the agents' context, stays in the parent.

Who writes when: a pod in edit mode writes the manifest only while it has the notebook, after each commit (a run-mode pod mounts a throwaway fork and writes nothing, and its edits are discarded), and the dashboard only while no pod has it (to create, copy or edit the notebook's settings, which forks the latest version, writes and finalizes a new one, or to delete it). Every write is conditional on the ETag the writer last read or wrote (`If-None-Match: *` for a new notebook's), so a refused write means someone else wrote, and the refused writer stops and says so. Its versions stay reachable by locator. Every version is kept.

The agents' sign-ins are separate objects under `users/<subject>/agents/`, at their paths in the home directory, which only the pod reads and writes.

**The asset keyvalues and the index** are the package's: a pod manager that lists or uploads assets does it through the same release's `stargazer.utils` and `build_asset()`, so it accepts exactly what the SDK does ([Types](types.md)).
