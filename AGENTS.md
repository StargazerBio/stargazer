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

**Documentation Guidelines**
- No code snippets are to be added to any documents outside of `.opencode/plans/`. Code examples in documentation files like this one become stale as conventions and implementations drift, creating confusion rather than clarity. The codebase itself should be the source of truth for implementation patterns.

## OpenCode Agent Definitions

The `.opencode/agent/` directory contains specialized agent definitions for [OpenCode](https://github.com/sst/opencode), an AI coding assistant. These markdown files define role-specific personas that can be invoked as subagents, each with tailored instructions, temperature settings, and tool permissions.

### Available Agents

| Agent | File | Purpose |
|-------|------|---------|
| **Task** | `task.md` | Implements individual Flyte v2 tasks for bioinformatics tools |
| **Test** | `test.md` | Writes unit and integration tests following TDD approach |
| **Workflow** | `workflow.md` | Composes Flyte v2 tasks into end-to-end pipelines |
| **Code Review** | `code-review.md` | Strict code reviewer that audits for edge cases, UX issues, and data provenance |

### Agent File Format

Each agent file uses YAML frontmatter to configure behavior:
```yaml
---
description: Brief description of the agent's role
mode: subagent
temperature: 0.2  # Lower = more deterministic
tools:
  write: true
  edit: true
  bash: true
---
```

The markdown body contains detailed instructions including:
- Role definition and core principles
- Implementation templates and patterns
- Project-specific rules (imports, async patterns, types)
- Checklists and communication guidelines

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

### Specs

- **`.opencode/context/specs/`** - Concise documentation on the project's design principles
  - **Critical**: Specs must be updated as the project evolves to stay in sync with the current state
  - No code in spec docs - these are high-level references supported by docstrings in the actual functions
  - `filesystem_spec.md` - IpFile metadata system, type/component contracts, task interoperability patterns


## Project Structure

### Directory Organization

The project follows this structure:
- `src/stargazer/` - Main package
  - `tasks/` - Flyte task definitions (one module per tool/function)
  - `workflows/` - Flyte workflow definitions (one module per pipeline)
  - `types/` - Custom Flyte types and dataclasses
  - `utils/` - Utility functions
- `tests/` - Test directory
  - `conftest.py` - Pytest configuration
  - `assets/` - Test fixtures and small data files
  - `unit/` - Unit tests
  - `integration/` - Integration tests
- `.opencode/context/` - Reference materials
- `scratch/` - Scratch materials

### Types Directory (`src/stargazer/types/`)

**Purpose:** Define all input and output dataclasses used across tasks and workflows.

**Guidelines:**
- Create separate modules for different domains (e.g., `reference.py`, `alignment.py`, `variant_calling.py`)
- Use descriptive dataclass names (e.g., `Alignments`, `VariantCallingOutputs`)
- Group related types in the same module
- Use Python dataclasses with type annotations
- Import Flyte I/O types from `flyte.io` (e.g., `File`, `Dir`)

### Tasks Directory (`src/stargazer/tasks/`)

**Purpose:** Define individual Flyte tasks that perform specific operations.

**Guidelines:**
- **Modular Organization:** Separate tasks by tool or functional domain (e.g., `bwa_tasks.py`, `samtools_tasks.py`)
- **Naming Convention:** Use descriptive, action-oriented names
  - Task files: `{tool}_tasks.py` or `{function}_tasks.py`
  - Task functions: `{action}_{tool}` (e.g., `align_with_bwa`, `sort_bam`)
- **One Task Per Function:** Each task should do one thing well
- **Use Structured I/O:** Leverage dataclasses from `types/` for inputs/outputs
- **Resource Specification:** Define appropriate resource requests (CPU, memory, GPU)

### Workflows Directory (`src/stargazer/workflows/`)

**Purpose:** Compose tasks into end-to-end workflows.

**Guidelines:**
- **Modular Organization:** Separate workflows by analysis type or pipeline (e.g., `germline_variant_calling.py`, `somatic_variant_calling.py`)
- **Naming Convention:** Use descriptive, pipeline-oriented names
  - Workflow files: `{analysis_type}_workflow.py` or `{pipeline_name}.py`
  - Workflow functions: `{pipeline_description}` (e.g., `germline_variant_calling_pipeline`)
- **Clear Composition:** Show task dependencies clearly
- **Use Structured I/O:** Leverage dataclasses for workflow inputs/outputs
- **Document Purpose:** Include docstrings explaining the workflow's goal

### Core Concepts

- Main SDK import: `import flyte`
- I/O types: `from flyte.io import File, Dir`
- Task environments: `flyte.TaskEnvironment(name="my_env")`
- Async tasks are preferred for I/O operations
- In v2, there is no separate `@workflow` decorator - workflows are tasks that call other tasks
- Use `asyncio.gather` for parallel execution

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

All imports should use the `stargazer` package name, not relative imports across packages.
