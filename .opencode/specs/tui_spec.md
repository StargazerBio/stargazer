# TUI Specification

## Design Goals

The TUI is the primary interface for power users who `git clone` Stargazer and run it locally. It is a terminal-based chat application that connects to the Stargazer MCP server over stdio. No hosted infrastructure required — the user provides their own LLM API key and runs everything on their machine.

## Architecture

The TUI is an MCP host. It owns the LLM client and uses the MCP server as its tool provider.

```
┌─────────────────────────────────────────────┐
│  TUI Binary (Ink/React, compiled via Bun)   │
│  ┌───────────────┐  ┌───────────────────┐   │
│  │ LLM Client    │  │ MCP Client        │   │
│  │ (Anthropic    │──│ (stdio transport) │   │
│  │  SDK)         │  │                   │   │
│  └───────────────┘  └────────┬──────────┘   │
│  ┌───────────────────────────┤              │
│  │ Chat UI (Ink components)  │              │
│  └───────────────────────────┘              │
└──────────────────────────────┬──────────────┘
                               │ stdin/stdout
                    ┌──────────▼──────────┐
                    │ stargazer serve     │
                    │ (Python MCP server) │
                    └─────────────────────┘
```

## Runtime Requirements

- Python with Stargazer installed (`uv pip install -e .`)
- LLM API key (e.g., `ANTHROPIC_API_KEY`)
- `STARGAZER_MODE` (defaults to `local`)
- Optional: `PINATA_JWT` for remote storage

The TUI binary itself is a compiled TypeScript executable. It does not bundle Python — it spawns `stargazer serve` as a child process.

## Technology

- **Framework**: Ink (React for terminals)
- **Build**: `bun build --compile` for single binary
- **Shared code**: Imports `frontend/core/` for MCP client, chat state, React hooks
- **Rendering**: Ink components (`<Box>`, `<Text>`, `<TextInput>`)

## User Interaction

### Chat Flow

1. User types a message in the input area
2. Message is sent to the LLM with available MCP tools
3. LLM responds with text and/or tool calls
4. Tool calls are executed against the MCP server
5. Results are fed back to the LLM
6. Final response is streamed to the chat display

### UI Layout

```
┌─────────────────────────────────────┐
│ stargazer · local · connected       │  ← status bar
├─────────────────────────────────────┤
│                                     │
│ user: Align sample NA12878 to       │
│       GRCh38                        │
│                                     │
│ assistant: I'll align your reads.   │
│   ┌─ tool: hydrate ──────────────┐  │
│   │ filters: {type: reads,       │  │  ← tool call (collapsible)
│   │   sample_id: NA12878}        │  │
│   │ → Found 2 files (r1, r2)    │  │
│   └──────────────────────────────┘  │
│   ┌─ tool: bwa_mem ──────────────┐  │
│   │ Running alignment...         │  │
│   │ → Alignment complete         │  │
│   └──────────────────────────────┘  │
│                                     │
│ Your reads have been aligned.       │
│ Output: ~/.stargazer/local/...      │
│                                     │
├─────────────────────────────────────┤
│ > _                                 │  ← input
└─────────────────────────────────────┘
```

### Key Behaviors

- Streaming: assistant responses appear token-by-token
- Tool calls render inline with a summary of inputs and outputs
- Long-running tools show a spinner with elapsed time
- Status bar shows current mode, connection status, and active workflow
- Scroll: message history is scrollable
- Ctrl+C: graceful shutdown (kills MCP server subprocess)

## Configuration

The TUI reads configuration from environment variables. No config file required for basic operation.

| Variable | Purpose | Required |
|----------|---------|----------|
| `ANTHROPIC_API_KEY` | LLM authentication | Yes |
| `STARGAZER_MODE` | `local` or `cloud` | No (defaults to `local`) |
| `PINATA_JWT` | Pinata storage | No (local storage if absent) |

## Relationship to Browser

The TUI and browser share the `frontend/core/` TypeScript library — MCP client wrapper, chat state management, and React hooks (`useChat`, `useTools`, `useResources`). Only the rendering layer differs: Ink components vs DOM elements.
