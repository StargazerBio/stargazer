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

Driven by the devbox test tier, `tests/devbox/test_germline.py`. The session deploys the dashboard and passes the devbox storage settings to every run, so nothing needs exporting first.

Preconditions: the same as [Asset storage on the devbox](./devbox-asset-storage.md).

Steps:

- **Run the tests.** Run `uv run --all-extras pytest -m devbox -rP tests/devbox/test_germline.py`. Both tests pass and it exits `0`. Their shared setup seeds the TP53 reference and NA12829's reads from a pod (`devbox-germline-seed`), then runs the workflow for a fresh cohort, which has to succeed (`devbox-germline-run`).
  - `test_workflow_joint_calls_the_cohort` covers `devbox-germline-joint-call`: the workflow returns a VCF from `joint_call_gvcfs` for the cohort, built from `NA12829` on `GRCh38`.
  - `test_cohort_vcf_found_from_another_pod` covers `devbox-germline-output`: another pod finds the VCF by cohort, and it holds sample `NA12829`, contig `chr17:7658421-7697490`, and at least one record.
- **Proof.** Keep the pytest output. `-rP` prints each run's URL. With the images already built, the workflow run takes about a minute and a half (1m26s measured 2026-10-08).

## Gotchas

- Every Stargazer image is built for x86_64 only. On Apple silicon the devbox runs natively and these pods run emulated, which is slower than Union. Don't start the devbox itself as x86_64: no pod ever starts (`.opencode/reference/devbox_workarounds.md`, "Stargazer pods run x86_64 on an arm64 devbox").
- The first run after a source change builds the GATK image under emulation. When only the source changed, that's the project's install layer; a recipe change rebuilds more.
- The tests bundle code from the repo root, as SDK code does by default. Their pods import `tests.devbox.pod_tasks` from the bundle and `stargazer` from the image.
- After the devbox is recreated, clear Flyte's local cache before the first run (`.opencode/reference/devbox_workarounds.md`, "Laptop-side Flyte cache"). Each session seeds again, so the store and index needn't survive.
- A run with no `PINATA_JWT` secret on the devbox fails before any pod starts, with `none of the secret managers injected secret`. `cli/devbox-setup.sh` creates it.
