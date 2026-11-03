---
title: pixi-notebook-sandbox
status: maybe
priority: normal
created: 2026-11-03
---

A notebook declares its Python packages in its PEP 723 header, and they reproduce wherever it opens. Its command-line tools (gatk, samtools, bwa) have no such home: since ticket [[warm-uv-cache]] the notebook image carries none, and a notebook that runs one in its own process, like the community germline notebook on "On this machine", relies on the user running `micromamba install` or on a hosted `main_env` image. Nothing in the notebook records which tools it needs.

marimo 0.25.1, the version the image pins, has a pixi sandbox backend (`marimo/_environments/pixi.py`, `--sandbox=pixi`): a notebook's environment is a conda environment built from its own header with `pixi install --script`, and marimo adds packages with `pixi add --script --pypi`. Its kernel overlay (`--with marimo`) rides uv through `pixi exec`, chaining the conda prefix's site-packages. If the header can list conda packages (bioconda's `gatk4`, `samtools`) beside `stargazer-bio`, the tools travel with the notebook, locally and hosted, and the project keeps uv everywhere else. This is a spike: decide whether to switch the notebook sandbox, not do it.

## Questions

- How pixi's script metadata declares conda dependencies and channels (conda-forge, bioconda) in a PEP 723 header, and whether marimo's backend reads them.
- Whether pixi takes the editable path source the headers use today (`stargazer-bio = { path = "/stargazer", editable = true }` under `[tool.uv.sources]`), or how it says the same.
- Cold and warm open times against uv's: a core notebook, and germline with gatk4 (which brings a JVM). Whether a pixi cache can be warmed in the image the way `/opt/uv-cache` is, and what it adds to the image.
- Whether the `--with marimo` overlay works over the conda prefix in our image (marimo's comment says it verified the chaining; check it here).
- What changes for the launch script (`--sandbox=pixi`), the image (pixi in it), the existing built-in and community headers, and the docs that say headers hold Python packages only.

## Spike

Build the image with pixi added and the launch script on `--sandbox=pixi`. Give a copy of the germline notebook a header that declares its tools, open it locally from a fresh container, and run it "On this machine". Time the open against the current uv image, and record what the header had to look like.

Related: [[board]], [[warm-uv-cache]], [[local-notebook-images]], [[layered-notebook-image-cache]], [[marimo-sandbox]].
