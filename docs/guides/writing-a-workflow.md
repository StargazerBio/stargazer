# Writing a Workflow

This guide walks through composing tasks into an end-to-end workflow.

## 1. Create the Workflow Module

Add a file in `src/stargazer/workflows/` named after the analysis type:

```python
"""
### My pipeline: align one sample and call its variants.

spec: [docs/architecture/workflows.md](../architecture/workflows.md)
"""

from stargazer.assets import R1, R2, Reference, Variants
from stargazer.assets.asset import assemble
from stargazer.config import gatk_env
from stargazer.tasks import bwa_mem2_mem, haplotype_caller, mark_duplicates, sort_sam


@gatk_env.task
async def my_pipeline(build: str, sample_id: str) -> Variants:
    """One-line description of the pipeline."""
    refs = await assemble(build=build, asset="reference")
    ref = next(a for a in refs if isinstance(a, Reference))

    reads = await assemble(sample_id=sample_id, asset=["r1", "r2"])
    r1 = next(a for a in reads if isinstance(a, R1))
    r2 = next((a for a in reads if isinstance(a, R2)), None)

    alignment = await bwa_mem2_mem(ref=ref, r1=r1, r2=r2)
    alignment = await sort_sam(alignment=alignment)
    alignment = await mark_duplicates(alignment=alignment)
    return await haplotype_caller(alignment=alignment, ref=ref)
```

The reference needs its indexes before it can be aligned against; `prepare_reference` in `gatk_data_preprocessing.py` builds them, and `germline_short_variant_discovery` shows the whole pipeline with a per-sample fan-out.

## 2. Key Rules

- **Accept scalar parameters only** — workflows handle their own assembly via `assemble()`, this keeps the workflow interface flexible for the MCP server while allowing you to create a strong contract with respect to the types *between* tasks
- **One `assemble()` per kind of input** — every filter must match each asset it returns, so a reference (which has a `build`, no `sample_id`) and a sample's reads (the reverse) are queried separately
- **Filter with `isinstance`** — not string matching on asset keys
- **Use `asyncio.gather`** for independent tasks that can run in parallel, such as one branch per sample
- **Workflows are tasks** — in Flyte v2, there's no separate decorator; decorate with the environment whose image runs the workflow body

## 3. Register in the MCP Server

The MCP registry and the [Catalog](../reference/catalog.md#workflows) list the workflows `stargazer.workflows` exports. Import yours in `src/stargazer/workflows/__init__.py` and add it to `__all__`.

## 4. Test

Test a workflow end to end where its tasks run. A GATK workflow needs a cluster, so it's tested on the devbox: `tests/devbox/test_germline.py` seeds a reference and a sample's reads from a pod, runs `germline_short_variant_discovery` the way SDK code submits it, and checks the cohort's VCF from another pod (`uv run --all-extras pytest -m devbox`).
