# Platform Architecture Plan

## Overview

Stargazer's user-facing platform is a set of surfaces unified by a shared API and IPFS asset layer. Marimo is the hosted frontend for researchers. Other surfaces are linked to, not rebuilt.

## Surfaces

| Surface | Owned? | Role |
|---------|--------|------|
| **Marimo** | Yes | Hosted frontend — explore, prototype, run, visualize |
| **MCP server** | Yes | Programmatic AI interface — any MCP client (Claude Code, Cursor, etc.) |
| **Union UI** | No (link out) | Workflow execution monitoring, logs, history |
| **GitHub** | No (link out) | Code contribution, PR review, discussion |
| **Code editor** | No (opt-in) | Full authoring for power users (VS Code Server, local clone) |

We build and own two things: the marimo notebook experience and the MCP server. Everything else is an existing product we link to.

## Unifying Layer

All surfaces share two things:

1. **The stargazer API** — tasks, workflows, types, utils. Same code runs everywhere.
2. **IPFS assets** — content-addressed storage. A CID is a CID whether you're in a notebook, the Union UI, or a terminal.

The UI doesn't unify the experience — the data and operations underneath do.

## Marimo as Hosted Frontend

Marimo gives us a lightweight, Python-native notebook environment that runs as a Flyte App. It handles:

- Interactive exploration and visualization
- Running tasks and workflows via direct Python imports
- Prototyping new task logic in cells
- AI-assisted authoring via built-in chat panel with custom rules

It links out to spokes when deeper tooling is needed:

- A task execution shows a **"View in Union"** link for monitoring
- An exported task shows a **"View PR"** link once submitted to GitHub
- Power users can clone the repo and use a full editor

### AI Chat in Marimo

Marimo's built-in chat panel supports custom rules via `marimo.toml` `[ai] rules`. We inject stargazer authoring conventions declaratively so every researcher gets a stargazer-aware AI assistant without any custom backend code. The rules cover task patterns, asset types, workflow composition, and project conventions.

**Not using custom MCP server in marimo** — marimo doesn't yet support custom MCP server configuration (only built-in presets). When this ships upstream, the stargazer MCP server can be wired in as a one-line config change. Until then, the MCP server serves developers via coding tools.

### Notebooks Never Export

The dependency graph is strictly one-directional. Notebooks import from `stargazer.*` but are never a dependency of production code. This keeps the module graph clean and means notebook changes cannot break tasks or workflows.

## MCP Server

The MCP server is the programmatic interface to stargazer. It exposes tools for task discovery, execution, asset management, and workflow orchestration. Any AI client that speaks MCP can use it:

- Claude Code, Cursor, Windsurf, VS Code Copilot (today)
- Marimo chat panel (when custom MCP support ships)

The MCP server and marimo serve overlapping functions through different interfaces — one conversational, one visual. They're peers, not parent-child.

## Contribution Flow

Every user is naturally a contributor. Two types of contributions, two paths:

### Data Contributions (frictionless)

Researcher runs a task, gets results, publishes to IPFS. No git, no PR, no review. The CID is the contribution. Anyone can reference it.

### Code Contributions (structured)

Researcher prototypes a task in a notebook cell. To contribute it back:

1. **Export** from marimo — bundles cell logic + metadata into a structured artifact
2. **Submit** — server-side flow uses the researcher's GitHub OAuth token to fork, run `promote-task` extraction, create a branch, and open a PR
3. **Review** happens on GitHub — first-class tooling already exists, no need to rebuild

The notebook never becomes a git client. It produces a well-shaped artifact. A server-side process handles the GitHub mechanics. GitHub handles review.

### Auth

Users log in to the hosted version (Union) with GitHub OAuth. This gives us:

- Identity for per-user state (scratch notebooks, exported artifacts)
- A GitHub token for the PR creation flow
- Auth outsourced entirely — no user management to build

## What We Don't Build

- Execution monitoring UI (Union has this)
- PR review UI (GitHub has this)
- A full IDE (VS Code Server exists for power users)
- A separate chat application (marimo's built-in chat + custom rules is sufficient)
- User/auth management (GitHub OAuth via Union)
- Custom MCP integration in marimo (wait for upstream support)

## Open Questions

- **Scratch notebook persistence**: Where do per-user notebooks live in the hosted environment? Tied to GitHub username? Union user workspace?
- **Minimum viable export**: What metadata does the structured artifact need? Just the function body + description? Or types and test hints too?
- **Community namespace**: Is there a `contrib/` tier for lower-bar contributions, or does everything go through full review?

## Implementation Phases

### Phase 1: Marimo as hosted frontend (current branch)
- [x] Notebook app deployed as Flyte AppEnvironment
- [x] Direct imports from stargazer API
- [x] Shared config (STARGAZER_ENV_VARS, STARGAZER_SECRETS)
- [x] Custom AI rules in marimo.toml for stargazer-aware chat
- [ ] Link out to Union UI from task execution results
- [ ] Getting started notebook covers core workflows

### Phase 2: Export and promote
- [ ] `stargazer promote-task` CLI for cell-to-module extraction
- [ ] Structured export format definition

### Phase 3: GitHub contribution flow
- [ ] Server-side PR creation using GitHub OAuth token
- [ ] Fork management (create or reuse)
- [ ] Branch + commit + PR from exported artifact
- [ ] Link back to PR from marimo

### Phase 4: Hosted platform polish
- [ ] Per-user scratch notebook persistence
- [ ] "My contributions" view showing exported tasks and PR status
- [ ] Union UI deep links from notebook execution cells
- [ ] Wire stargazer MCP server into marimo chat (when upstream support ships)
