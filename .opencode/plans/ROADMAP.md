# Stargazer Roadmap

Upcoming work is ordered — the **next feature is at the top**. Items are unnumbered: priority is list order, so reordering stays a small diff. Refer to other items by name, never by position. Move items into Complete (with a ✅) as they ship.

## Upcoming

- **Create users' projects outside the app.** The admin ensures
   `u-<subject>` on a user's first request, but on Union its in-cluster
   identity (the org platform key, `contributor`) is refused
   `action_administer_project`, so new users see "still being set up"
   until an org admin creates the project. Project creation needs to move to
   something run with admin rights.
- **Union production deploy** (tenant: `stargazerbio.us-west-2.unionai.cloud`).
   Done in PRs: per-pod session keys (#2), the `STARGAZER_TARGET`
   devbox/union switch, a configurable domain, and a fixed per-deploy
   notebook image (#3). Remaining:
   - **Remote-builder images can't be pulled.** Union's builder pushes
     Nydus-only images and the tenant's nodes have no Nydus snapshotter, so
     every remote-built image fails at pull. Ticket filed with Union. Until
     it's fixed, deploys build locally and push to GHCR
     (`FLYTE_IMAGE_BUILDER=local`, `STARGAZER_REGISTRY=ghcr.io/stargazerbio`);
     each new GHCR package starts internal and must be made public once.
   - **In-pod image builds.** `STARGAZER_REGISTRY` is forwarded into every
     pod, but pods have no credentials for GHCR, so a task image built from
     inside a notebook can't be pushed. Resolves itself when the remote
     builder works again.
   - **Union-native app secrets.** Only `PINATA_JWT` is left baked into
     `env_vars`, where anyone who can view the app spec sees it. Move to
     `flyte create secret` plus `secrets=[flyte.Secret(...)]`, after
     confirming Union injects app secrets at all.
   - **`flyte.deploy` with commit-SHA versions** in place of `flyte.serve`
     for the admin app, run from CI with a `FLYTE_API_KEY`.
   - **Pin the admin to one replica** (`Scaling(replicas=(1, 1))`).
     `_launched` is in-memory, and scaling to zero puts a cold start on
     the first dashboard load.
   - **Resource ceilings.** Notebook resources are honored as-authored. Cap
     them with `flyte edit settings --domain production` (`task_resource.max.*`),
     after checking that the cap applies to apps and not only tasks.
   - **Custom domain** for the admin (`flyte.app.Domain`).
   - **Admin identity.** A dedicated API key with project-create (and,
     for the Union console handoff, policy/assignment) permissions.
- **Per-user storage isolation.** Every project on the tenant runs as one
   IAM role, so a notebook's own code can read and write every user's
   workspace objects (and all task data). Needs per-project roles scoped to
   each user's prefix, from Union.
- **Union session cookies reach notebook pods.** Union forwards the
   visitor's session cookies to the app. The proxy strips them before
   marimo, but code in a pod could still capture a visiting org member's
   token. Look for a way to have Union drop them for an app, or isolate the
   proxy from notebook code.
- **User onboarding.** Only `stargazerbio` org members get past the login,
   and Union doesn't auto-provision users on first sign-in yet. New users
   need an invite until it does.
- **Devbox app tier without Union auth.** The devbox has no Union login in
   front of apps, so the admin and notebook pods won't authenticate there.
   A dev-only fixed identity would make the app tier testable locally
   again.
- **Union console handoff (per-user project access).** Users click through
   from the dashboard to the Union console to view executions in their own
   project. Users are already Union principals (they signed in), but
   `provision_user()` grants no role binding on their project, so the
   console would show them nothing. Adds role/policy/assignment
   provisioning via `flyteplugins.union.remote`.
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
    remote image builder:** the admin pod cannot build with the local Docker
    builder (see `_build_and_push_notebook_image`). Scoped to workspace
    notebooks first; image-baked tutorials/workflows deferred.
    [`23_notebook_declared_image.md`](./23_notebook_declared_image.md)

## Complete

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
