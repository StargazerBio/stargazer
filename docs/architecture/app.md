# App: Hosted Dashboard + Per-User Notebooks

The `app/` directory is **deployment glue**: FastAPI, Flyte AppEnvironment definitions, the workspace store. It lives outside `src/stargazer/` because it is not invokable by tasks or workflows; the SDK stays importable in environments without FastAPI or a Flyte control plane connection.

This doc is the high-level map of the hosting tier. For what the dashboard's notebook sections *mean* (taxonomy, archetypes, promotion paths), see [Notebooks](notebook.md). For implementation-level detail (identity headers, route table, pod launch, hydrate and sync mechanics), see the agent reference `.opencode/reference/architecture/app_internals.md`.

Two kinds of Flyte `AppEnvironment` are defined here, and both sit behind the platform's login (`requires_auth=True`):

- **`app_env`** (the dashboard) — one per user, deployed into that user's own Flyte project. Renders their notebooks, keeps them in the workspace store, and launches notebook apps. It is keyed to its owner, and the platform alone decides who may open it.
- **Per-notebook envs** — built by the `per_notebook_env()` factory (`app/per_notebook.py`), one `nb-{slug}-{mode}` env per launch, deployed into the same project and owned by the same user.

A third piece runs outside the platform: **onboarding** (`app/onboard.py`, the `stargazer-users` command), which an org admin runs from their own machine to give a user their project, access and dashboard.

## Topology

```mermaid
flowchart LR
    ADM([Org admin]) -->|stargazer-users onboard| FCP[(Flyte control plane)]
    FCP -->|creates| PR[project u-HANDLE<br/>+ access grant]
    FCP -->|deploys| D[dashboard<br/>app_env]
    U([User browser]) -->|platform login| D
    D -->|read / write notebooks| S[(workspace store<br/>object storage)]
    D -->|/launch per tile click| FCP
    FCP -->|deploys| N[nb-SLUG-MODE pod]
    U -->|browser tab, platform login| N
    N -->|hydrate at start, save changes| S
    D -.-> PR
    N -.-> PR
```

Each user has one project holding their dashboard and their notebook pods, and nothing else. Pods are spawned lazily when a tile's Edit/Run button is clicked. The dashboard never calls a pod: each pod loads and saves its owner's notebooks itself.

## Request Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant P as Platform login
    participant D as Dashboard
    participant S as Workspace store
    participant F as Flyte CP
    participant N as Notebook pod

    B->>P: GET dashboard URL
    P-->>B: sign in (first visit only)
    P->>D: GET / + signed-in user
    D->>S: list the owner's notebooks
    D-->>B: dashboard
    B->>D: POST /launch (tile click)
    D->>F: serve nb-slug-mode in the dashboard's project
    D-->>B: notebook URL (open in tab)
    B->>P: GET notebook URL
    P->>N: request + signed-in user
    N->>S: hydrate the owner's workspace
    N-->>B: starting page, then marimo
```

## Core Concepts

**The platform owns sign-in.** There is no login page, OAuth flow or session cookie in the app tier. The platform gates every request to both app kinds and forwards the signed-in user's stable id (the *subject*) plus display claims. It overwrites any client-sent copy, so the identity can't be forged. The subject keys everything per-user: the workspace store prefix, the `_owner` stamped on assets, and the label that ties a user to their project.

**One project per user.** The platform admits a signed-in user to an app only if they can view the app's project, and anyone who can view a project sees every app in it. So each user gets their own project, `u-<handle>`, with access to that project and nothing else. Their dashboard and notebooks live there, and in the platform console they see only their own work. The project id is readable (from their email by default) and permanent; the subject on its label is what onboarding looks it up by.

**The platform is the only access control.** The app tier adds no ownership check of its own. Whoever the platform admits to a project (its user, or an org admin) can open that project's dashboard and notebooks. A dashboard knows its owner from its deploy and keys its state by that owner, not by the visitor, so an admin sees the owner's notebooks.

**Onboarding is an admin step.** New users need an invite to the org anyway, so the same command does the rest: invite (or find) the user, create their project, grant them access to it, and deploy their dashboard at a stable, bookmarkable address. Running it again only redeploys. Nothing that runs on the platform needs the right to create projects or grant access, and no privileged credential is deployed anywhere. Releasing a new version redeploys every user's dashboard from the same images, each deployed under the commit it came from, so the platform console shows what every dashboard runs. A release needs no admin rights, so it can also run under an API key; offboarding stops a user's apps, removes their access and archives their project, and leaves their notebooks in the store.

**Notebook pods are gated by the platform too.** Each pod is baked with its owner's subject, which only keys where it loads and saves notebooks. Platform cookies and identity headers are stripped before a request reaches the notebook, so notebook code never sees a visitor's platform token through a request.

**Users are separated by Flyte project boundaries**, not by varying the env definition. Every per-notebook env is served into the user's project, so each user's runs, apps and cache stay in their own project, and their files sit under their own prefix in the store. The factory is parameterized by notebook (slug, mode, path, resources) and owner, so which project the env lands in is what separates users. **Storage isn't isolated yet:** every project runs as the same cloud role, so code in one user's notebook could read another user's objects. That stays soft until it needs hardening (a bucket and role per user, ticket `per-user-storage-isolation`); meanwhile the dashboard and the asset upload form carry an alpha notice asking users not to upload sensitive data.

**Saving just works.** A user's workspace lives in the workspace store: object storage, one object per file at its path, under the user's subject. Notebooks are files like any other, and so is whatever the user keeps beside them: data, helper modules, outputs. There's no opt-in and no setup. The store is the durable copy and pods are working copies. A pod loads its owner's whole workspace when it starts and writes changed files back every 5 seconds. A file deleted in the pod is deleted from the store. The pod does a final save when it scales to zero. A pod that dies without warning loses what changed since its last save. Each pod writes only the files it changed, so two running notebooks overwrite each other's work only when both change the same file. Dotfiles and Python's and marimo's caches aren't saved.

**Big files belong in the asset store.** A file over 100 MB isn't saved with the workspace. It stays on the pod's disk until the pod stops, and the notebook page names it, with a cell that stores it as an asset straight from the pod, which has no size limit. The limit matches the asset page's upload limit, and it keeps the final save small enough to finish before the pod is killed.

**Sharing upstream is a download.** Any workspace notebook can be downloaded as its `.py` file and contributed to the repository like any other change. The app tier has no GitHub integration.

**Resources live in the notebook.** A workspace notebook's `[tool.stargazer]` header (cpu/memory) is parsed textually at launch (no code execution) and honored as-authored, with no ceiling. Image-baked notebooks carry no header and fall back to the env default.

**So does the image.** A workspace notebook can declare the image its pod runs on as `main_img` in its setup block ([Notebooks → Notebook Environment](notebook.md#notebook-environment)). At launch the dashboard evaluates just that expression and hands the resulting image to the SDK's `serve`, which builds it on Union's remote builder in the user's own project (or finds it already built) before deploying the notebook on it. It's the one piece of notebook code the dashboard runs: the owner's, in the owner's own dashboard. The dashboard's one secret is the org's Pinata key, which any of the owner's tasks can read anyway.

**Tiles are stateful and authoritative.** On load the dashboard asks the control plane which `nb-{slug}-{mode}` apps are live and hydrates those tiles to Open/Stop; a notebook runs in edit *or* run mode, never both. Discovery is a single project-scoped deployment list, re-checked per app for authoritative status. This is read from Flyte rather than in-memory state, so it survives dashboard restarts.

**The tier is lightweight by construction.** Dashboard responses are gzip-compressed, and the notebook proxy streams everything except the HTML pages it decorates, so large notebook assets never sit in proxy memory. Details in `.opencode/reference/architecture/app_internals.md`.

## Asset Index

Each dashboard also holds its user's **asset index**: the metadata behind `assemble()` for every file the user's tasks and notebooks store. It is a SQLite file on the dashboard's own disk. The user's notebook pods, and the task pods their runs start, reach it at the dashboard's in-cluster address (`http://dashboard.<project>-<domain>.svc.cluster.local`), which needs no login. The files themselves go straight to the bucket, under the same root as the user's notebooks; only one small row per asset passes through the dashboard.

The dashboard can scale to zero, so its disk isn't durable. Litestream copies every change to the bucket, at `<root>/users/<subject>/index`. At startup the dashboard restores the file before serving; at scale-to-zero it syncs one last time after the web server stops. Redeploying a dashboard briefly runs the old and new versions side by side, and a write the old one accepts after the new one has restored would be lost, so a dashboard isn't redeployed while its owner has runs going. `stargazer-users upgrade` goes one user at a time and comes back for busy users until every dashboard is done; one user's runs never hold up another's.

See [Configuration](configuration.md) for the storage model and `.opencode/reference/architecture/app_internals.md` for the mechanics.

## Asset Manager

The dashboard also hosts `/assets` — a browse-and-upload surface with two
tabs. Routes live in `app/assets.py`; mechanics and the route table are in
`.opencode/reference/architecture/app_internals.md`.

**Private is the user's own index and store**, the same ones their tasks
and notebooks write to, so the tab shows everything they've stored. Uploads
stream through the dashboard into the store, which works out the CID and
writes the index row, and downloads stream back out. Only the dashboard's
owner reaches them. It works on every dashboard, with or without a Pinata
key.

**Public is Pinata's public network**, called directly. The dashboard gets
the org's Pinata key as a Flyte secret: Union injects it into the pod and
keeps only a reference in the app's spec, so the user who owns the dashboard
can't read it there. Pinata's private network is never used: the key is
shared across the org, and anyone who can run a task can reach it, so it
would keep nothing private. The devbox drops app secrets, so a devbox
dashboard's Public tab says shared data isn't available.

**Public uploads never transit the dashboard pod.** The page validates metadata and
mints a Pinata **signed upload URL** (`POST /assets/sign`); the browser then
PUTs bytes straight to Pinata. Because Pinata bakes the filename and
keyvalues into the URL at mint time, the uploader can supply bytes only —
never metadata the server didn't validate. Validation is the *same*
`build_asset()` choke point the MCP server uses, so the page and the SDK
agree on what a valid upload is. **A registered type's form takes extra
fields** below its declared ones, stored as text on the typed asset (see
[Types → Extra keys](types.md#extra-keys)); an upload with more fields than
a Pinata file holds is refused before the URL is minted. Public downloads redirect the same way: bytes go
browser↔Pinata, not through the pod. Private uploads use the same validation
before the dashboard reads any of the file.

**Ownership is server-stamped attribution, not enforcement.** Every hosted
write path stamps an `_owner` keyvalue (the user's subject) — the page from the signed-in user at sign
time, workspace SDK/MCP uploads from a launcher-injected `STARGAZER_OWNER`,
pipeline outputs from that var forwarded into task pods. Users never type
it (`_`-prefixed keys are a reserved namespace `build_asset()` rejects). So
an unowned record on the hosted deployment is legacy data or a bug, never
expected. Because the Pinata key is shared, this is attribution only — it
drives default filtering, not access control; anyone holding the key can
still edit or delete any record. See [Types → Ownership](types.md#ownership-_owner).

**Reading public data needs no ownership.** Public-network bytes are world-readable on
IPFS, and a local run serves the page anonymously. The listing is served
from a short in-process TTL cache (a semi-static mirror, not a per-request
proxy to the Pinata API), and every download, anonymous or not, redirects to
`PINATA_GATEWAY`, the account's dedicated gateway, which meters bandwidth.
Free public gateways rate-limit full downloads, and `dweb.link` no longer
serves files. `_owner` is stamped on uploads as a publisher byline. Rate
limiting of the anonymous surface is deferred.

**The page lives in the dashboard's box.** `assets.html` renders in the same
glassy card as the notebook dashboard (reached from the avatar menu's
**Assets** link), and the reactive starfield background is left untouched —
the asset graph is a separate foreground canvas. The browse surface offers two
interchangeable renderings of the same listing, switched by a Graph/List
toggle (Graph is the default):

- **Graph** draws assets as nodes and their links as edges: `companion_of`,
  and the `*_cid` provenance links (`reference_cid`, `mate_cid`,
  `alignment_cid`, …) — a foreground
  constellation echoing the background field. Hovering a node peeks its
  metadata; clicking pins a detail card with the full metadata, its linked
  assets, and a download button. It's rendered with **Cytoscape.js** (vendored,
  no build step), so it's interactive: scroll to zoom, drag to pan, drag a node
  to reposition it, double-click to reset, capped at 150 nodes. Links to assets
  outside the current view (on the other tab, or filtered out) aren't drawn but
  are listed on the card, so provenance is never hidden. On a record the signed-in user owns, the card also
  offers **Edit metadata** — an in-place fix for a mis-tagged record that
  merges the change (the CID is unchanged, so provenance edges survive). The
  edit route fail-closes on ownership server-side; the same fix is available
  via the MCP `update_file` tool.
- **List** is the same records as a sortable table (CID, name, owner, type,
  metadata, download). The upload panel below is schema-driven — pick a
  registered type or a bare/custom asset, fill metadata, choose Private or
  Public — and the upload appears in the listing straight away, before
  Pinata's listing catches up on a public one.

## Images

The dashboard and the per-notebook pods use **different images by design**:

- `app_env.image` is Flyte-built via `with_uv_project` — the dashboard is small Python with no heavy deps.
- Per-notebook envs use the programmatically-defined `notebook-app` image. Onboarding builds it and hands each dashboard the exact build, so every notebook pod runs the image that shipped with its dashboard and the dashboard pod (no Docker daemon) never rebuilds it. A notebook that declares its own image runs on a build layered on that one, which `serve` builds on Union's remote builder; that needs only the Flyte API, no Docker.

Both images are content-hashed, so a release builds each once however many users it deploys, and every user's dashboard runs the same build.

## Deploy Targets

One switch, `STARGAZER_TARGET`, picks the backend: `devbox` (the default, a local cluster for lightweight testing) or `union` (the hosted tenant). The app tier is built around the platform's login, which the devbox doesn't have, so the devbox gets one dashboard for a stand-in user instead of per-user onboarding: enough to test the asset index, asset storage and the dashboard locally. The stand-in is never honored on Union. Setup and rationale are in `.opencode/reference/devbox_workarounds.md`. It selects the deployer's Flyte config and where images are pushed. The Flyte domain is set separately, so the same target can serve a development or a production deployment. The per-target table is in `.opencode/reference/architecture/app_internals.md`.

The project `Dockerfile`'s `stargazer` is the hosted notebook image's recipe as a local `docker run`, defined separately in the `Dockerfile`; it is not the hosted build. Build/publish detail in `.opencode/reference/architecture/app_internals.md`.
