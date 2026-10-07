---
name: verify-stargazer
description: Drive Stargazer the way a user does and capture evidence that a change works. Covers the marimo notebooks run headless, with SDK tasks executing locally against an isolated asset store. Use before declaring a task, workflow, or notebook change done, or when asked to verify, prove, or reproduce Stargazer behavior.
---

# Verify Stargazer

Proves user-visible behavior on the real surface: a notebook run end to end, with its output assets checked against what they claim to be. A passing pytest run is not this proof.

Read `features/README.md` before driving anything, then follow the matching feature file as the recipe. Adapted from [pstack](https://github.com/cursor/plugins/tree/main/pstack)'s verification skills (MIT).

## Launch

Every run gets its own asset store and evidence directory. All commands run from the repo root.

```bash
export RUN_ID=$(date +%Y%m%d-%H%M%S)
export RUN_DIR=$HOME/.stargazer/verify-runs/$RUN_ID
export STARGAZER_LOCAL=$RUN_DIR/local
export STARGAZER_STORE_ROOT=$RUN_DIR/store
export STARGAZER_INDEX_URL=$RUN_DIR/index.db
export PINATA_JWT=
mkdir -p "$RUN_DIR/evidence"
```

The three `STARGAZER_*` paths are the run's whole asset store: the local cache, the stored files, and the index. Without all three, a run shares the user's defaults under `~/.stargazer/`.

`PINATA_JWT=` must be explicitly empty, not unset. marimo loads `.env`, which holds a real JWT, and an empty value already in the environment wins over it. With it empty, storage has no public tier: every output stays in the run directory and nothing reaches Pinata.

There is no server to keep alive. Each drive is one headless `marimo export html`, which runs every cell and exits.

## Doctor

```bash
.claude/skills/verify-stargazer/scripts/doctor.sh
```

Read-only. `FAIL` lines block every drive. `info` lines name features that are unreachable this run (devbox down, CLI tools missing). Run it before the first drive and again after any failed drive.

## Seed

Notebooks look their inputs up in the asset store. Seed the store from the verify cache rather than letting the notebook fetch from a public IPFS gateway.

```bash
uv run python .claude/skills/verify-stargazer/scripts/seed_scrna.py
```

On a cache miss the script downloads the file once into `~/.stargazer/verify-cache/<cid>`. Later runs never touch the network.

## Drive

```bash
uv run marimo export html <notebook.py> -o "$RUN_DIR/evidence/<feature>.html" > "$RUN_DIR/evidence/<feature>.log" 2>&1
```

Exit `0` means every cell ran. Exit `1` with `Export was successful, but some cells failed to execute` means at least one cell raised. The log names the exception type. The rendered HTML holds the traceback.

Exit `0` is not proof. A notebook can run every cell and still show wrong data. Each feature file names the evidence check that follows the drive.

## Evidence

Proof standards:

- Drive the notebook a user opens, not a script that calls the same tasks.
- Check the stored outputs, not only the rendered page. `check_anndata.py` compares every AnnData asset's `n_obs` keyvalue with the file it points at, and flags a sample missing from a stage.
- Record the export exit code, the check output, and the feature ID.

Evidence lives in `$RUN_DIR/evidence/` and survives cleanup.

## Cleanup

```bash
rm -rf "$RUN_DIR/local" "$RUN_DIR/store" "$RUN_DIR"/index.db*
```

This removes the run's asset store, which holds hundreds of MB per scRNA run. It never touches `$RUN_DIR/evidence/`, `~/.stargazer/verify-cache/`, or the user's own store under `~/.stargazer/`. Confirm the evidence still exists after cleanup.

## Helpers

| Script | Does |
|---|---|
| `scripts/doctor.sh` | Read-only health check. Exit 1 on a blocking failure |
| `scripts/seed_scrna.py` | Seeds the run's store and index with the `scrna_demo` raw samples |
| `scripts/check_anndata.py [stage ...]` | Checks AnnData assets against their files. Exit 1 on a mismatch or a sample missing from a stage |
