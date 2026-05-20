# Stargazer Roadmap

Upcoming work is ordered — the **next feature is at the top**. Move items into Complete (with a ✅) as they ship.

## Upcoming

1. **Admin app with embedded dashboard.** Single shared FastAPI deployment: OAuth, fork, provisioning, dashboard tile UI, `/launch` broker. Detailed plan: [`16_admin_app_with_dashboard.md`](./16_admin_app_with_dashboard.md).
2. **Per-notebook apps + marimo `--sandbox` inline deps.** Edit/Run click spawns a per-notebook app from a shared static `note` image; Python deps inlined via PEP 723; container-local fork clone on launch; cookie-validating proxy serves workspace `list`/`sync` locally. Detailed plan: [`17_per_notebook_apps.md`](./17_per_notebook_apps.md).
3. **In-notebook local-vs-remote toggle UI.** Formalize the dispatch choice as a reusable `mo.ui` element (radio / segmented control) so individual cells don't need to hardcode `flyte.with_runcontext(mode="local").run` vs `flyte.run`.
4. **Marimo AI features investigation.** Determine what marimo's native AI surface offers (`mo.ai.chat` / similar), whether tool-calling is supported, and how to wire the registry catalog in.
5. **Publish `stargazer` to PyPI.** Once the package is published, notebook PEP 723 headers can pin a version (`stargazer == X.Y.Z`) instead of `[tool.uv.sources] stargazer = { path = "/stargazer", editable = true }`. Unlocks fully reproducible community notebooks without baking the source path.
6. **Upload public assets for quickstart workflow to Pinata.**
7. **Update README with CLI quickstart and bump to alpha status.**
8. **Interactive workflow for generating a DB from existing data in `STARGAZER_LOCAL`.**
9. **Condensed context files for production use (separate from dev).**
10. **Recurring docs-sync job** so architecture docs never go stale against the code.
11. **Agentic PR process** for end-to-end automated review/merge of trusted contributors.
12. **More robust logging.**
    - Per-task tags so logs can be demultiplexed.
    - One logfile per workflow execution.
    - Stop flushing to stdout/err to keep context windows clean.
    - Env vars for log level and a bool to include actual tool-call output.
13. **Data-aware caching.** Flyte's input-hash caching is solid but breaks down for keyword/metadata-based workflows — need a higher-level cache keyed on semantic inputs.

## Complete

- ✅ scRNA preprocessing tutorial rebuild (Asset → Task → Workflow → local → remote). [`archive/15_scrna_tutorial_rebuild.md`](./archive/15_scrna_tutorial_rebuild.md)
- ✅ Integrate marimo as the notebook experience (basic plumbing — per-user provisioning, in-pod execution, tutorial scaffold).
- ✅ Create Stargazer org.
- ✅ Set up GitHub Pages.
- ✅ Exhaustively link docs to code for agent traversal.
