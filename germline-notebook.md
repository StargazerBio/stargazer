---
title: germline-notebook
status: done
priority: normal
created: 2026-11-02
pr: 125
---

A workflow notebook for germline short variant discovery, in the
`StargazerBio/community-notebooks` repo beside the scRNA pipeline (both
move there in ticket [[notebooks-in-git]]), under `germline/`. There has never been one
(searched the full history of `main`): the germline pipeline exists only as
the SDK workflow `germline_short_variant_discovery`, the MCP's
`run_workflow`, and `tests/devbox/test_germline.py`.

The docs now use it as the headline example of the asset graph ("workflows
take questions, not files", ticket [[asset-graph-docs]]), and a notebook
makes that runnable: pick a build and samples, choose where it runs, and
watch the outputs land in the graph linked back to the reference.

## Shape

Modelled on `scrna_pipeline.py`, a thin parameterized UI over SDK calls:

1. **Inputs from the graph.** A button fetches the `variant_calling_demo`
   bundle (a TP53 slice of GRCh38, build `GRCh38_TP53`, and sample
   NA12829's R1/R2). Then `assemble()` lists the references and samples
   the user's graph holds, as a build dropdown and a sample multiselect,
   so the same notebook runs on their own data or published data with
   nothing to change.
2. **Where it runs.** `run_location()` and `dispatch()` from
   `stargazer.notebooks.ui`, as in the Execution tutorial. The cluster is
   the expected path. Locally the tools are on the image's PATH, but joint
   calling works only in the `amd64` image, so say so where the switch is,
   in product terms.
3. **Run it.** `dispatch(where, germline_short_variant_discovery,
   build=..., sample_ids=..., cohort_id=...)`, with the run's console link
   for a cluster run.
4. **See the graph.** A table of what the run added to the graph: the
   cohort VCF and its index, and per sample the alignments and GVCFs, each
   with its type, key fields and CID. Show the links that exist, e.g.
   `assemble(reference_cid=ref.cid)`. How far back the lineage reaches
   depends on ticket [[provenance-on-every-output]]; show what's there, and
   extend the view when that lands.
5. **Look at the result.** A small summary of the VCF: variant counts by
   type, a table of the first records. Use the `dataviz` skill for any
   chart.

The setup block's `main_name`/`main_description` give the dashboard tile;
it's listed through the community repo's catalog.

## Related

- [[reuse-reference-companions]]: until it lands, every run rebuilds the
  reference's indices. On the TP53 slice that's small, so this doesn't
  wait on it; on a full genome it would dominate the run.
- [[provenance-on-every-output]]: decides how far step 4 can walk back.

## Pieces

- [x] `germline/short-variant-discovery.py` in the community repo,
      importing only public `stargazer` APIs, its demo bundle
      `variant_calling_demo`. The run waits on a button, or `--run` (CI).
      Step 3 has no console link: `dispatch()` returns only the output.
- [x] In `catalog.yaml`, at `be9ab20`'s pin (`352b277`).
- [x] It runs headless on its demo inputs in the released image: the full
      workflow with `--run` on GitHub Actions, 47 sites across 1 sample
      (community-notebooks PR 1, evidence in ticket [[notebooks-in-git]]).
- [x] A tile name the dashboard can open: `main_name` "Germline variants"
      (community-notebooks `352b277`). "Germline short variants" slugs to
      23 characters, over the dashboard's 22, so Open from GitHub refused it.
- [x] Docs: Home's "Workflows take questions, not files" example links to
      it (`docs/index.md`, a small doc edit on stargazer PR 125).

## Outcome

Shipped: the notebook in `StargazerBio/community-notebooks` (`germline/short-variant-discovery.py`, catalog pin `352b277`), and Home's "Workflows take questions, not files" example linking to it, in stargazer PR 125 (merge `51da133`, 2026-11-04). Verified on Union and headless on GitHub Actions (47 sites across 1 sample, community-notebooks PR 1). Its "On this machine" run needs the tools in the notebook's environment: today `micromamba install`, and with ticket [[pixi-notebook-sandbox]] declared in its header. No review comments.

## Verification recipe: germline notebook

A user opens the germline notebook from GitHub on their dashboard, adds the
demo inputs, runs the pipeline on the cluster, and sees what the run added
to their graph and a summary of the cohort VCF.

### Sub-features

- **GN-1** Open from GitHub accepts the notebook and it launches.
- **GN-2** The demo bundle lands in the user's graph and the pickers offer
  `GRCh38_TP53` and NA12829.
- **GN-3** *On the cluster* runs the whole workflow: reference prep, the
  per-sample chain, HaplotypeCaller, joint calling.
- **GN-4** Section 4 lists the run's alignments, indices and GVCFs with their
  links; section 5 summarizes the fetched cohort VCF.
- **GN-5** The outputs are stored under the user's own prefix.

### How to get to it (user POV)

Dashboard → Workspace → paste
`https://github.com/StargazerBio/community-notebooks/blob/<commit>/germline/short-variant-discovery.py`
into Open from GitHub → the Germline variants tile → Run.

### Driving it

Union, test account (infra's `verify-dashboard` skill, from an infra
checkout with `tenant.env` loaded):

1. `uv run python .claude/skills/verify-dashboard/scripts/union_dashboard.py deploy`,
   sign in to the console, open the dashboard with `location.href`.
2. From the dashboard page, `fetch('/workspace/github', {method: 'POST', body})`
   with `link` set to the commit link: 200 and a `germline-variants` tile (GN-1).
3. `fetch('/launch', ...)` with `slug=germline-variants`, `mode=run`,
   `section=workspace`, repeated until it answers `{"url": ...}`; open it.
4. marimo's controls live in shadow roots: find them with a recursive
   `querySelectorAll` over every `shadowRoot`. Click *Add the demo inputs*,
   then the build dropdown holds `GRCh38_TP53` (GN-2). Click the *On the
   cluster* radio, then *Run the pipeline*.
5. The run appears in `u-pryce` as `gatk.germline_short_variant_discovery`,
   after a `build-image` run the first time a release's task image is needed
   in the project. `Action.listall(for_run_name=...)` lists its steps (GN-3).
6. Read sections 3 to 5 from the page's tables (GN-4), and the run's output
   `path` from `Run.get(<run>).outputs()`: `s3://stargazerbio-users/users/<subject>/assets/...` (GN-5).
7. `union_dashboard.py teardown`: every app stopped, `live runs: []`.

### Gotchas

- The devbox can't run it on the cluster: a notebook pod there asks for the
  task's image, and only Union has a remote image builder
  (`ImageBuildError: remote image builder is not enabled`). The notebook
  page showed no error for it.
- The built-in browser blocks a devbox notebook's assets
  (`ERR_BLOCKED_BY_CLIENT` on `*.devbox.stargazer.bio`); a `kubectl
  port-forward` to the pod's queue-proxy port (8012) on localhost loads it.
- A graph that already holds the same reference file under another build
  shows that build until the bundle is added: adding it relabels the file,
  since a CID has one record.
- *Open from GitHub* refuses a `main_name` whose slug is over 22 characters
  with a 400; the button in the page gave no visible sign when driven blind.

### Evidence (2026-11-03)

Union, test account, the released image (v2026.10.30), notebook at
community-notebooks `352b277`:

- GN-1: `/workspace/github` 200, tile `germline-variants`; `/launch` gave
  `https://germline-variants-run-e96a252a.apps.stargazerbio.us-west-2.unionai.cloud`.
  At `6004f43` (name "Germline short variants") the same call was a 400,
  `Notebook names can be at most 22 characters.` (devbox dashboard).
- GN-2: after *Add the demo inputs*, the build dropdown held `GRCh38_TP53`
  and the sample picker NA12829.
- GN-3: run `uh9774jh2s2c497fw4bh` SUCCEEDED, after `build-image`
  `ukq8bmjt6788lfxlwvxd`. Its actions: prepare_reference (samtools_faidx,
  create_sequence_dictionary, bwa_mem2_index), preprocess_sample
  (bwa_mem2_mem, sort_sam, mark_duplicates), haplotype_caller,
  joint_call_gvcfs, all SUCCEEDED.
- GN-4: section 3 "Cohort cohort: 1 sample(s) on GRCh38_TP53, VCF
  bafkreiff57yy…"; section 4 lists the alignments with `reference_cid`,
  their indices by `companion_of`, and the GVCFs by `haplotype_caller`;
  section 5 "47 sites across 1 sample(s)": SNP 25, deletion 15, insertion 8,
  symbolic 3, with genotypes for NA12829.
- GN-5: the output `Variants` (`sample_count=1`, `caller=joint_call_gvcfs`)
  is at `s3://stargazerbio-users/users/387300641116005877/assets/bafkreiff57yy…/cohort_genotyped.vcf`,
  the test account's subject.
- Teardown: `nb-germline-variants-run` and `dashboard` stopped, `live runs: []`.

Devbox: GN-1 and GN-2 passed (opened, launched, bundle added); GN-3 blocked
by the missing image builder (see Gotchas). Local image not rerun.

Related: [[board]], [[notebooks-in-git]], [[provenance-on-every-output]], [[reuse-reference-companions]].
