# App Tier — Internals (agent reference)

Deep, implementation-level detail for the `app/` deployment tier. This is the verbose companion to the human-facing [docs/architecture/app.md](../../../docs/architecture/app.md) — it carries the cross-cutting protocol detail (identity, the workspace store, pod lifecycle, hydrate and save) that spans several modules and so belongs to no single module docstring. When you change auth, storage, pod launch, or workspace sync, read this first and update it after.

Module-local behavior lives in each module's own docstring (`spec:`-linked back to the architecture doc); this file is only for the multi-module protocols.

## Identity (Union auth)

Both app kinds run `requires_auth=True`. Union's ingress gates every request on its login (an anonymous request gets a 302 to the tenant sign-in page) and forwards the signed-in user as headers it sets itself, **overwriting any client-sent value** (measured on the tenant):

| Header | Value | Used for |
|---|---|---|
| `X-User-Subject` | stable Union user id, bare (e.g. `387300641116005877`) | every per-user key |
| `X-User-Claim-Email`, `X-User-Claim-Name` | JSON-encoded strings (`"\"a@b.c\""`) | display only |
| `X-User-Token` | `IDToken <JWT>` | unused; stripped by the proxy |

No GitHub login, id or token is forwarded. The browser's Union session cookies (`flyte_idt`, `flyte_at_*`, `flyte_user_info`) also reach the pod.

`app/identity.py` parses these: `user_from_request` returns a `User(subject, email, name)` or None, and the `CurrentUser` route dependency 401s without a subject (only possible in a local run or a deploy with auth off). Everything per-user derives from the subject:

- Flyte project: `u-<subject>` (`app.provision.project_id`)
- workspace store prefix: `<root>/users/<subject>/`
- `_owner` on assets: the subject (an email would leak into public bylines)

**Union's gate needs view permission on the app's project.** A signed-in org member with no role on the project gets 403; with `viewer` they get in. Org membership alone isn't enough, so the admin's project needs a grant per user, and so does each user's own project for their notebook pods. Gate decisions are cached per browser session for several minutes. (Measured 2026-10-06; this is what plan 26 restructures around.)

**Bearer tokens work too.** A request with `Authorization: Bearer <access token>` passes the gate as that user, which is how a second identity can be exercised from the CLI.

## Project Provisioning

There's no login callback, so the admin ensures the user's project on their first request to the process (`provision.provision_user`, remembered in an in-memory set; a failure isn't remembered and retries next request). A failure renders the dashboard with a "still being set up" notice and makes `/launch` answer 503.

**On Union this cannot succeed.** App and task pods authenticate as the org's platform key (`stargazerbio-EAGER_API_KEY-union-us-west-2`, application subject `393067446845621194`), which holds org-wide `contributor`. Creating a project needs `action_administer_project`, which only `admin` has. Measured from a task pod on 2026-10-06: `Project.create` is refused with *"Identity [application_id:{subject:"393067446845621194"}] is not permitted to perform action [action_administer_project]"*. Projects therefore have to be created by an org admin outside the app (plan 26's onboarding command).

## Ownership Check (notebook pods)

Union only proves the visitor is an org member who can view the project. The proxy (`app/proxy.py`, `_is_owner`) compares `X-User-Subject` with `SG_OWNER_SUBJECT`, baked into the pod's env at launch, and returns a plain-text `403 Forbidden` to everyone else, on HTTP and websockets alike. An unset owner denies everyone. Before forwarding to marimo it strips `Host`, `Cookie` and every `X-User-*` header (`_forwardable`), so notebook code never sees a visitor's Union token through a request.

Measured on the tenant (2026-10-06): the org admin, who can view every project, got `403 Forbidden` from the proxy on another user's notebook URL, while the same token loaded the shared admin.

**Residual risk.** Code in a pod can still read anything in the pod, and the cookies do reach the pod's proxy process. A malicious owner could serve code that captures a visiting member's token before the strip. On the ROADMAP.

## The Workspace Store

`app/workspace_store.py` owns the layout; no route composes a URI by hand.

```
<STARGAZER_WORKSPACE_ROOT>/users/<subject>/notebooks/<slug>.py
<STARGAZER_WORKSPACE_ROOT>/users/<subject>/snapshots/<slug>.py
```

One object per notebook, so the dashboard can list a user's notebooks and read one header without fetching the rest. Subjects must match `[A-Za-z0-9_-]+` and filenames one plain `.py` segment, so a key can't escape its prefix. Create refuses to overwrite (`NotebookExistsError` → the 409 that create and copy rely on); get of a missing notebook returns None; delete is idempotent. Reads and writes go through `flyte.storage`, listing and deletes through the fsspec filesystem it resolves for the root, so the same code runs against `s3://` on the tenant and a local path in tests.

On Union the root is a prefix in the tenant bucket (`s3://union-us-west-2-stargazerbio/stargazer`). Every project runs as one IAM role (`union-us-west-2-stargazerbio-userflyterole`), so cross-project access works (the admin in `flytesnacks` reads what a pod in `u-<subject>` wrote) and, equally, any pod can read every user's objects. The deployer's laptop has no credentials for the bucket; only pods can reach it.

A Union deploy refuses to start without `STARGAZER_WORKSPACE_ROOT` (`admin_app.main`). Without a root (a local run), store-backed routes return 503 and the Workspace section says saving isn't available.

## Pod Hydrate & Save

The pod is a working copy; the store is the durable one. The admin never calls a pod (a `requires_auth=True` pod is unreachable server-to-server), so the pod does both ends itself.

1. **Hydrate.** `launch-notebook.sh` runs `sg_proxy.hydrate()` before starting marimo: the owner's `notebooks/` prefix lands flat in `/workspace`, their `snapshots/` in `/snapshots`. A brand-new user, or a store failure, starts with empty dirs (logged, never fatal).
2. **Starting page.** The proxy answers immediately; until marimo is up, a browser request gets a self-refreshing "Starting your notebook…" page. `/__sg__/ready` reports 200/503 for scripts.
3. **Save on an interval.** A background loop uploads every top-level, non-`_` `.py` in `/workspace` whose content hash changed, every `SYNC_INTERVAL_SECONDS` (5s), each to its own key. The hashes of just-hydrated files are seeded at startup, so the first pass doesn't re-upload them. A failed upload is logged and retried next pass. One PUT per object, so an interrupted upload can't leave a half-written notebook. Snapshots never write back, and deletions don't propagate (deleting is a dashboard action).
4. **Save at shutdown.** The FastAPI `lifespan` shutdown hook cancels the loop and runs a final pass when Knative scales the pod to zero.

Measured on the tenant (2026-10-06): a cell added in a fresh edit pod was readable through the admin's Download route seconds later; after the pod scaled to zero and was reopened, the cell was still there.

The signal path is load-bearing for step 4. Flyte's `fserve` wrapper is PID 1 and, on the Knative SIGTERM, forwards the signal to its **one direct child only** (`Popen(cmd, shell=True)` + `send_signal`). So uvicorn must be that direct child: the AppEnvironment args prepend `exec` (so the `sh -c` wrapper replaces itself with the launch script rather than lingering; Debian's `/bin/sh` does not reliably exec-collapse a bare `sh -c "script"`), and the launch script then `exec`s uvicorn into that slot. An intermediate shell anywhere in the chain swallows SIGTERM and the final save is silently skipped.

Receiving SIGTERM is necessary but not sufficient: uvicorn drains open connections and in-flight background tasks **before** running the `lifespan` shutdown. The proxy holds a long-lived task to the local marimo backend that never drains on its own, so with uvicorn's default `timeout_graceful_shutdown=None` the drain blocks forever and the final save never fires (verified empirically). The launch script therefore passes `--timeout-graceful-shutdown 15`, which bounds the drain, cancels the lingering task, and then still runs `lifespan.shutdown`. 15s sits well under the pod's 300s termination grace period.

## Creating Notebooks & Per-Notebook Resources

The Workspace section offers a **New notebook** create tile (name + blank|template seed only — resources and the tile blurb are set afterward). The seeds are real shipped notebooks — `notebooks/workspace/blank.py` and `template.py` — not generated source. `POST /workspace/create` slugifies the name, copies the chosen seed, injects **default** resources into its `[tool.stargazer]` header (`with_stargazer_resources`), writes it to the user's store (`create_workspace_notebook`, no-overwrite → 409), and **returns the rendered tile HTML**. The seeds are read from the installed package, not a checkout. (Notebooks don't pin marimo in their PEP 723 headers — `marimo --sandbox` injects the image launcher's version into each kernel venv, so the two never skew without per-notebook bookkeeping.) Create is a pure "add a notebook" action: the browser drops that tile into the Workspace grid; it does not launch or navigate. Both seed slugs are reserved create names and filtered out of the dashboard's tile listing.

Each Workspace tile carries two corner controls:

- **Gear** → settings modal to edit **resources (cpu/memory)** and **description**. Save (`POST /workspace/settings`, workspace-only) rewrites the `[tool.stargazer]` header in the store (`with_stargazer_resources(..., description=…)` via `update_workspace_notebook`) and echoes the normalized values so the browser refreshes the tile blurb + the gear's `data-*` in place. Resource changes take effect at the **next** launch (resources bind at pod-spawn); the description updates immediately. The gear seeds its fields from `data-*` the dashboard renders by fetching each workspace notebook's header (in parallel, best-effort) at page load.
- **Trash** (`POST /workspace/delete`, workspace-only) removes `<slug>.py` from the store (idempotent — a file already gone still succeeds; recovery relies on bucket versioning, not yet confirmed enabled) and tears down any edit/run pod for that slug (deactivate, then delete the record), so deleting can't orphan a pod with no tile left to Stop it.
- **Download** (`GET /workspace/download`) returns the notebook's `.py` as an attachment — the path for sharing a notebook upstream. Also on snapshot tiles (own and published).

Seed slugs are rejected by both. The browser confirms delete, then drops the tile on success.

Resources are honored **as-authored — no ceiling**. At `/launch`, the admin reads a workspace notebook's source from the store and `app.notebook_meta.parse_notebook_resources` reads `[tool.stargazer]` (cpu/memory) and passes it to `per_notebook_env(resources=…)`. Parsing is purely textual — the admin never executes notebook code. Image-baked tutorials/workflows notebooks carry no such block and keep the env's legacy `("2Gi", "6Gi")` default.

## Running State (stateful tiles)

Tile run-state is unified and authoritative. The dashboard's launch/stop handlers are **event-delegated**, so dynamically added tiles (a freshly created notebook) work with no re-binding. On load the page calls **`GET /launch/status`**, which discovers deployments with **one control-plane list** (`list_project_apps`, the same project-scoped call cleanup uses — `App.listall` can't be scoped to a per-user project), filters to `nb-{slug}-{mode}` names (`_parse_nb_name`; the mode is the last dash segment since slugs may contain dashes), then re-fetches each discovered name with `App.get` in parallel for authoritative status (list payloads may not carry full conditions). The active ones are returned with their plain endpoints; the page flips those tiles straight to **Open + Stop** instead of a fresh Edit/Run. Because it reads the control plane rather than in-memory state, it's correct across admin restarts, and because discovery is name-based it never probes notebooks that were never launched. A listing failure degrades to "nothing running" rather than an error. Org-scoped calls like this list need the org, which in-cluster init can't discover in an app pod, so the deployer bakes `FLYTE_ORG` into the admin and the admin passes it on to notebook pods.

**Hydrated Open re-serves; fresh Open links directly.** A **fresh** launch (Edit/Run click → `/launch`) links straight to the returned URL. A **hydrated** Open (from `/launch/status` on load) instead **re-serves through `/launch` on click** before navigating, because a hydrated pod may have been served before a redeploy with an older image or env. Re-serving reconciles it to the current spec (a no-op for a warm, current pod). The tab is opened synchronously in the click handler and navigated once `/launch` returns, so the await can't cost the user gesture and trip the popup blocker. A scaled-to-zero pod needs no special handling: the platform wakes it on the first request and the proxy shows its starting page.

**One modality at a time.** A notebook runs in either `edit` *or* `run` mode, never both — there's no use case for two live pods of the same notebook, and forbidding it caps pod count at one per notebook. When a tile is launched (or hydrated as already-running), the dashboard hides **both** the launched mode's own Edit/Run button *and* the other mode's, leaving only that pod's controls: **Open: Edit Mode** / **Open: Run Mode** and **Stop**. **Stop** restores both buttons. This is a client-side affordance: it removes the second-pod path from the UI rather than enforcing mutual exclusion in the control plane. There's no Save button: pods save themselves (see Pod Hydrate & Save).

A global **Clean up stopped apps** control (`POST /workspace/cleanup`) deletes (`App.delete`) the deployment records for every *deactivated* `nb-{slug}-{mode}` app in the user's project — Stop deactivates an app but leaves the record; this removes them. Active/idle apps are left alone.

## Snapshots (freeze mechanics)

Conceptual framing (snapshot vs. workflow, the publication path) is in the architecture doc and [Notebooks → Promotion Paths](../../../docs/architecture/notebook.md#promotion-paths). The mechanics:

**Freezing is a move.** `POST /workspace/snapshot` takes a notebook *out* of the editable Workspace surface: it re-creates the notebook's current stored source verbatim as a snapshot (`create_snapshot_notebook`), then deletes the workspace original (`delete_workspace_notebook`). The snapshot write happens first, so a failed move leaves the notebook editable rather than lost. The source of truth is the store, which a running pod updates every few seconds, so a freeze captures edits up to the last save pass. Like delete, snapshot tears down any running pod for the slug (`_teardown_notebook_pods`), since once moved there's no Workspace tile left to Stop it. A slug shared with a published snapshot is refused (409), since both would launch as the same `nb-{slug}-run` pod.

Each Workspace tile carries a **📸 snapshot** button (between the gear and trash) that calls this route, then drops the workspace tile and inserts the returned tile into the Snapshots grid. A snapshot tile carries **Run**, **Copy to workspace** and **Download**, plus a delete control on the user's own snapshots (`POST /snapshot/delete`); no Edit or gear, since a frozen record isn't edited or re-configured. Launching one goes through the same `/launch` path, **restricted to run mode** (`marimo run`, read-only), with its `[tool.stargazer]` resources honored like any workspace launch. A running snapshot's `nb-{slug}-run` app is discovered by `/launch/status`'s project list like any other launch, so it hydrates to Open/Stop on reload and `/workspace/cleanup` reaps its stopped pod.

**Published vs. own.** The Snapshots section lists both:

- **Published** snapshots ship in the image from `src/stargazer/notebooks/snapshots/` (`notebooks.public_snapshots()`), like tutorials. Everyone sees them, and they launch from their path in the image (`section=public-snapshots`).
- **Own** snapshots live in the user's store under `snapshots/`, and the pod hydrates them into `/snapshots` (`section=snapshots`).

Publishing one is a contribution: the author downloads it and adds it to the repo's `notebooks/snapshots/`; once merged it ships in the next image.

**Deferred:** image-digest pinning and an inputs/outputs (CID) manifest. This cut freezes the notebook *source*, which is auditable; bit-for-bit re-run is a later phase.

## Copy to workspace

**Copy is the reverse of freeze: a read-only source becomes editable.** Workflows tiles and Snapshots tiles carry a **Copy to workspace** button → `POST /workspace/copy` (`slug` + `section`). The route resolves the source (`_copy_source`): a Workflows notebook or a published snapshot is read from the installed package (`shipped_source`, `public_snapshot(...).source()`); an own snapshot from the store. It then writes it to the workspace via `create_workspace_notebook` and returns the rendered Workspace tile the browser drops before the New-notebook tile. The copy keeps the source's parsed `[tool.stargazer]` resources but gets its own `name`/`description` (from the workflow's registry title/blurb, or the snapshot's stored header) re-injected with `with_stargazer_resources`, so it tiles and launches like any user notebook. The target slug is derived from the source title (`_notebook_slug`); the store's no-overwrite create makes a name collision a **409**, so copy never clobbers an existing notebook. Copy is a pure "add a notebook" action: no launch, no navigation.

## The Proxy Data Path

- **Proxy:** the standalone `app/proxy.py` (which can't import the app package) keeps one module-local shared client with keep-alive to loopback marimo (`_upstream_client`, closed in the proxy lifespan after the shutdown save). Only `text/html` responses are buffered — for the terminal-overlay splice; everything else (static bundles, API JSON, downloads) **streams** through chunk-by-chunk (`StreamingResponse` over `aiter_raw`, `BackgroundTask(resp.aclose)`) with its original headers, so large bodies never sit in proxy memory. The raw query string passes through untouched (duplicate params intact), hop-by-hop, cookie and `X-User-*` headers are stripped, and the request body is streamed only when one exists (no gratuitous chunked framing on GETs).
- **Concurrency:** the dashboard route resolves the workspace and snapshot listings with `asyncio.gather`, and reads each workspace notebook's header in parallel (best-effort).
- **Compression:** the admin app runs `GZipMiddleware` (min 1KB) for the dashboard HTML and asset listings. The proxy does **not** — it relays marimo's own encoding untouched.

## Admin Routes (full table)

All on `app/admin_app.py` (`app_env`), all behind Union's login and the `CurrentUser` dependency except `/health`. Lifespan runs `init()` at startup.

| Route | Purpose |
|---|---|
| `/` | Dashboard (ensures the user's project on first request) |
| `/workspace/create` | Writes a new notebook to the user's store from a seed, returns the rendered tile (409 on name collision) |
| `/workspace/settings` | Rewrites a workspace notebook's `[tool.stargazer]` header (resources + description) |
| `/workspace/delete` | Removes a workspace notebook (idempotent); tears down its pods |
| `/workspace/snapshot` | *Moves* a workspace notebook into the user's snapshots; tears down its pods |
| `/snapshot/delete` | Removes one of the user's own snapshots (idempotent); tears down its run pod |
| `/workspace/copy` | *Copies* a Workflows or Snapshots notebook into the workspace as an editable notebook (409 on name collision); returns the rendered tile |
| `/workspace/download` | A workspace notebook or snapshot (own or published) as a `.py` attachment |
| `/launch` | Serves a per-notebook env into the user's project, owned by them; returns its URL |
| `/launch/status` | Reports active per-notebook apps so the dashboard hydrates running tiles to Open/Stop |
| `/stop` | Deactivates a per-notebook app by name |
| `/workspace/cleanup` | Deletes deactivated per-notebook app records |
| `/health` | Health probe |

Gone with plan 25 (each has a test asserting the 404): `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/app-install-callback`, `/workspace/enable`, `/workspace/save`, `/workspace/pod-token`.

Asset-manager routes are a separate router (`app/assets.py`, `include_router`ed onto the same app):

| Route | Auth | Purpose |
|---|---|---|
| `GET /assets` | none | Render `assets.html` (anonymous, local runs only → public tab only) |
| `GET /assets/schema` | none | `{asset_key: [{name,type,default}]}` from `ASSET_REGISTRY` (minus `_BASE_FIELDS`) for the dynamic form |
| `GET /assets/list?<kv>&network=` | public: none / private: signed in | Public served from a TTL cache (filters in-memory); private forces `_owner == user's subject` server-side (fail closed) |
| `POST /assets/sign` | signed in | `build_asset()` validate → stamp `_owner` → mint Pinata signed upload URL (filename + keyvalues + `MAX_UPLOAD_BYTES` baked in) → `{url, keyvalues}` |
| `POST /assets/update` | signed in + **owner** | Fail-closed ownership (record's `_owner` must equal the user's subject, read fresh) → `build_asset()` validate patch → re-stamp `_owner` → `PinataClient.update_metadata()` merge → updated record |
| `GET /assets/download/{cid}?network=` | public: none / private: signed in | 302 redirect; split-gateway (anon public → `PUBLIC_FALLBACK_GATEWAY`, signed in → `PINATA_GATEWAY`); private → signed URL |

## Asset Manager (mechanics)

`PINATA_JWT` rides into the admin pod via `_RUNTIME_SECRETS`, baked from the deployer's shell into `env_vars` (App-pod `secrets=` is dropped by the devbox Flyte build; whether Union injects app secrets is unconfirmed). It's the only secret left in the app tier, and anyone who can view the app spec can read it. Without it the routes 503 and the page shows "not configured"; there is no TinyDB fallback for this surface.

- **Owner stamping.** `/assets/sign` stamps the signed-in user's subject as `_owner` *after* `build_asset()` validation, so it rides the signature-protected signed URL — unforgeable from the browser. Workspace/SDK uploads stamp from `STARGAZER_OWNER` instead: the launcher injects it into per-notebook pods (`env.env_vars["STARGAZER_OWNER"]` next to `FLYTE_PROJECT`), and `config._stargazer_env_vars()` forwards it into task pods at submission so pipeline outputs are owned too. Stamping lives in `PinataClient.upload()` (`_stamp_owner`, env wins over any stale value) and in the sign route; `build_asset()` rejects user-supplied `_*` keys so the namespace stays clean.
- **Metadata edit (`update_metadata`).** A mis-tagged record is fixed in place rather than delete-and-re-uploaded. `PinataClient.update_metadata(cid, keyvalues, network)` looks up the file's internal UUID by CID, then `PUT /v3/files/{network}/{id}` with the patch — Pinata **merges** (verified empirically: supplied keys added/overwritten, omitted keys preserved, no key removal), and the bytes/CID are untouched so `*_cid` provenance edges survive. `_stamp_owner` runs here too (env wins; no-op in the admin pod, where the route sets `_owner` explicitly). `LocalStorageClient.update_metadata` mirrors the merge into TinyDB when there's no remote. Two surfaces drive it: the MCP `update_file` tool (validate via `build_asset` → delegate, shared-JWT so unenforced by design) and the `POST /assets/update` route (which additionally **fail-closes on ownership** — the record's current `_owner` must match the signed-in user, read fresh from Pinata not the public TTL cache, so a shared-JWT user still can't rewrite another user's or an unowned record from the page). Editing is the headline reason the bare `cid` is *not* treated as a relationship key in the graph — a content-addressed id never changes under a metadata edit.
- **Public TTL cache.** `_public_cache` (module global, `PUBLIC_CACHE_TTL` = 60s) holds one unfiltered public-network listing; the public tab filters it in-memory. So anonymous public browsing costs ≤1 Pinata listing call per TTL regardless of traffic, and the admin acts as a semi-static mirror. Refresh is single-flight (`_public_cache_lock`, double-checked) so concurrent misses share one listing. Swap to a background refresher if the first-request-after-expiry latency ever matters.
- **Client swap for tests.** `_pinata_client` / `_public_cache` are module attributes resolved at call time, so route tests monkeypatch a fake Pinata client and reset the cache (`tests/unit/test_assets_routes.py`, `TestClient` without lifespan).
- **Errors** are FastAPI-standard `HTTPException` → `{"detail": ...}` (401 auth, 400 validation, 503 not-configured), via the `require_user` / `_require_pinata` guards.

### Template (`app/templates/assets.html`)

The page extends `base.html` and renders inside one `.dashboard` card — the same glassy surface as the notebook dashboard — with the identical brand+avatar header (an `Assets`↔`Dashboard` cross-link in each menu). It reuses base's tokens/buttons; asset-specific CSS rides the `{% block extra_css %}` hook. **The reactive `#sky` starfield is untouched** — the asset graph is a separate foreground canvas inside the card.

The graph is rendered by **Cytoscape.js**, vendored as `app/static/cytoscape.min.js` (pinned 3.30.2, ~370 KB) and `<script src>`-loaded only on this page. This is the one deliberate exception to the app's "ship only hand-written JS" convention (base.html's starfield is still hand-rolled): a graph library earns its keep here because zoom/pan/node-drag/force-layout are exactly its core competency, and the project has no bundler, so a single vendored min.js (no build step, served by the existing `/static` mount) was the lowest-friction way in. To update: re-fetch the pinned version from jsdelivr into the same path. The rest of the page JS is still dependency-free vanilla, gated behind `{% if pinata_configured %}`. A `state` object (network, view, filters, `records`, `selected`, `editing`, `schema`) is the single source of truth; the graph and list are two renderings of the **same** `/assets/list` payload, so toggling Graph⇄List re-renders from memory while changing the network tab or filters refetches.

- **Graph edges from `*_cid`.** `relKeys()` selects every keyvalue ending in `_cid` with a non-empty value (bare `cid` excluded); `buildGraph()` draws an edge from the record to the asset whose `cid` matches the value, labeled with the key minus `_cid` (`reference_cid` → "reference"). The typed `*_cid` fields (`reference_cid`, `r1_cid`, `mate_cid`, `alignment_cid`, `variants_cid`, `known_sites_cid`, `source_cid`) ride in `keyvalues` from `to_keyvalues()`, so no backend change was needed; custom/bare assets carrying their own `*_cid` rows link too.
- **Dangling edges** (a `*_cid` value with no matching node in the current set — cross-network, owner-scoped-out, or unloaded) are **not drawn**; instead the detail card lists *all* of a node's links, resolving in-view targets to a clickable chip and showing the rest read-only as "not in this view," so provenance is never hidden.
- **Layout** is Cytoscape's built-in `cose` force layout (`GRAPH_LAYOUT`, non-animated, fit-to-view), run on `graphElements(records)` — nodes sized by degree, edges carrying a target arrow for provenance direction. Style lives in the `GRAPH_STYLE` array (canvas-rendered, so hex/rgba not CSS vars; it mirrors the violet/accent palette). Nodes are capped at `NODE_CAP` (150) with a "showing N of M" hint past the cap. The `cy` instance is created once and reused (`cy.elements().remove()` + `add` + `resize` + re-layout on each render).
- **Interaction** is mostly Cytoscape-native: **scroll zooms**, **drag pans the background**, **drag moves a node** (free with the library). `bindGraphEvents()` adds the app behaviors: `tap` on a node → `selectAsset()`, `tap` on empty canvas → clear; `mouseover`/`mouseout` drive the styled `graph-tip` tooltip (positioned via `node.renderedPosition()`) and a neighbor/edge `.hot` highlight; a native container `dblclick` calls `cy.fit()` to reset. Selection is driven by a `.selected` class we toggle (cy runs `autounselectify`), so it stays in sync whether you click a graph node or a list row (`selectAsset()` is shared). Clicking pins the **detail card** (full metadata, system `_*` keys dimmed, linked-asset chips, a Download button → `/assets/download/{cid}?network=`, and **Edit metadata** on owned records).
- **Upload** is schema-driven from `/assets/schema`: a typed mode (inputs per field, non-`str` values JSON-encoded to match `from_keyvalues()`) and a visually-distinct custom/bare mode (dashed framing, generic notice, free-form k/v rows reserving `asset`/`cid`/`name`/`_*`). On submit it mints (`POST /assets/sign`), PUTs the file straight to the single-use signed URL (re-mint-and-retry once on failure), then **optimistically inserts** the returned record into `state.records` so it appears before Pinata's list catches up. Network radio defaults to Private; the 100 MB cap is enforced at mint via `MAX_UPLOAD_BYTES` (TUS for larger is the roadmap's TUS resumable uploads item).

## Runtime Init

The same `init()` (`app/init.py`) works locally and in-cluster:

| Context | Signal | Call |
|---------|--------|------|
| In-cluster app pod | `_U_EP_OVERRIDE` set | `flyte.init_in_cluster()` |
| API-key context | `FLYTE_API_KEY` set | `flyte.init_from_api_key(...)` |
| Local dev / deployer | neither set | `flyte.init_from_config()` |

FastAPI's lifespan calls `init()` once at startup so subsequent SDK calls have a configured client.

## Images (build & publish)

The admin app and the per-notebook pods share a strict split:

- `app_env.image` is Flyte-built via `with_uv_project` — the admin is small Python with no heavy deps, and the Flyte builder is the natural fit.
- Per-notebook envs use the **`notebook-app`** image, defined programmatically as `notebook_app_img_recipe` in `app/per_notebook.py` (proxy, launch script, bioconda CLIs, Claude Code, SDK source at `/stargazer`). The admin pod references the exact build via `Image.from_base(config.NOTEBOOK_IMAGE)` so it never tries to (re)build the image itself — the admin pod has no Docker daemon or project source layout. (The `note` target in the project `Dockerfile` — `stargazer-note` — is for local `docker run` exploration only and is *not* the hosted image.)

The admin deploy entrypoint (`python -m app.admin_app` / `stargazer-app`) runs `flyte.build` on the recipe (`_build_notebook_image`) and bakes the returned content-hashed URI into the admin pod as `STARGAZER_NOTEBOOK_IMAGE` before calling `flyte.serve(app_env)`. Every per-notebook pod therefore runs exactly the build that shipped with its admin: no mutable tag, no `docker buildx` retag, and no chance of a node serving a stale cached `:latest`. A per-notebook pod picks up new proxy/launch code on its next re-serve after a redeploy (the dashboard's Open re-serves).

**On Union today images are built locally and pushed to GHCR.** Union's remote builder emits Nydus-only images the tenant's nodes can't pull (ticket open), so deploys set `FLYTE_IMAGE_BUILDER=local` and `STARGAZER_REGISTRY=ghcr.io/stargazerbio`, with docker logged in to GHCR. A new GHCR package starts internal and must be made public once before nodes can pull it.

## Deploy targets (devbox vs union)

`STARGAZER_TARGET` (`devbox` default, or `union`) is the one switch between the local devbox and the hosted Union tenant. `stargazer.config` validates it (a typo is an import error, not a silent devbox), and forwards it, plus any explicit `STARGAZER_REGISTRY`, into every pod via `STARGAZER_ENV_VARS`, so in-pod builds resolve images the same way the deployer does.

| Setting | devbox | union |
|---|---|---|
| Deployer's Flyte config (`app.config.FLYTE_CONFIG`) | `.flyte/config.yaml` | `.flyte/union.yaml` (remote builder) |
| `STARGAZER_REGISTRY` default | `localhost:30000` | unset: the remote builder pushes to Union's registry (set to GHCR while it's broken) |
| Login | none: the devbox has no Union auth, so the app tier doesn't run there | Union's gate |
| Storage port-forward at deploy | yes | never (kubectl may point anywhere) |

`FLYTE_DOMAIN` (default `development`) is independent of the target: it's where the admin serves and looks up every per-notebook app, so a prod deploy sets `FLYTE_DOMAIN=production`. Both `.flyte/` files are gitignored; create `union.yaml` with `flyte create config --endpoint dns:///<tenant> --image-builder remote -o .flyte/union.yaml`.

## Deploy Settings

No secret is required to deploy. The deployer's shell supplies:

| Env var | Purpose | If absent |
|---|---|---|
| `STARGAZER_TARGET=union` | picks `.flyte/union.yaml` | the devbox is targeted |
| `STARGAZER_WORKSPACE_ROOT` | where users' notebooks live; baked into the admin and every pod | a Union deploy refuses to start |
| `FLYTE_IMAGE_BUILDER=local`, `STARGAZER_REGISTRY=ghcr.io/stargazerbio` | the local-build path while the remote builder is broken | images build remotely and fail to pull |
| `PINATA_JWT` | the asset manager | `/assets` renders "not configured" |

The deployer's org (from its Flyte config) is baked in as `FLYTE_ORG` automatically, and the notebook image URI as `STARGAZER_NOTEBOOK_IMAGE`.

## Known Gaps

Production gaps live in the roadmap, not here: project creation from the admin (refused on Union, see Project Provisioning), the org-wide platform key in every pod, the shared IAM role for the store, Union cookies reaching pods, invite-only onboarding, and no Union auth on the devbox. See [`.opencode/plans/ROADMAP.md`](../../plans/ROADMAP.md).
