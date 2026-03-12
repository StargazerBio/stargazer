# Stargazer

**General Guidelines**
- When I say task, I am referring to a Flyte V2 task, not a raw python function
- Tasks are collected into workflows which are just regular tasks calling other tasks, sync or async
- This project uses UV so the appropriate commands are `uv add` and `uv pip install -e .`
- If something is changed that you didn't change, it's not a typo, it's a manual change. I do still write code occassionally..
- Don't use the "if TYPE_CHECKING:" pattern anywhere, Flyte will always check types
- Do not make any git commits unless explicitly requested
- The README is a document written exclusively BY HUMANS FOR HUMANS. Never modify the README. Notify if it is out of spec only.

**Dev Process**
- You will implement features piece by piece in a sequential fashion
- Handle a single case well at first instead of trying to anticipate every way the app will be used
- Do not add complexity until it is needed, which may be never
- Simple tests will be written before implementation and you will pause to ensure they're capturing the right behavior
- Implementation will be tightly scoped so it can be understood
- Tests will run until they pass
- All necessary CLI tools e.g. parabricks, bwa etc, are available in PATH. Use them to generate test assets as needed and alert the user if they are not available.
- When adding a task that wraps a new CLI tool, check the `Dockerfile` bioconda install block to confirm the tool is listed. If it is missing, add it and notify the user.
- **CRITICAL** Do not consider backwards compatibility unless explicitly requested!
- Run `ruff --fix` after every set of changes to satisfy the pre-commit

## OpenCode Agent Definitions

The `.opencode/agent/` directory contains specialized agent definitions for [OpenCode](https://github.com/sst/opencode), an AI coding assistant. These markdown files define role-specific personas that can be invoked as subagents, each with tailored instructions, temperature settings, and tool permissions.

### Available Agents

| Agent | File | Purpose |
|-------|------|---------|
| **Architecture** | `architecture.md` | Designs feature plans in `.opencode/plans/` and maintains docs in `docs/` |
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

### When to Use

- **architecture agent**: When designing a new feature or updating system specs
- **task agent**: When implementing a new bioinformatics tool wrapper
- **test agent**: When writing tests for tasks or workflows
- **workflow agent**: When composing tasks into pipelines
- **code-review agent**: Before merging code, to catch issues early

## Docstring Spec References

Every module in `src/` has two conventions in its module-level docstring:

1. The first line is a `###` heading so it renders prominently in the generated API docs.
2. A `spec:` line at the bottom is a markdown link to the relevant architecture doc:

```
spec: [docs/architecture/types.md](../architecture/types.md)
```

**Rationale:** This serves two purposes:
1. **Diff scanning** — when reviewing recent PRs or commits, an LLM can immediately see which spec doc is affected by any changed module and check whether the docs need updating.
2. **Low-overhead lookup** — when making changes to a specific module, the relevant high-level architecture is one link away without any search.

The `spec:` line is **module-level only** — class and function docstrings do not carry it.

100% docstring coverage is enforced by the `docstr-coverage` pre-commit hook.

## Specs, Plans and Reference Materials

- **`.opencode/reference/flyte_v2_docs.md`** - Official Flyte v2 documentation
- **`.opencode/reference/sdk_examples_concise.md`** - Flyte SDK v2 examples
- **`.opencode/reference/tool_refs/`** - Bioinformatics tool documentation, use as the source of truth for tool parameters and behavior
- **`docs/`** - Project documentation (architecture, guides, reference)
  - **Critical**: Docs must be updated as the project evolves to stay in sync with the current state
  - No code in architecture docs - these are high-level references supported by docstrings in the actual functions
  - Guides are the only docs that contain code examples
- **`.opencode/plans/`** - Step by step instructions for building new features and fixing bugs
  - Only place outside src where code snippets are allowed
  - Keep track of progress and check off completed work as you go

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
- `docs/` - Project documentation
  - `architecture/` - System design and contracts
  - `guides/` - Step-by-step walkthroughs with code examples
  - `reference/` - Auto-generated API reference
- `.opencode/reference/` - Agent-facing reference materials (Flyte docs, tool refs)
- `scratch/` - Scratch materials

### Types Directory (`src/stargazer/types/`)

**Purpose:** Define all input and output dataclasses used across tasks and workflows.

**Guidelines:**
- Create separate modules for different domains (e.g., `reference.py`, `alignment.py`, `variant_calling.py`)
- Use descriptive dataclass names (e.g., `Alignments`, `Variants`)
- Group related types in the same module
- Use Python dataclasses with type annotations

### Tasks Directory (`src/stargazer/tasks/`)

**Purpose:** Define individual Flyte tasks that perform specific operations.

**Guidelines:**
- **Modular Organization:** Separate tasks by tool or functional domain (e.g., `bwa_tasks.py`, `samtools_tasks.py`)
- **Naming Convention:** Use descriptive, action-oriented names
  - Task files: `{tool}.py` or `{function}.py`
  - Task functions: `{action}_{tool}` (e.g., `align_with_bwa`, `sort_bam`)
- **One Task Per Function:** Each task should do one thing well
- **Use Structured I/O:** Leverage dataclasses from `types/` for inputs/outputs
- **Resource Specification:** Define appropriate resource requests (CPU, memory, GPU)

### Workflows Directory (`src/stargazer/workflows/`)

**Purpose:** Compose tasks into end-to-end workflows.

**Guidelines:**
- **Modular Organization:** Separate workflows by analysis type or pipeline (e.g., `germline_variant_calling.py`, `somatic_variant_calling.py`)
- **Naming Convention:** Use descriptive, pipeline-oriented names
  - Workflow files: `{analysis_type}.py` or `{pipeline_name}.py`
  - Workflow functions: `{pipeline_description}` (e.g., `germline_variant_calling_pipeline`)
- **Clear Composition:** Show task dependencies clearly
- **Use Structured I/O:** Leverage dataclasses for workflow inputs/outputs

### Core Concepts

- Main SDK import: `import flyte`
- Task environments: `flyte.TaskEnvironment(name="my_env")`
- Async tasks are preferred for I/O operations
- In v2, there is no separate `@workflow` decorator - workflows are tasks that call other tasks
- Use `asyncio.gather` for parallel execution

## Style and Conventions

- **Paths:** Use `pathlib.Path` for all filesystem operations (e.g., `joinpath`). Use `resolve()` for absolute paths. Only convert to `str` immediately before a subprocess call.
- **Formatting:** Use `ruff` for formatting and correctness checking
- **Imports:** Use the `stargazer` package name, not relative imports across packages. Module level imports should be at the top of the file!!
- **Documentation:** Include docstrings explaining purpose and behavior
- **Resource Awareness:** Specify appropriate resource requests for bioinformatics workloads
- **Learn from V1:** Use `stargazer_flyte_v1/` for workflow logic, but adapt to v2 API
