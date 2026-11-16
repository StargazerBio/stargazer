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
from stargazer.tasks.gatk.env import gatk_env
from stargazer.tasks import bwa_mem2_mem, haplotype_caller, mark_duplicates, sort_sam


@gatk_env.task
async def my_pipeline(build: str, sample_id: str) -> Variants:
    """One-line description of the pipeline."""
    ref = await Reference.find(build=build)
    r1 = await R1.find(sample_id=sample_id)
    r2 = await R2.find(sample_id=sample_id, required=False)

    alignment = await bwa_mem2_mem(ref=ref, r1=r1, r2=r2)
    alignment = await sort_sam(alignment=alignment)
    alignment = await mark_duplicates(alignment=alignment)
    return await haplotype_caller(alignment=alignment, ref=ref)
```

The reference needs its indexes before it can be aligned against; `prepare_reference` in `gatk_data_preprocessing.py` builds them, and `germline_short_variant_discovery` shows the whole pipeline with a per-sample fan-out.

## 2. Key Rules

- **Accept scalar parameters only** — workflows look up their own inputs, this keeps the workflow interface flexible for the MCP server while allowing you to create a strong contract with respect to the types *between* tasks
- **One `find()` per input** — `Reference.find(build=...)` returns the newest stored `Reference` matching every filter and raises when there's none; `required=False` returns `None` instead, for an optional input like `R2`. `find_all()` returns every match, newest first, and `assemble()` queries across types
- **Use `asyncio.gather`** for independent tasks that can run in parallel, such as one branch per sample
- **Workflows are tasks** — in Flyte v2, there's no separate decorator; decorate with the environment whose image runs the workflow body

## 3. Register in the MCP Server

The MCP registry and the [Catalog](../reference/catalog.md#workflows) list the workflows `stargazer.workflows` exports. Import yours in `src/stargazer/workflows/__init__.py` and add it to `__all__`.

## 4. Test

Test a workflow end to end where its tasks run. A GATK workflow needs a cluster, so it's tested on the devbox: `tests/devbox/test_germline.py` seeds a reference and a sample's reads from a pod, runs `germline_short_variant_discovery` the way SDK code submits it, and checks the cohort's VCF from another pod (`pixi run pytest -m devbox`).
