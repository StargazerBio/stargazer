# Stargazer - Flyte v2 Migration Project

**General Guidelines**
- When I say task, I am referring to a Flyte V2 task, not a raw python function
- Tasks are collected into workflows which are just regular tasks calling other tasks, sync or async
- This project uses UV so the appropriate commands are `uv add` and `uv pip install -e .`
- If something is changed that you didn't change, it's not a typo, it's a manual change. I do still write code occassionally..
- Don't use the "if TYPE_CHECKING:" pattern anywhere, Flyte will always check types

**Dev Process**
- You will implement features piece by piece in a sequential fashion
- Handle a single case well at first instead of trying to anticipate every way the app will be used
- Do not add complexity until it is needed, which may be never
- Commits will be small and carry a short and meaningful messages
- Simple tests will be written before implementation and you will pause to ensure they're capturing the right behavior
- Implementation will be tightly scoped so it can be understood
- Tests will run until they pass
- All necessary CLI tools e.g. parabricks, bwa etc, are available in PATH. Use them to generate test assets as needed and
  alert the user if they are not available.

## Context Directory Reference

The `.opencode/context` directory contains essential reference materials for developing Stargazer on Flyte v2:

### Flyte v2 Documentation & Examples

- **`.opencode/context/flyte_v2_docs.md`** - Official Flyte v2 documentation
  - Core concepts and API reference
  - Migration guide from v1 to v2
  - Best practices for v2 development

- **`.opencode/context/sdk_examples_concise.md`** - Flyte SDK v2 examples
  - Concise code examples and patterns
  - Task and workflow patterns
  - Data type handling examples
  - Resource configuration examples

### Tool References

- **`.opencode/context/tool_refs/`** - Bioinformatics tool documentation
  - Contains detailed reference docs for tools like:
    - DeepVariant, DeepSomatic, MuTect
    - BWA, Minimap2, Samtools
    - Parabricks tools (bqsr, markdup, etc.)
    - STARFusion, HaplotypeCaller, and more
  - Use these as the source of truth for tool parameters and behavior

### Legacy V1 Implementation

- **`.opencode/context/stargazer_flyte_v1/`** - Original Stargazer implementation on Flyte v1
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
├── .opencode/context/       # Reference materials (see above)
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
# src/stargazer/types/reference.py
from dataclasses import dataclass, field
from typing import Self
from pathlib import Path

from stargazer.utils.pinata import default_client, IpFile
from stargazer.utils.query import generate_query_combinations


@dataclass
class Reference:
    """
    A reference genome stored as IPFS files.

    Attributes:
        ref_name: Name of the main reference file
        files: List of IpFile objects containing reference data
    """

    ref_name: str
    files: list[IpFile] = field(default_factory=list)

    async def add_files(
        self,
        file_paths: list[Path],
        keyvalues: dict[str, str] | None = None,
    ) -> None:
        """Upload files and add to reference."""
        if not file_paths:
            raise ValueError("No files to add. file_paths is empty.")

        # Validate all paths exist before uploading
        for path in file_paths:
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")

        # Upload each file and collect IpFile objects
        for path in file_paths:
            ipfile = await default_client.upload_file(path, keyvalues=keyvalues)
            self.files.append(ipfile)

    async def fetch(self) -> Path:
        """Fetch all reference files to local cache."""
        if not self.files:
            raise ValueError("No files to fetch. Reference is empty.")

        # Download all files to cache
        for ipfile in self.files:
            await default_client.download_file(ipfile)

        return default_client.cache_dir
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
"""
BWA tasks for reference genome indexing and alignment.
"""

from datetime import datetime

from stargazer.types import Reference
from stargazer.config import pb_env
from stargazer.utils import _run
from stargazer.utils.pinata import IpFile


@pb_env.task
async def bwa_index(ref: Reference) -> Reference:
    """
    Create BWA index files for a reference genome using bwa index.

    Creates the following index files:
    - .amb (FASTA index file)
    - .ann (FASTA index file)
    - .bwt (BWT index)
    - .pac (Packed sequence)
    - .sa (Suffix array)

    Args:
        ref: Reference object containing the FASTA file to index

    Returns:
        Reference object with BWA index files added

    Reference:
        https://bio-bwa.sourceforge.net/bwa.shtml
    """
    # Fetch all reference files to cache
    await ref.fetch()

    # Get the cached reference file path
    ref_file_path = ref.get_ref_path()

    # Verify the reference file exists
    if not ref_file_path.exists():
        raise FileNotFoundError(f"Reference file {ref.ref_name} not found in cache")

    # BWA index creates 5 files with these extensions
    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]

    # Check if we already have all BWA index files in our files list
    index_file_names = [f"{ref.ref_name}{ext}" for ext in index_extensions]
    existing_names = {f.name for f in ref.files}

    if all(name in existing_names for name in index_file_names):
        return ref

    # Run bwa index in the cache directory
    cmd = ["bwa", "index", str(ref_file_path)]
    stdout, stderr = await _run(cmd, cwd=str(ref_file_path.parent))

    # Get the reference file's metadata to copy over
    ref_file = None
    for f in ref.files:
        if f.name == ref.ref_name:
            ref_file = f
            break

    # Build metadata for index files
    keyvalues = {"type": "reference", "tool": "bwa_index"}
    if ref_file and ref_file.keyvalues:
        if "build" in ref_file.keyvalues:
            keyvalues["build"] = ref_file.keyvalues["build"]

    # Add each index file to the reference
    base_name = ref_file_path.name

    for ext in index_extensions:
        cached_index_path = ref_file_path.parent / f"{base_name}{ext}"

        if not cached_index_path.exists():
            raise FileNotFoundError(
                f"BWA index file {cached_index_path.name} was not created"
            )

        user_facing_name = f"{ref.ref_name}{ext}"

        # Create an IpFile for the index file with metadata
        index_file = IpFile(
            id="local",
            cid="local",
            name=user_facing_name,
            size=cached_index_path.stat().st_size,
            keyvalues=keyvalues,
            created_at=datetime.now(),
            local_path=cached_index_path,
        )

        ref.files.append(index_file)

    return ref
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
# src/stargazer/workflows/parabricks.py
"""
Reference genome indexing workflow.

This workflow chains together:
1. Setup task to create a Reference object from a FASTA file
2. samtools faidx to create FASTA index
3. bwa index to create BWA alignment indices
"""

import flyte

from stargazer.config import pb_env
from stargazer.types import Reference


@pb_env.task
async def wgs_call_snv(ref_name: str) -> Reference:
    """
    Complete reference genome indexing workflow.

    Chains together:
    1. Create Reference object
    2. Run samtools faidx to create .fai index
    3. Run bwa index to create BWA alignment indices

    Args:
        ref_name: Name for the reference

    Returns:
        Reference object with FASTA, .fai, and BWA index files

    Example:
        flyte.init_from_config()
        run = flyte.run(
            wgs_call_snv,
            ref_name="genome.fa"
        )
        print(run.url)
    """
    # Step 1: Hydrate Reference object from Pinata
    ref = await Reference.pinata_hydrate(ref_name=ref_name)

    # # Step 2: Create FASTA index with samtools
    ref = await samtools_faidx(ref)

    # # Step 3: Create BWA index
    ref = await bwa_index(ref)

    return ref


if __name__ == "__main__":
    import pprint

    flyte.init_from_config()
    r = flyte.with_runcontext(mode="local").run(wgs_call_snv, ref_name="GRCh38_TP53.fa")
    r.wait()
    pprint.pprint(r.outputs)
```

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

## Style Preferences

1. **Paths:** Use pathlib.Path for all filesystem operations e.g. joinpath. Use resolve() to get absolute Paths
whenever appropriate. Only convert to str when absolutely necessary, e.g. immediately before a subprocess call.
2. **Formatting:** Use `ruff` for formatting and correctness checking

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
