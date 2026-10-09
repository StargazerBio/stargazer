# Stargazer Roadmap

Upcoming work is ordered — the **next feature is at the top**. Items are unnumbered: priority is list order, so reordering stays a small diff. Refer to other items by name, never by position. Move items into Complete (with a ✅) as they ship.

## Upcoming

- **Make `Asset.fetch()` cheaper.** Even when the file is already in the
   cache, `fetch()` looks up the asset's companions every time: one index
   query (an HTTP call to the dashboard on Union) and, with `PINATA_JWT` set,
   one Pinata API call (measured 2026-10-07). A task that fetches many assets
   pays that many round-trips. Options: memoize companion lookups per
   process, or ask Pinata only about assets that came from the public tier.
- **Union production deploy** (tenant: `stargazerbio.us-west-2.unionai.cloud`).
   Done in PRs: per-pod session keys (#2), the `STARGAZER_TARGET`
   devbox/union switch, a configurable domain, and a fixed per-deploy
   notebook image (#3). Union fixed the remote builder's unpullable (Nydus)
   images on 2026-10-06, so deploys are back on the remote builder and the
   GHCR workaround is gone. Remaining:
   - **Union-native app secrets.** Dashboards carry no secret today (the
     asset manager is off for that reason). When the asset manager returns, a
     Pinata key can't be baked into `env_vars`, where the owner sees it. Move to
     `flyte create secret` plus `secrets=[flyte.Secret(...)]`, after
     confirming Union injects app secrets at all.
   - **`flyte.deploy` with commit-SHA versions** in place of `flyte.serve`
     for `stargazer-users upgrade`, run from CI with an org-admin API key.
   - **Resource ceilings.** Notebook resources are honored as-authored. Cap
     them with `flyte edit settings --domain production` (`task_resource.max.*`),
     after checking that the cap applies to apps and not only tasks.
- **Org-wide platform key in every pod.** Every app and task pod
   authenticates as `stargazerbio-EAGER_API_KEY-union-us-west-2`, which
   holds org-wide `contributor`, so code in any notebook can act in any
   project. Ask Union whether an app can run without it or with a key we
   supply.
- **Per-user storage isolation.** Every project on the tenant runs as one
   IAM role, so a notebook's own code can read and write every user's
   workspace objects (and all task data). Needs per-project roles scoped to
   each user's prefix. The roles and policies are ours to create in our AWS
   account (attaching policies to the shared `userflyterole` needs no Union
   step), but per Union's BYOC docs, Union binds a custom role to a
   project-domain namespace. So each new user's project would need a Union
   request unless that binding can be automated.
   ([Union BYOC: enabling AWS resources](https://www.union.ai/docs/v2/union/deployment/byoc/enabling-aws-resources.md))
- **Union session cookies reach notebook pods.** Union forwards the
   visitor's session cookies to the app. The proxy strips them before
   marimo, but code in a pod could still capture a visiting org member's
   token. Look for a way to have Union drop them for an app, or isolate the
   proxy from notebook code.
- **App internal addresses skip Union's login.** Every app answers at
   `http://<app>.<project>-<domain>.svc.cluster.local` with no login and no
   identity headers; a task pod in the same project reached a
   `requires_auth=True` app that way (measured, plan 27 Piece 0). Untested:
   whether pods in other projects can reach it, and whether a forged
   `X-User-Subject` sent there gets through the dashboard's owner check. If
   both hold, code in any pod can act as any user on their dashboard. One fix
   is to verify the signed `X-User-Token` ID token instead of trusting
   `X-User-Subject`; another is per-namespace network policy.
- **Self-serve onboarding.** New users are onboarded by an org admin
   (`stargazer-users onboard`, which sends Union's invite), since Union
   doesn't auto-provision users on first sign-in. Unverified: that the
   subject `User.create` returns is the one the user's first GitHub sign-in
   arrives with; check with a real second address before onboarding anyone
   new. If Union adds self-serve sign-up, onboarding could run on first
   sign-in instead.
- **Union injects third-party analytics into app pages.** Every page our
   apps serve picks up Heap, Userflow, Reo, Google Analytics (via `/cexr/`)
   and Cloudflare scripts at Union's edge; Heap's beacon carries the
   visitor's subject. Those scripts run on the dashboard and likely on
   notebook pages too, where they can read whatever the page shows. Ask
   Union whether apps can opt out.
- **Old dashboard revisions keep running after a redeploy.** Each deploy
   makes a new Knative revision, and the old one keeps its pod for up to an
   hour (`autoscaling.knative.dev/window: 1h`): three were running at once on
   the devbox after three deploys (measured 2026-10-08). If each pod's
   Litestream replicates its own copy of the index to the same bucket path,
   that breaks Litestream's one-writer rule, and a restore could come back
   from a stale copy (inferred; the restart test still found every row).
   Applies to `upgrade` on Union too. The devbox tests deploy once per
   session, so they add revisions quickly.
- **Small gaps found while testing on the devbox (2026-10-09).**
   - `gatk_env` sets no `resources=`, which AGENTS.md requires of every
     TaskEnvironment for the devbox's ~7.5 GiB node.
   - `apply_bqsr` stores the recalibrated BAM but not its index, unlike
     `mark_duplicates` and `sort_sam`. The germline workflow still finishes
     on the devbox, so a later step may be indexing it again (inferred).
- **Code bugs found in the docs correctness sweep (2026-10-09).** Each
   changes stored outputs or behavior, so each wants its own branch.
   - `Asset.fetch()` pulls more than companions: any asset recording
     `<key>_cid` comes along, so `Reference.fetch()` downloads every
     `Alignment` made against it (`reference_cid`), and every task that
     fetches the reference after alignment pays for them (measured against
     an isolated store). Related to "Make `Asset.fetch()` cheaper".
   - `normalize` copies `X` into `layers["counts"]` after `normalize_total`,
     so the layer holds normalized counts (every row sums to ~498 on the
     fixture), while its docstring, and `find_markers`, which tests on that
     layer, say raw counts (measured).
   - `variant_recalibrator` records the tranches file only as a path in its
     own pod (`VQSRModel.tranches_path`) and never stores it, so
     `apply_vqsr` in another pod can't read it (inferred from the code; no
     test runs the two in separate pods). Plan 27's open Q20: the tranches
     file should be its own companion asset.
   - `haplotype_caller` sets `source_samples` to a string, not a list; it
     round-trips as a string, so `len()` counts characters (measured: 7 for
     `"NA12829"`).
   - The scRNA tasks aren't exported from `stargazer.tasks`, so `list_tasks`
     and the catalog omit them, and `run_task` can't run them.
   - The default `PINATA_GATEWAY`, `https://dweb.link`, no longer serves
     files: every request answers 429 "This IPFS gateway is switching to a
     service worker gateway only" (`sunset: 21 Sep 2026`), so
     `fetch_resource_bundle` and any public download fail on a default
     config, and with them the README quickstart. `gateway.pinata.cloud`
     answered a full download with a Cloudflare challenge (429) and
     `w3s.link` with 429 (all measured 2026-10-09). The account's dedicated
     gateway (`<name>.mypinata.cloud`) served the demo files during plan 27,
     but anonymous downloads through it spend account bandwidth. Picking the
     default is a decision, not a one-line fix.
- **Notebooks on the devbox.** The devbox dashboard and asset storage work
   (`cli/devbox_dashboard.py`, a stand-in user), and a tutorial launched in
   run mode from that dashboard starts and serves marimo (2026-10-08). Edit
   mode, workspace saving and the in-notebook terminal haven't been driven.
- **Local-to-cluster storage.** A run submitted from this machine with the
   default local store and index has nowhere shared to write: those
   defaults aren't forwarded into task pods (`_stargazer_env_vars` in
   `config.py`), since a pod can't reach them. Today a remote run needs
   `STARGAZER_STORE_ROOT` and `STARGAZER_INDEX_URL` exported to a store and
   index pods can reach, as in the devbox recipe in
   `docs/guides/contributing.md`. Inputs uploaded to the local store before
   the switch point at paths no pod can read. On Union a local machine can't
   write to the bucket, and `HttpIndex` sends no token to the dashboard's
   public URL. Plan 27's open Q15 and Q21.
- **Asset storage follow-ups (plan 27).** `publish(asset)` to promote a
   stored asset to Pinata's public network with its keyvalues and `_owner`
   (the CID doesn't change); the asset-manager page on the index instead of
   Pinata, which also retires most of the TUS browser-upload item; a
   read-only Artifacts projection of selected outputs, for console lineage
   and triggers.
- **Union console handoff (per-user project access).** Delivered by the
   per-user dashboards' onboarding (users get `contributor` on their own
   project); what remains is the dashboard's link out to the console.
   [`24_union_console_handoff.md`](./24_union_console_handoff.md)
- **In-notebook local-vs-remote toggle UI.** Formalize the dispatch choice as a reusable `mo.ui` element (radio / segmented control) so individual cells don't need to hardcode `flyte.with_runcontext(mode="local").run` vs `flyte.run`.
- **Marimo AI features investigation.** Determine what marimo's native AI surface offers (`mo.ai.chat` / similar), whether tool-calling is supported, and how to wire the registry catalog in.
- **Publish `stargazer` to PyPI.** Once the package is published, notebook PEP 723 headers can pin a version (`stargazer == X.Y.Z`) instead of `[tool.uv.sources] stargazer = { path = "/stargazer", editable = true }`. Unlocks fully reproducible community notebooks without baking the source path.
- **Upload public assets for quickstart workflow to Pinata.**
- **Update README with CLI quickstart and bump to alpha status.**
- **Interactive workflow for generating a DB from existing data in `STARGAZER_LOCAL`.**
- **Condensed context files for production use (separate from dev).**
- **Recurring docs-sync job** so architecture docs never go stale against the code.
- **Agentic PR process** for end-to-end automated review/merge of trusted contributors.
- **More robust logging.**
    - Per-task tags so logs can be demultiplexed.
    - One logfile per workflow execution.
    - Stop flushing to stdout/err to keep context windows clean.
    - Env vars for log level and a bool to include actual tool-call output.
- **Data-aware caching.** Flyte's input-hash caching is solid but breaks down for keyword/metadata-based workflows — need a higher-level cache keyed on semantic inputs.
- **`stargazer promote-task` CLI.** The mechanical step of task promotion — extract the cell function via `ast` (marimo files are valid Python), drop it into the target `src/stargazer/tasks/` module with decorator and types intact, generate a skeleton test, open a PR via the server-side GitHub flow. Waiting for real usage patterns to inform the exact UX. (Was a Roadmap note in `docs/architecture/notebook.md`.)
- **In-notebook MCP integration.** marimo does not yet support custom MCP server configuration; when that ships upstream, the stargazer MCP server becomes a one-line config addition to the chat panel, giving the in-notebook assistant direct access to `list_tasks`, `run_task`, `query_files`, etc. (Was a Future note in `docs/architecture/notebook.md`.)
- **Bit-for-bit snapshot reproducibility.** Snapshots currently freeze the notebook *source* only; add image-digest pinning and a CID input/output manifest so a snapshot re-run is bit-for-bit. (Was a Deferred note in `docs/architecture/app.md`.)
- **Cohesive `marimo.toml` integration.** A root `marimo.toml` exists with `[ai] rules` carrying stargazer authoring conventions, but it's an ad-hoc artifact — no story for how it's baked into the notebook image, kept in sync with the conventions in AGENTS.md/docs, or extended (completions, future MCP wiring, per-notebook overrides). Design one deliberate marimo-config surface and remove the duplication. Subsumes the marimo-AI angle of the Marimo AI features investigation and In-notebook MCP integration.

- **TUS resumable uploads — browser half remaining.** Pinata's plain
    multipart POST is hard-capped at 100MB; larger files need the TUS
    resumable endpoint (per-file ceiling then 10 GiB, chunks <50MB).
    - ✅ **SDK/task outputs (2026-06-10):** `PinataClient.upload()` now
      size-branches — ≤100MB plain POST, larger streams via chunked TUS
      (`_upload_tus`, CID read from the `Upload-Cid` header on the final
      PATCH). Chunked-first: no resume yet. Verified by
      `test_tus_upload_multichunk_roundtrip` (pinata-marked).
    - ⬜ **Browser/assets page:** wire `tus-js-client` into `assets.html`
      (Piece 3 territory) so the page lifts past `MAX_UPLOAD_BYTES` (100MB).
      Confirmed empirically that **signed upload URLs speak full TUS** —
      anonymous TUS creation against a signed URL returns 201 with a signed,
      resumable Location URL whose mint-time keyvalues/filename/network/size
      cap ride in signature-protected query params, so the
      no-unvalidated-metadata property carries over. Note: the resumable
      session inherits the signed URL's `expires`, so mint generously for
      big files.
    - ⬜ **Resume** (`HEAD`-then-continue-from-offset) for both halves — the
      real payoff of TUS (survive a dropped multi-GB upload); deferred until
      a flaky large upload demands it.

- **Notebook-declared pod image (`main_img`).** A notebook declares the image
    its own pod runs on as a `flyte.Image` expression in its setup block;
    `/launch` parses it statically, replays it onto the base image, builds it,
    and serves the pod on the result. Replaces the growth curve of the
    `[tool.stargazer]` table + settings modal — every new environment knob
    currently costs a form field, parser, writer, and template row — with one
    object that already has the whole Image API behind it. **Blocked on a
    remote image builder:** a dashboard pod has no Docker daemon, so today the
    deployer builds the notebook image (`onboard.build_notebook_image`). Scoped to workspace
    notebooks first; image-baked tutorials/workflows deferred.
    [`23_notebook_declared_image.md`](./23_notebook_declared_image.md)

## Complete

- ✅ Note and chat images rebuilt and published (2026-10-09): the Dockerfile's `base` stage ran `uv sync` with no extras, so the chat image couldn't start the MCP server its `.mcp.json` names or run the scRNA workflow, and it had no Flyte config. The GHCR `:latest` tags dated from 2026-05-21, and that note image opened a tutorial that no longer exists. `base` now installs the `mcp` and `bio` extras and writes the local Flyte config for both images. Both are published to GHCR for amd64 and arm64, as `:latest` and the commit's short hash. Verified on native arm64 builds: the chat image's server lists all ten tools, and with the demo files in its cache, `scrna_clustering_pipeline` stored `s1d1_markers.h5ad` (6,307 cells, annotated) in 84s; the note image serves the Assets tutorial. The bundle download itself still fails on the default gateway (above).
- ✅ Per-user dashboard upgrades and a version tag (2026-10-09): `stargazer-users upgrade` used to deploy nothing while any user had a run going, though a redeploy only risks its own owner's index. It now goes one user at a time, checking each just before their deploy, skips busy users and comes back for them every minute until every dashboard is redeployed. Each dashboard carries the deployer's commit (`git describe --always --dirty`) as `STARGAZER_VERSION` and shows it in its footer. Verified on the tenant: with a run going in `u-pryce`, `upgrade` waited four passes, deployed once the run finished, and the dashboard served the commit in its footer.
- ✅ Asset storage on the object store, indexed per user (2026-10-08, PR #13): asset bytes moved off Pinata into object storage as `flyte.io.File`s, identified by an IPFS CID computed locally (it matches Pinata's). The keyvalue index is SQLite: a file on disk locally, owned by each user's dashboard on Union, served to task and notebook pods over HTTP and kept durable by Litestream. TinyDB, the two storage modes and Pinata as the working store are gone; Pinata stays as the public tier for shared data, attributed by `_owner`. Verified on the tenant with the real scRNA pipeline for both demo samples and a 20-way fan-out. Its open questions and follow-ups are in Upcoming (Local-to-cluster storage, Asset storage follow-ups, the VQSR tranches bug). [`27_asset_storage_index.md`](./27_asset_storage_index.md)
- ✅ Test tiers, and the germline workflow on the devbox (2026-10-08): each top-level directory under `tests/` belongs to exactly one tier, and its tests carry that tier's marker. `unit` (assets, notebooks, unit, utils) is a bare run, and pre-commit runs it on every commit. `tasks` runs every task test in the image its task runs in (`cli/docker_task_tests.py`): the GATK and alignment tests in `gatk_env`'s, which carries the tools so no one installs them (the tests that call them used to skip wherever the tools were missing, which was everywhere), and the scRNA ones in `scrna_env`'s. `pinata` holds the tests that call the real Pinata API. `devbox` tests deploy the dashboard, store and find assets across pods, and run `germline_short_variant_discovery` end to end on the devbox; the `verify-stargazer` devbox recipes drive them. A test never skips: outside its tier it's deselected, inside it a missing tool or service fails. Every Stargazer image is now x86_64-only, as on Union, because GATK's GenomicsDB has no arm64 build; on an Apple-silicon devbox those pods run emulated. Getting the workflow through on the devbox fixed six things. Task pods couldn't import `stargazer`, so the task images now install it. The devbox had no `PINATA_JWT` secret, so every task pod was refused; `cli/devbox-setup.sh` creates it. Picard's BAM index (`<name>.bai`) was never stored. Joint calling read contigs from a path it hadn't fetched, and now defaults to every contig. `bwa-mem2` couldn't find its CPU-specific binaries on x86_64, which likely broke it on Union too. And joint calling needed x86_64. Verified: unit 393 passed in 8s; tasks 52 passed, 37 in `gatk_env`'s image and 15 in `scrna_env`'s, in 2m34s including both image builds; devbox 6 passed in 2m55s, with the germline run joint-calling the cohort; one read-only pinata test passed.
- ✅ Devbox dashboard and asset storage (2026-10-08): `cli/devbox_dashboard.py` deploys one dashboard on the devbox for a stand-in user (`SG_STAND_IN_SUBJECT`, never honored on Union), storing under `s3://flyte-data/stargazer`, and holds the storage port-forward open while it uploads. The Litestream launcher now takes an S3-compatible store's endpoint and keys from Flyte's `FLYTE_AWS_*`. Verified with the `verify-stargazer` devbox recipe: one pod stored three files, a second found and read them all back, and the index came back whole after two dashboard restarts.
- ✅ Per-user dashboards (2026-10-06): the shared admin is replaced by one dashboard per user, in their own readable project (`u-<handle>`), serving only its owner. An org admin runs `stargazer-users onboard` to invite or find the user, create the project, grant `contributor` on it alone, and deploy the dashboard at a stable subdomain; `upgrade` is the release, `offboard` stops apps, removes access and archives. Union's app gate needs project view, so this keeps every user's console to their own project, and no privileged credential is deployed. Verified on the tenant end to end. Still open: whether an invited user's first sign-in arrives with the subject `User.create` returned (needs a real second address). [`26_per_user_dashboard.md`](./26_per_user_dashboard.md)
- ✅ One login: Union auth + workspace state on object storage (2026-10-06): Union's GitHub SSO is the only login; the app tier no longer talks to GitHub (no OAuth App, fork, GitHub App or session cookie). Workspace notebooks and own snapshots live on object storage keyed by the Union subject; notebook pods hydrate at launch, save every few seconds and at scale-to-zero, and admit only their owner. Verified on the tenant end to end. One finding is still open: the admin's in-cluster identity is refused project creation on Union, so each user's `u-<subject>` project has to be created by an org admin until project creation moves out of the app. [`25_workspace_state_object_storage.md`](./25_workspace_state_object_storage.md)
- ✅ scRNA per-sample output filenames (2026-10-05): every scRNA task wrote a fixed filename (`qc_filtered.h5ad`, `reduced.h5ad`, …) into the shared store, so samples fanned out in-process with `asyncio.gather` overwrote each other and downstream stages read the wrong sample's data. Outputs are now prefixed with `sample_id`, matching the GATK tasks. Verified with `verify-stargazer` on the scRNA pipeline notebook (every stage `ok` for both samples), and locked in by `tests/tasks/scrna/test_sample_isolation.py`.
- ✅ Toolchain pinning + lint/SDK catch-up (2026-08-07): ruff pinned to one version across `.pre-commit-config.yaml` and `pyproject.toml` (they had drifted 0.14→0.16, where ruff's default rule set grew 59→413 and the two gates diverged); 322 findings resolved — auto-fixes applied, deliberate patterns declared in `[tool.ruff.lint]` with rationale, the frozen v1 reference snapshot untracked and gitignored. MCP SDK migrated to 2.x (`FastMCP` → `MCPServer`, `mcp.server.fastmcp` → `mcp.server`) and bounded to `<3`; that import had been broken, taking 3 unit tests and a pre-commit hook with it.
- ✅ GitHub App deploy-credential gate (2026-08-07): a half-exported App credential pair (`GITHUB_APP_ID` without `GITHUB_APP_PRIVATE_KEY`) made Workspace saving read as disabled for every user, silently, for two months. `main()` now refuses to deploy on a partial pair, module import warns, and the previously-silent "no fork found" login path logs. Deploy-secret contract documented in [`app_internals.md`](../reference/architecture/app_internals.md).
- ✅ App-tier performance & modernization audit (2026-07-06): one pooled HTTP client per process (aiohttp out of the app tier), streaming notebook proxy, `/launch/status` via a single project deployment list, gzip on the admin, single-flight public-asset cache. [`archive/22_app_tier_performance_audit.md`](./archive/22_app_tier_performance_audit.md)
- ✅ Asset manager dashboard page (2026-06-16): graph + list + upload surface for arbitrary assets, on new `app/assets.py` routes (form schema, list, upload, download) plus `update_metadata` across every storage backend. Strict asset-subtype enforcement was loosened so arbitrary assets are first-class, asset building/checking moved out of the MCP server into the assets module where it belongs, exceptions refactored onto FastAPI's `HTTPException`, and the handrolled graph HTML replaced with vendored cytoscape.js. The browser half of TUS did **not** land — uploads through the page are still capped at `MAX_UPLOAD_BYTES` (100MB), tracked under TUS resumable uploads in Upcoming. [`archive/20_asset_manager_page.md`](./archive/20_asset_manager_page.md), [`archive/21_asset_manager_template.md`](./archive/21_asset_manager_template.md)
- ✅ Tutorial story tightening (2026-06-09): the tutorial sequence simplified and given one coherent arc. [`archive/19_tighten_tutorial_story.md`](./archive/19_tighten_tutorial_story.md)
- ✅ GitHub token scope tightening (2026-06-05): the broad OAuth token is now used exactly once — to fork the repo — and then discarded. A dedicated GitHub App, installed when the user enables Workspaces, is scoped to the fork alone and mints short-lived installation tokens for every subsequent op (`app/installation_tokens.py`). The 2026-08-07 deploy-credential gate above is the follow-up to this work. **Carry-over:** the plan's deploy checklist is still unchecked — App Setup URL, credential export, notebook image rebuild, and live expiry/revoke verification all need a real deploy. [`archive/18_tighten_github_token_scope.md`](./archive/18_tighten_github_token_scope.md)
- ✅ Per-notebook apps + marimo `--sandbox` inline deps (2026-05-20): Edit/Run spawns a per-notebook app from a shared static `note` image, with Python deps inlined via PEP 723 and resolved into a per-notebook sandbox venv at boot; container-local fork clone on launch, push-back on shutdown (Flyte v2 rejects pod templates on AppEnvironments, so there is no per-user PVC). The cookie-validating proxy serves `/__sg__/workspace/list` and `/__sg__/workspace/sync` locally and carries a Ctrl+\` terminal overlay for agentic work in the notebook. [`archive/17_per_notebook_apps.md`](./archive/17_per_notebook_apps.md)
- ✅ Admin app with embedded dashboard (2026-05-18): single shared FastAPI deployment carrying OAuth, fork discovery/creation, per-user provisioning into `sg-<username>`, the dashboard tile UI, and the `/launch` broker (plus `/launch/status` polling against real cluster state). The per-user dashboard pod from the original three-app design was folded into this one. Follow-ons shipped through 2026-07-01: notebook snapshotting for frozen reproducible runs, snapshot delete, copy-to-workspace for public workflows and snapshots, per-notebook resource config, and workspace save/delete/cleanup. [`archive/16_admin_app_with_dashboard.md`](./archive/16_admin_app_with_dashboard.md)
- ✅ scRNA preprocessing tutorial rebuild (Asset → Task → Workflow → local → remote). [`archive/15_scrna_tutorial_rebuild.md`](./archive/15_scrna_tutorial_rebuild.md)
- ✅ Integrate marimo as the notebook experience (basic plumbing — per-user provisioning, in-pod execution, tutorial scaffold).
- ✅ Create Stargazer org.
- ✅ Set up GitHub Pages.
- ✅ Exhaustively link docs to code for agent traversal.
