---
title: lean-task-bodies
status: review
priority: normal
created: 2026-11-09
pr: 148
---

A task body should read as: fetch inputs, run the tool, store the output. Today each of the ~25 tasks carries the same ceremony around those three lines, found in a review of the core (2026-11-09; counts are `grep` over `src/stargazer/tasks`):

- **Scratch space through the storage client.** Every task imports `stargazer.utils.storage as _storage` only to read `_storage.default_client.local_dir`, and writes its output straight into that shared root under a name like `<sample_id>.g.vcf`. Two tasks running in one process for the same sample (a notebook's local run of two references) write the same file.
- **Two steps to store an output.** `gvcf = Variants()` then `await gvcf.update(path, sample_id=...)`: 26 of the 46 `update()` calls are this pair. `update` reads as a metadata edit, and it skips `None` values silently.
- **Checks the next line already makes.** 26 `if not output.exists(): raise FileNotFoundError(...)` blocks after a tool run. `_run` raises on a non-zero exit, and storing a missing file raises `FileNotFoundError` naming it.
- **Logging by hand.** 63 `logger.info(x.to_dict())` lines at the top and bottom of task bodies.
- **A private name as the public API.** Tasks import `_run` from `stargazer.utils`.
- **A proxy class for a lazy singleton.** `storage._LazyClient` stands in for a `StorageClient` (with a `type: ignore`) so the client is built after Flyte injects `PINATA_JWT`.

One PR, since every piece touches every task.

## Plan

On `refactor/lean-task-bodies`.

- [x] `Asset.store(path, **fields)`, a classmethod: builds the asset from `fields`, uploads `path`, returns it. `gvcf = await Variants.store(output_gvcf, sample_id=..., build=ref.build)`. Unknown fields raise as they do on assignment; `None` is not special. `update()` goes: re-storing an existing instance is `await default_client.upload(asset, path)`, which the few non-task callers already could use (check each of the 20 remaining call sites; a notebook cell that teaches `update` is rewritten to `store`).
- [x] `stargazer.utils.scratch_dir() -> Path`: a fresh directory under `STARGAZER_LOCAL/scratch/` (`tempfile.mkdtemp`), one per call, so a task's outputs can't collide with another's. Tasks take their output directory from it and stop importing `stargazer.utils.storage`.
- [x] `_run` becomes `run`. It logs the command as now. The existence checks after it go, except where a tool can exit 0 without writing its output (name each kept one in a comment).
- [x] The `logger.info(x.to_dict())` lines go. `Asset.store` logs one line per stored asset (`cid`, name, type), which is the record a run needs.
- [x] `get_client()` is `functools.cache`d and `_LazyClient`/`default_client` go; callers use `get_client()`. Tests swap the client by patching `get_client` (one fixture in `tests/conftest.py`), not a module attribute.
- [x] Docs and guides: `docs/guides/writing-a-task.md`, the tasks tutorial notebook, `docs/architecture/tasks.md` and `types.md`, the `tasks-and-workflows` skill's template.

Assumptions made instead of asked: `store` is a classmethod on `Asset` (not a free function) so the type reads first at the call site; scratch directories aren't cleaned up, as now (a pod's disk goes with it, and a local user's `STARGAZER_LOCAL` is theirs to clear).

## Evidence (2026-11-10)

PR 148. Unit tier 291 passed; tasks tier 30 passed in the gatk image and 17 in the scrna image; devbox tier 7 passed (all measured). Germline run `r2rvb2wlbn47gvfng66r` on the devbox ended in a cohort VCF with 10 `Stored` lines in its pods' logs for its 10 outputs. No existence check was kept as "tool can exit 0 without its output". `scratch_dir()` takes its root from the client's `local_dir` (which is `STARGAZER_LOCAL`), so a test's patched client covers it.

## Verification recipe

STORED-LINES: a workflow's pods log one `Stored <type> <name> <cid>` line per output, and nothing else about its assets.

1. With the devbox up and `FLYTE_IMAGE_REGISTRY=localhost:30000`, from the worktree (its `.flyte` linked): `pixi run pytest -m devbox tests/devbox/test_germline.py`. Passes: all pass.
2. For the newest run with more than five actions, `flyte --config .flyte/config.yaml get logs <run> <action>` for each action, joined onto one line (the log wraps), then `grep -oE "Stored +[a-z_]+ +[^ ]+"`. Passes: one line per output file (alignments and their indexes, the duplicate metrics, the GVCF and the cohort VCF with their indexes). Fails as on `main`: no `Stored` line, and a `to_dict()` dump per input and output.

Related: [[board]], [[asset-core-tidy]], [[task-environment-factory]], [[provenance-on-every-output]].
