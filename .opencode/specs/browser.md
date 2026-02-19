# Browser Specification

## Design Goals

The browser interface lets researchers try Stargazer without installing anything. It is a hosted web application powered by Chainlit that provides a frictionless chat experience with a server-provided LLM. No API keys required from the user — the hosted server provides everything.

## Architecture

The browser frontend is a Chainlit application that acts as an MCP client. Chainlit connects to `stargazer serve` over stdio, discovers available tools, and executes them through the MCP wire protocol. LLM inference is handled by LiteLLM, which provides a unified interface across providers.

```
┌──────────────────────────────────────┐
│  Browser (Chainlit-provided UI)      │
│  ┌────────────────────────────────┐  │
│  │ Chat UI (React, served by      │  │
│  │ Chainlit)                      │  │
│  └────────────┬───────────────────┘  │
│               │ WebSocket            │
└───────────────┼──────────────────────┘
                │
┌───────────────▼──────────────────────┐
│  Hosted Server                       │
│  ┌──────────────┐                    │
│  │ Chainlit App │                    │
│  │ (MCP client) │                    │
│  │      │       │                    │
│  │      ├──→ LLM Provider (LiteLLM) │
│  │      │                            │
│  │      └──→ stargazer serve (stdio) │
│  │               ├──→ Union (exec)   │
│  │               └──→ Pinata (store) │
│  └──────────────┘                    │
└──────────────────────────────────────┘
```

### Key Architectural Decisions

**Chainlit as MCP client**: Chainlit's native MCP integration connects to MCP servers over stdio, SSE, or streamable HTTP. It discovers tools via `session.list_tools()` and executes them via `session.call_tool()`. This means `server.py` remains the single source of truth for tool definitions — no duplication, no drift.

**LiteLLM for LLM inference**: LiteLLM provides a unified OpenAI-compatible interface across 100+ providers. The model is specified as `provider/model-name` (e.g., `anthropic/claude-haiku-4-5-20251001`). Swapping providers requires changing one string, no code changes. LiteLLM also provides:
- `litellm.supports_function_calling(model)` — verify provider supports tool use
- `litellm.utils.function_to_dict()` — generate schemas from Python functions
- Token usage tracking for cost monitoring
- Fallback support for models without native tool calling

**stdio transport**: Chainlit spawns `stargazer serve` as a subprocess and communicates over stdin/stdout. This keeps both processes on the same machine with negligible overhead. The MCP server handles submitting work to Union and storing files on Pinata.

### Why Chainlit

- Python-native — fits the existing stack, no second language or build pipeline
- Native MCP client support — discovers and executes tools via the standard protocol
- Provides the full chat UI out of the box (streaming, tool steps, file upload, auth)
- Tool calls render as collapsible step cards with input/output details
- Active development and community

### Why a Hosted LLM

Browser users should not need an API key. The server provides the LLM, likely a cheaper inference provider to keep costs manageable. This makes the experience frictionless — visit the URL, start chatting.

Requirements for the hosted LLM provider:
- OpenAI-compatible function/tool calling (required for agentic workflows)
- Streaming support with tool calls
- Sufficient context window for bioinformatics tool outputs

## User Interaction

### Chat Flow

1. User types a message in the Chainlit input
2. Message is sent to the Chainlit backend over WebSocket
3. Chainlit sends the message to the LLM via LiteLLM with MCP tool definitions
4. LLM responds with text and/or tool calls
5. Tool calls are executed via `mcp_session.call_tool()` against `stargazer serve`
6. `stargazer serve` submits work to Union, stores results on Pinata
7. Results are rendered as Chainlit steps (collapsible tool call cards)
8. Tool results are fed back to the LLM for the next iteration
9. Final text response streams back to the browser

### Key Behaviors

- Streaming: responses arrive token-by-token via WebSocket
- Tool calls render as Chainlit steps with input/output details
- File upload via Chainlit's built-in upload mechanism
- Long-running tasks (Union execution) show progress indicators
- Auth required (GitHub OAuth via Chainlit)

## Hosting

The deployment runs:

1. **Chainlit process** — serves the browser UI, manages LLM interaction, acts as MCP client
2. **`stargazer serve` subprocess** — spawned by Chainlit over stdio, handles tool execution, Union submission, Pinata storage

Both are managed as a single deployment unit. Chainlit spawns and manages the `stargazer serve` lifecycle.

## Multi-Tenancy (Initial)

For the initial implementation:
- All browser users share a single Pinata account (public files)
- All browser users share a single Union namespace
- No user isolation — this is acceptable for early adoption
- Session state (conversation history) is persisted per-user by the web server

## Authentication

Two separate concerns:

### User Auth — GitHub OAuth

Users authenticate via GitHub OAuth. This gates access to the chat interface and ensures only authorized users can consume LLM inference.

Setup:
1. Register a GitHub OAuth App at https://github.com/settings/apps
2. Set callback URL to `CHAINLIT_URL/auth/oauth/github/callback`
3. Provide `OAUTH_GITHUB_CLIENT_ID` and `OAUTH_GITHUB_CLIENT_SECRET` as environment variables

The Chainlit app implements an `@cl.oauth_callback` handler that receives the authenticated GitHub user data and returns a `cl.User` to allow access or `None` to deny. This allows restricting access to specific GitHub users or org members if needed.

### Infrastructure Auth

Server-side credentials, not exposed to users:
- LLM provider API key (consumed by LiteLLM)
- `PINATA_JWT` for storage
- Union/Flyte configuration for workflow execution

## Cost Controls

Since the server provides the LLM:
- Auth prevents anonymous access
- Per-user rate limiting or token budgets may be needed for public-facing deployments
- LiteLLM provides token usage tracking out of the box
- Choice of cheaper inference provider keeps per-request cost low

## Relationship to CLI

The browser and CLI are fully independent frontends. They share the same MCP server (`stargazer serve`) as the tool interface, but consume it differently.

| Concern | CLI (Bring Your Own) | Browser (Chainlit) |
|---------|---------------------|-------------------|
| Rendering | User's MCP client | Chainlit (React, served by Python) |
| MCP transport | stdio (user spawns server) | stdio (Chainlit spawns server) |
| LLM client | User-provided (their API key, their client) | Server-provided (LiteLLM, hosted key) |
| Task execution | Local or Union (user's config) | Union (server's config) |
| Storage | Local or Pinata (user's choice) | Pinata public (server's account) |
| Auth | None needed | Required (Chainlit built-in) |
| Distribution | `stargazer serve` + any MCP client | Hosted URL |
