# Browser Specification

## Design Goals

The browser interface lets researchers try Stargazer without installing anything. It is a hosted web application that connects to a remote Stargazer MCP server over Streamable HTTP. All execution happens on the server (Union/Flyte) and all storage is remote (Pinata/IPFS).

## Architecture

The browser is an MCP host with one key difference from the TUI: the LLM client runs server-side to protect API keys. The browser sends user messages to a chat endpoint, which orchestrates LLM calls and MCP tool execution, then streams results back.

```
┌──────────────────────────────────┐
│  Browser SPA (React)             │
│  ┌────────────────────────────┐  │
│  │ Chat UI (React components) │  │
│  └────────────┬───────────────┘  │
│               │ HTTP/SSE         │
└───────────────┼──────────────────┘
                │
┌───────────────▼──────────────────┐
│  Hosted Server                   │
│  ┌──────────────┐  ┌──────────┐  │
│  │ Chat Endpoint│  │ MCP      │  │
│  │ (LLM client, │──│ Server   │  │
│  │  tool loop)  │  │ (HTTP)   │  │
│  └──────────────┘  └──────────┘  │
└──────────────────────────────────┘
```

### Why LLM is Server-Side

The browser cannot hold API keys. In the TUI, the user provides their own `ANTHROPIC_API_KEY` and the LLM client runs locally. In the browser, the hosted server holds the key and proxies LLM interactions. This is the one structural asymmetry between TUI and browser.

The chat endpoint:

1. Receives user message from the browser
2. Sends it to the LLM with available MCP tools
3. Executes any tool calls against the MCP server
4. Streams the LLM's response back to the browser via SSE

## Technology

- **Framework**: React
- **Build**: Vite (static SPA)
- **Shared code**: Imports `frontend/core/` for chat state, React hooks, types
- **Styling**: TBD (CSS modules, Tailwind, etc.)

## User Interaction

### Chat Flow

Same logical flow as TUI, but the LLM loop runs server-side:

1. User types a message
2. Message is sent to the chat endpoint via HTTP POST
3. Server runs the LLM ↔ MCP tool loop
4. Response streams back via SSE
5. Browser renders messages, tool calls, and results

### UI Layout

The browser has more screen real estate than a terminal and can show richer UI:

- **Chat panel**: Messages, tool calls, streaming responses
- **Sidebar**: File browser (via MCP resources), run history, workflow status
- **File upload**: Drag-and-drop to upload files (calls `upload_file` tool)
- **Download links**: Output files are downloadable via Pinata gateway URLs

### Key Behaviors

- Streaming: responses arrive via SSE, rendered incrementally
- Tool calls render as expandable cards with input/output details
- File upload via drag-and-drop triggers `upload_file` MCP tool
- Download links for output files (public Pinata gateway or signed URLs)
- Workflow progress visualization (polls `get_run_status`)
- Responsive layout for different screen sizes

## Hosting

The browser deployment requires a hosted server that runs:

1. The Python MCP server (`stargazer serve --http`)
2. The chat endpoint (LLM proxy)
3. Static file serving for the SPA

This can be a single process or split across services. The MCP server and chat endpoint share the same Python process for simplicity.

## Authentication

Browser users do not provide their own API keys. The hosted server holds:

- `ANTHROPIC_API_KEY` (or equivalent LLM provider key)
- `PINATA_JWT`
- Union/Flyte configuration

User authentication (who can access the hosted instance) is a separate concern. Options include session tokens, OAuth, or API keys issued to users. This is not part of the MCP spec — it's a deployment concern.

## Relationship to TUI

The browser and TUI share the `frontend/core/` TypeScript library — chat state management, React hooks (`useChat`, `useTools`, `useResources`), and TypeScript types. The differences:

| Concern | TUI | Browser |
|---------|-----|---------|
| Rendering | Ink (`<Box>`, `<Text>`) | DOM (`<div>`, `<span>`) |
| MCP transport | stdio (child process) | Streamable HTTP (remote) |
| LLM client | Local (user's API key) | Server-side (hosted key) |
| File access | Local filesystem | Upload/download via Pinata |
| Distribution | Compiled binary | Hosted SPA |
