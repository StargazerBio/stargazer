# Stargazer - Flyte v2 Migration Project

**General Guidelines**
- When I say task, I am referring to a Flyte V2 task, not a raw python function
- Tasks are collected into workflows which are just regular tasks calling other tasks, sync or async

## Context Directory Reference

The `/context` directory contains essential reference materials for developing Stargazer on Flyte v2:

### Flyte v2 Documentation & Examples

- **`context/flyte_v2_docs.md`** - Official Flyte v2 documentation
  - Core concepts and API reference
  - Migration guide from v1 to v2
  - Best practices for v2 development

- **`context/sdk_examples_concise.md`** - Flyte SDK v2 examples
  - Concise code examples and patterns
  - Task and workflow patterns
  - Data type handling examples
  - Resource configuration examples

### Tool References

- **`context/tool_refs/`** - Bioinformatics tool documentation
  - Contains detailed reference docs for tools like:
    - DeepVariant, DeepSomatic, MuTect
    - BWA, Minimap2, Samtools
    - Parabricks tools (bqsr, markdup, etc.)
    - STARFusion, HaplotypeCaller, and more
  - Use these as the source of truth for tool parameters and behavior

### Legacy V1 Implementation

- **`context/stargazer_flyte_v1/`** - Original Stargazer implementation on Flyte v1
  - Reference for workflow logic and structure
  - Task organization patterns
  - Type definitions (see `types/` subdirectory)
  - Existing tasks (see `tasks/` subdirectory)
  - Workflow compositions (see `workflows/` subdirectory)
  - **Note:** Do not copy v1 syntax directly; adapt patterns to v2 API
  
## Scratch Directory

The `scratch` directory is intended for one-off testing and hypothesis validation. It contains nothing persistent and will not be committed to git.

## Project Structure

### Directory Organization

```
stargazer/
├── src/
│   └── stargazer/
│       ├── __init__.py
│       ├── tasks/           # Flyte task definitions
│       │   ├── __init__.py
│       │   ├── parabricks.py
│       │   ├── samtools.py
│       │   └── ...
│       ├── workflows/       # Flyte workflow definitions
│       │   ├── __init__.py
│       │   ├── parabricks.py
│       │   └── ...
│       ├── types/           # Custom Flyte types and dataclasses
│       │   ├── __init__.py
│       │   ├── parabricks.py
│       │   └── ...
│       └── utils/           # Utility functions
│           ├── __init__.py
│           └── ...
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── assets/              # Test fixtures and small data files
│   ├── unit/                # Unit tests
│   │   └── __init__.py
│   └── integration/         # Integration tests
│       └── __init__.py
├── context/                 # Reference materials (see above)
├── scratch/                 # Scratch materials (see above)
├── Dockerfile
├── pyproject.toml
└── README.md
```

### Types Directory (`src/stargazer/types/`)

**Purpose:** Define all input and output dataclasses used across tasks and workflows.

**Guidelines:**
- Create separate modules for different domains (e.g., `reference.py`, `alignment.py`, `variant_calling.py`)
- Use descriptive dataclass names (e.g., `Alignments`, `VariantCallingOutputs`)
- Group related types in the same module
- Use Python dataclasses with type annotations
- Import Flyte I/O types from `flyte.io` (e.g., `File`, `Dir`)

**Example Module Structure:**
```python
# src/stargazer/types/alignment.py
from dataclasses import dataclass
from flyte.io import File

@dataclass
class AlignmentInputs:
    fastq_r1: File
    fastq_r2: File
    reference_genome: File

@dataclass
class AlignmentOutputs:
    aligned_bam: File
    alignment_metrics: File
```

### Tasks Directory (`src/stargazer/tasks/`)

**Purpose:** Define individual Flyte tasks that perform specific operations.

**Guidelines:**
- **Modular Organization:** Separate tasks by tool or functional domain
  - Examples: `bwa_tasks.py`, `samtools_tasks.py`, `deepvariant_tasks.py`
- **Naming Convention:** Use descriptive, action-oriented names
  - Task files: `{tool}_tasks.py` or `{function}_tasks.py`
  - Task functions: `{action}_{tool}` (e.g., `align_with_bwa`, `sort_bam`)
- **One Task Per Function:** Each task should do one thing well
- **Use Structured I/O:** Leverage dataclasses from `types/` for inputs/outputs
- **Resource Specification:** Define appropriate resource requests (CPU, memory, GPU)

**Example Task Module:**
```python
# src/stargazer/tasks/bwa.py
import flyte
from flyte.io import File
from stargazer.types.alignment import AlignmentInputs, AlignmentOutputs

env = flyte.TaskEnvironment(name="bwa")

@env.task(
    requests={"cpu": "8", "mem": "32Gi"},
    limits={"cpu": "16", "mem": "64Gi"}
)
async def align_with_bwa(inputs: AlignmentInputs) -> AlignmentOutputs:
    """Align paired-end reads using BWA-MEM."""
    # Download input files
    r1_path = await inputs.fastq_r1.download()
    r2_path = await inputs.fastq_r2.download()
    ref_path = await inputs.reference_genome.download()

    # Task implementation (run BWA alignment)
    # ... alignment logic ...

    # Upload output files
    bam_file = await File.from_local("aligned.bam")
    metrics_file = await File.from_local("metrics.txt")

    return AlignmentOutputs(
        aligned_bam=bam_file,
        alignment_metrics=metrics_file
    )
```

### Workflows Directory (`src/stargazer/workflows/`)

**Purpose:** Compose tasks into end-to-end workflows.

**Guidelines:**
- **Modular Organization:** Separate workflows by analysis type or pipeline
  - Examples: `germline_variant_calling.py`, `somatic_variant_calling.py`, `rna_seq_analysis.py`
- **Naming Convention:** Use descriptive, pipeline-oriented names
  - Workflow files: `{analysis_type}_workflow.py` or `{pipeline_name}.py`
  - Workflow functions: `{pipeline_description}` (e.g., `germline_variant_calling_pipeline`)
- **Clear Composition:** Show task dependencies clearly
- **Use Structured I/O:** Leverage dataclasses for workflow inputs/outputs
- **Document Purpose:** Include docstrings explaining the workflow's goal

**Example Workflow Module:**
```python
# src/stargazer/workflows/germline_variant_calling.py
import flyte
from stargazer.tasks.bwa import align_with_bwa
from stargazer.tasks.samtools import sort_bam, index_bam
from stargazer.tasks.deepvariant import call_variants
from stargazer.types.workflows import GermlineWorkflowInputs, GermlineWorkflowOutputs

env = flyte.TaskEnvironment(name="germline_pipeline")

@env.task
async def germline_variant_calling_pipeline(
    inputs: GermlineWorkflowInputs
) -> GermlineWorkflowOutputs:
    """
    Complete germline variant calling pipeline:
    1. Align reads with BWA
    2. Sort and index BAM
    3. Call variants with DeepVariant
    """
    # In v2, tasks call other tasks directly
    alignment = await align_with_bwa(inputs.alignment_inputs)
    sorted_bam = await sort_bam(alignment.aligned_bam)
    indexed_bam = await index_bam(sorted_bam)
    variants = await call_variants(indexed_bam, inputs.reference)

    return GermlineWorkflowOutputs(
        vcf=variants.vcf,
        bam=indexed_bam
    )

# For running the workflow
if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.run(germline_variant_calling_pipeline, inputs=my_inputs)
    print(run.url)
```

## Key Flyte v2 Patterns

### Core Imports

```python
import flyte                    # Main SDK
from flyte.io import File, Dir  # I/O types (NOT flytekit!)

env = flyte.TaskEnvironment(name="my_env")
```

### Task Definition

```python
# Async tasks (preferred for I/O operations)
@env.task(
    requests={"cpu": "4", "mem": "16Gi", "gpu": "1"},
    limits={"cpu": "8", "mem": "32Gi", "gpu": "1"}
)
async def my_task(input_file: File) -> File:
    # Download inputs
    local_path = await input_file.download()

    # Process...

    # Upload outputs
    return await File.from_local("output.txt")

# Sync tasks (for CPU-bound operations)
@env.task
def sync_task(x: int) -> int:
    return x * 2
```

### Workflows (Tasks Calling Tasks)

In v2, there is **no separate `@workflow` decorator**. Workflows are simply tasks that call other tasks:

```python
@env.task
async def my_workflow(input_data: File) -> File:
    # Call tasks directly with await
    processed = await task1(input_data)
    result = await task2(processed)
    return result
```

### Parallelism with asyncio

```python
import asyncio

@env.task
async def parallel_workflow(files: list[File]) -> list[File]:
    # Process files in parallel
    results = await asyncio.gather(*[process_file(f) for f in files])
    return results
```

### Running Tasks

```python
if __name__ == "__main__":
    # Initialize connection
    flyte.init_from_config()

    # Run remotely (default)
    run = flyte.run(my_task, input_file=my_file)
    print(run.url)

    # Run locally for testing
    run = flyte.with_runcontext(mode="local").run(my_task, input_file=my_file)
```

## Development Principles

1. **Refer to Context First:** Always check context documentation before implementing
2. **Follow v2 Patterns:** Use examples from `sdk_examples_concise.md` for v2 syntax
3. **Use Async/Await:** Prefer async tasks for I/O-heavy bioinformatics operations
4. **Modular Design:** Keep files focused and modules logically separated
5. **Type Safety:** Use dataclasses and type annotations throughout
6. **Resource Awareness:** Specify appropriate resource requests for bioinformatics workloads
7. **Documentation:** Include docstrings explaining purpose and behavior
8. **Learn from V1:** Use `stargazer_flyte_v1/` for workflow logic, but adapt to v2 API

## Quick Reference Workflow

When implementing a new pipeline component:

1. Check `context/tool_refs/` for tool-specific documentation
2. Review `context/flyte_v2_docs.md` for API patterns
3. Look at `context/sdk_examples_concise.md` for code examples
4. Reference `context/stargazer_flyte_v1/` for existing workflow logic
5. Define types in `src/stargazer/types/` (create new module if needed)
6. Implement tasks in `src/stargazer/tasks/` (one module per tool/function)
7. Compose workflows in `src/stargazer/workflows/` (one module per pipeline)
8. Add unit tests in `tests/unit/` and integration tests in `tests/integration/`

## Import Conventions

All imports should use the `stargazer` package name:

```python
# Correct
from stargazer.types.parabricks import Fq2BamOutputs
from stargazer.tasks.samtools import samtools_env

# Incorrect - don't use relative imports across packages
from types.parabricks import Fq2BamOutputs
from ..tasks.samtools import samtools_env
```
