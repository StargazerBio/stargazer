# Germline variant calling on the devbox

`germline_short_variant_discovery` runs on the local devbox the way it runs on Union, with every step in its own pod. Given a reference and one sample's paired reads in the asset store, it indexes the reference, aligns the reads with bwa-mem2, sorts and marks duplicates, calls the sample's GVCF with HaplotypeCaller, and joint-genotypes the cohort. Each output is stored as an asset, and the cohort's VCF can be found from any pod with `assemble()`.

## Sub-features

- `devbox-germline-seed` stores the TP53 reference and NA12829's paired reads from a pod.
- `devbox-germline-run` runs the workflow from SDK code on this machine (`flyte.init_from_config()` from the repo root, then `flyte.run(...)`), each step in a pod on `gatk_env`'s image.
- `devbox-germline-joint-call` joint-genotypes over every contig in the reference, through GenomicsDB, which runs only on x86_64.
- `devbox-germline-output` finds the cohort's VCF from another pod and reads it back.

## How to get to it (user POV)

- With the devbox up and the dashboard deployed (see [Asset storage on the devbox](./devbox-asset-storage.md)), export the three devbox storage settings and keep the store port-forward open, as in `docs/guides/contributing.md` → Running on the Devbox.
- Store a reference with `build` set and a sample's R1 and R2 under one `sample_id`, then call `flyte.run(germline_short_variant_discovery, build=..., sample_ids=[...], cohort_id=...)`.

## Driving it

Preconditions:

- Everything [Asset storage on the devbox](./devbox-asset-storage.md) lists, plus a deployed dashboard: `curl -s -o /dev/null -w "%{http_code}" http://dashboard-flytesnacks-development.devbox.stargazer.bio:30081/` prints `200`.
- `cli/devbox-setup.sh` has run since the devbox was created, so its verify step printed `✓ PINATA_JWT secret present`.
- These are exported, exactly:

  ```bash
  export STARGAZER_STORE_ROOT=s3://flyte-data/stargazer
  export STARGAZER_INDEX_URL=http://dashboard-flytesnacks-development.flyte.svc.cluster.local
  export STARGAZER_OWNER=devbox-user
  ```

The script below opens the store port-forward itself. Each subcommand prints its run URL.

Steps:

- **Seed.** Run `uv run --all-extras python .claude/skills/verify-stargazer/scripts/devbox_germline.py seed`. It ends with the three CIDs it stored (`reference`, `r1`, `r2`) and exits `0`. Seeding twice stores the same CIDs again, which is harmless. Covers `devbox-germline-seed`.
- **Run.** Run `uv run --all-extras python .claude/skills/verify-stargazer/scripts/devbox_germline.py run <cohort>` with a cohort ID not used before. It ends with `output: Variants(...)` and exits `0`; a failed run raises and exits non-zero. In the run's page, every action succeeded, `joint_call_gvcfs` included. With the image already built, the run takes about a minute and a half (1m26s measured 2026-10-08). Covers `devbox-germline-run` and `devbox-germline-joint-call`.
- **Check.** Run `uv run --all-extras python .claude/skills/verify-stargazer/scripts/devbox_germline.py check <cohort>`. It prints the VCF's keyvalues (`sample_id` is the cohort), its samples, its record count and contigs, then `ok`, and exits `0`. `samples` is `["NA12829"]`, `records` is above zero, and `contigs` is `["chr17:7658421-7697490"]`. Covers `devbox-germline-output`.
- **Proof.** Keep all three outputs and the run URLs.

## Gotchas

- Every Stargazer image is built for x86_64 only. On Apple silicon the devbox runs natively and these pods run emulated, which is slower than Union. Don't start the devbox itself as x86_64: no pod ever starts (`.opencode/reference/devbox_workarounds.md`, "Stargazer pods run x86_64 on an arm64 devbox").
- The first `seed` or `run` after a source change builds the GATK image under emulation. When only the source changed, that's the install layer; a recipe change rebuilds more.
- `run` bundles code from the repo root, as SDK code does by default. `seed` and `check` bundle only this skill's `scripts/` directory, and their pods import `stargazer` from the image.
- After the devbox is recreated, clear Flyte's local cache before the first run (`.opencode/reference/devbox_workarounds.md`, "Laptop-side Flyte cache"), and seed again: the store and the index went with it.
- A run with no `PINATA_JWT` secret on the devbox fails before any pod starts, with `none of the secret managers injected secret`. `cli/devbox-setup.sh` creates it.
