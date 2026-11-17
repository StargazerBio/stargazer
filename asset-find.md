---
title: asset-find
status: done
priority: normal
created: 2026-11-16
pr: 156
---

Asking the asset graph for one asset of a type takes four lines everywhere it's done: `assemble(...)`, filter by `isinstance`, raise if empty, take `[0]`. It's written out four times in `workflows/gatk_data_preprocessing.py` and `workflows/scrna_clustering.py` (read 2026-11-16), and again in the tutorials. A classmethod beside `Asset.store` (ticket [[lean-task-bodies]]) says it in one:

```python
ref = await Reference.find(build="GRCh38")
r2 = await R2.find(sample_id=sample_id, required=False)
```

It's also the line to lead with when showing someone a workflow.

## Plan

- [x] `Asset.find(required=True, **filters)`: `assemble(asset=cls._asset_key, **filters)`, the newest match, raising `ValueError` naming the type and the filters when there's none and it's required. Several matches: newest wins.
- [x] `Asset.find_all(**filters) -> list[Self]` for the typed list.
- [x] The workflows, the Assets tutorial (the Workflows tutorial has no lookup) and `docs/guides/writing-a-workflow.md` use them. `assemble()` stays for mixed-type queries.
- [x] `docs/architecture/types.md` → Assembly.

## Verification recipe: Asset.find

A workflow or notebook asks for one asset of a type in one line, `Reference.find(build=...)`, and gets the newest stored match, or a `ValueError` naming the type and filters, or `None` with `required=False`.

### Sub-features

- F1: `find()` returns the newest match of its type only; `find_all()` every match, newest first.
- F2: no match raises `ValueError: No <Type> found for k='v', ...`; `required=False` returns `None`.
- F3: the Assets tutorial's discovery section renders the sheet it stored via `SampleSheet.find`.
- F4: `prepare_reference` / `preprocess_sample` find their inputs on the cluster (germline workflow on the devbox).
- F5: `scrna_clustering_pipeline` finds the newest raw AnnData, in its task image.

### How to get to it (user POV)

`from stargazer import Reference; await Reference.find(build="GRCh38")` in a notebook cell or a workflow body; the Assets tutorial section 5.

### Driving it

Preconditions: a worktree of the branch; for F4 the devbox set up (`devbox/setup.sh`), `.flyte/config.yaml` linked, `FLYTE_IMAGE_REGISTRY=localhost:30000`.

1. F1, F2: `pixi run pytest tests/assets/test_find.py` → 6 passed.
2. F3: with the verify-stargazer isolated-store env exported, `pixi run marimo export html src/stargazer/notebooks/tutorials/assets.py -o $RUN_DIR/evidence/assets.html` → exit 0, and the HTML renders `found.cid == uploaded_sheet.cid → True`, `assemble()` returned `1` asset of `['SampleSheet']`, and the extras section's `find_all(lab="tutorial_lab")` found it → `True`. Repeat for `tasks.py` and `workflows.py` (they import it) → exit 0.
3. F4: `FLYTE_IMAGE_REGISTRY=localhost:30000 pixi run pytest -m devbox -rP tests/devbox/test_germline.py` → 3 passed.
4. F5: `pixi run python cli/docker_task_tests.py tests/tasks/scrna/test_scrna_clustering_pipeline.py` → 2 passed; and the script below, mounted into the scrna image beside `tests/` (`docker run --rm --platform linux/amd64 -v $PWD/tests:/work/tests:ro -v <script>:/check.py:ro <stargazer-scrna image> python /check.py`) stores two raw AnnData for one sample and runs the pipeline through Flyte's local mode → `root_is_newest_raw: true`, lineage from annotated back to raw, and a missing sample raising `No AnnData found for sample_id='nope', stage='raw'`.

```python
"""Run scrna_clustering_pipeline through Flyte's local mode against an isolated store."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

root = Path(tempfile.mkdtemp())
os.environ.update(
    STARGAZER_LOCAL=str(root / "local"),
    STARGAZER_STORE_ROOT=str(root / "store"),
    STARGAZER_INDEX_URL=str(root / "index.db"),
    PINATA_JWT="",
)

import flyte  # noqa: E402

from stargazer.assets import AnnData  # noqa: E402
from stargazer.workflows.scrna_clustering import scrna_clustering_pipeline  # noqa: E402

FIXTURE = Path("/work/tests/fixtures/scrna/synthetic_200x500.h5ad")


async def seed() -> AnnData:
    """Store the fixture twice under one sample: an old raw and a newer raw."""
    old = root / "old.h5ad"
    import anndata as ad

    a = ad.read_h5ad(FIXTURE)
    a.uns["note"] = "older copy"
    a.write_h5ad(old)
    await AnnData.store(old, sample_id="S1", stage="raw", organism="human")
    return await AnnData.store(FIXTURE, sample_id="S1", stage="raw", organism="human")


newest = asyncio.run(seed())
flyte.init()
run = flyte.with_runcontext(mode="local").run(
    scrna_clustering_pipeline, sample_id="S1", n_top_genes=200, max_pct_mt=80.0
)
run.wait()
out = run.outputs()[0]

import anndata as ad  # noqa: E402

final = ad.read_h5ad(asyncio.run(out.fetch()))
lineage = []
kv = out
from stargazer.assets import assemble  # noqa: E402

by_cid = {a.cid: a for a in asyncio.run(assemble(asset="anndata"))}
while kv.source_cid:
    lineage.append(kv.stage)
    kv = by_cid[kv.source_cid]
print(
    json.dumps(
        {
            "stage": out.stage,
            "n_obs_kv": out.n_obs,
            "n_obs_file": final.n_obs,
            "has_leiden": "leiden" in final.obs,
            "has_markers": "rank_genes_groups" in final.uns,
            "lineage": lineage,
            "root_is_newest_raw": kv.cid == newest.cid,
        }
    )
)
try:
    flyte.with_runcontext(mode="local").run(scrna_clustering_pipeline, sample_id="nope").wait()
    print("missing: no error")
except Exception as e:  # noqa: BLE001
    print("missing:", type(e).__name__, str(e)[-200:])
```

### Evidence (2026-11-16, PR 156)

- F1, F2: `tests/assets/test_find.py` 6 failed on `AttributeError` before the change, 6 passed after; unit tier 327 passed.
- F3: `assets.py`, `tasks.py`, `workflows.py` exports exit 0; renders as above.
- F4: devbox `test_germline.py` 3 passed (runs `rfm5rkwkq22f9hlzd8jf`, `rh7dpfjtzf2kgd8z54ql`, `rgvrv79bphh8fj2vgh27`).
- F5: tasks tier gatk 30 passed, scrna 17 passed; the script printed `{"stage": "annotated", "n_obs_kv": 59, "n_obs_file": 59, "has_leiden": true, "has_markers": true, "lineage": ["annotated", "clustered", "reduced", "featured", "normalized", "qc_filtered"], "root_is_newest_raw": true}` and `missing: ... ValueError: No AnnData found for sample_id='nope', stage='raw'`.

### Gotchas

- `tests/tasks/scrna/test_scrna_clustering_pipeline.py` pinned the old error text; it now matches the message `find()` raises.

## Outcome

Shipped in PR 156 (merge `a14174a`): `Asset.find()` and `Asset.find_all()`, used by the workflows, the Assets tutorial and the writing-a-workflow guide. Verified as under Evidence: F1–F5, including the germline workflow on the devbox and the scRNA pipeline in its image. Nothing left. No review comments.

Related: [[board]], [[lean-task-bodies]], [[sdk-front-door]].
