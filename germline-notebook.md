---
title: germline-notebook
status: doing
priority: normal
created: 2026-11-02
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

- [x] `germline/short-variant-discovery/notebook.py` in the community
      repo's first commit (bundle from PR 121's session), importing only
      public `stargazer` APIs, naming `variant_calling_demo` in its
      `meta.yaml`. The run waits on a button, or `--run` (CI). Step 3 has
      no console link: `dispatch()` returns only the output.
- [x] In `catalog.yaml`.
- [x] It runs headless on its demo inputs in the released image: the full
      workflow with `--run` on GitHub Actions, 47 sites across 1 sample
      (community-notebooks PR 1, evidence in ticket [[notebooks-in-git]]).
- [ ] Docs: the Asset Graph page can link to it as the runnable version of
      its germline example.

## Verification recipe

- Local image, `amd64`: `docker run` the release image, open the notebook
  from the community repo (Open from GitHub, or a mounted checkout) in run
  mode, fetch the bundle, run *On this machine*
  with NA12829 on `GRCh38_TP53`; the cohort VCF appears in step 4 and its
  summary in step 5.
- Devbox: the same with *On the cluster*; the run's graph shows the
  per-sample fan-out and joint calling.
- Union, test account: run on the cluster from a hosted notebook, check
  the outputs are under the user's prefix, then tear down the notebook app
  and confirm no runs are left.

Related: [[board]].
