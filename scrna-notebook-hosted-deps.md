---
title: The scRNA notebook runs on its own pod's machine
status: backlog
priority: normal
created: 2026-10-26
---

In a hosted notebook, the scRNA notebook's **On this machine** fails at `preprocess`: `qc_filter`'s scrublet step raises `` `threshold` is None and thus scrublet requires `scikit-image` `` (measured 2026-10-26, test account, Edit mode). The notebook's PEP 723 header lists `scanpy`, `anndata`, `matplotlib`, `numpy` and `stargazer`, but not what the `bio` extra adds for scanpy's lazy imports (`scikit-image`, `igraph` for Leiden), so the sandbox venv `marimo --sandbox` builds lacks them. Locally it passes because the checkout's venv has every extra. **On the cluster** is unaffected: the tasks run on `scrna_env`'s image. Likely fix: depend on `stargazer[bio]` in the header instead of listing scanpy's packages; verify with a hosted Run-mode drive on the default setting.
