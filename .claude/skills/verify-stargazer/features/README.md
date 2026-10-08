# Stargazer verification map

The maintained source for verifying Stargazer's user-facing behavior. Read this index before driving anything, then use the matching feature file as the recipe.

## Baseline preconditions

- The Launch block in `../SKILL.md` has run, so `RUN_DIR`, `STARGAZER_LOCAL`, `STARGAZER_STORE_ROOT`, `STARGAZER_INDEX_URL`, and an empty `PINATA_JWT` are exported.
- `scripts/doctor.sh` exits `0`.
- Never point the `STARGAZER_*` storage paths at the user's defaults under `~/.stargazer/`.

## Driving conventions

- Start every recipe from a freshly seeded run directory unless its preconditions say otherwise.
- Drive notebooks with `marimo export html`. Treat every command as literal.
- Run the evidence check named in the feature file after every drive, even when the export exits `0`.

## Proof and skip reporting

- Notebook proof includes the export exit code, the log, and the evidence check output.
- Record the feature ID with every artifact.
- Report an unreachable feature with the doctor line that blocked it. Do not report it as verified through a different path.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior, then four H2 sections in this order: `Sub-features`, `How to get to it (user POV)`, `Driving it with marimo export`, `Gotchas`.

## Features

- [scRNA-seq pipeline notebook](./scrna-pipeline.md) covers loading the demo samples, the fan-out of preprocessing and clustering, and the per-sample summary.

## Not yet mapped

Add a file here once a feature has been driven end to end.

- **Tutorial notebooks** (`notebooks/tutorials/`). Reachable locally.
- **MCP server tools** (`list_tasks`, `run_task`, `query_files`). Reachable locally.
- **Germline variant calling** (`workflows/`). Needs `bwa`, `samtools`, and `gatk` on PATH, or the devbox.
- **Hosted app** (`app/`: sign-in, notebook launch, asset manager). Needs the devbox, set up per `cli/devbox-setup.sh`.
