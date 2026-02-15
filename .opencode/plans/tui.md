# TUI Implementation Plan

## Overview

Build a terminal-based chat interface using Ink (React for terminals) that connects to the Stargazer MCP server over stdio. The TUI is the primary interface for power users running locally. Compiles to a single binary via Bun.

## Prerequisites

- MCP server (`mcp_server.md`) — completed
- Storage client refactor (`storage_client_refactor.md`) — completed
- STARGAZER_MODE configuration (`stargazer_mode_config.md`) — completed

## Current State

- MCP server exists at `src/stargazer/server.py` with all tools, resources, prompts
- No frontend code exists

## Target State

```
frontend/
├── core/                     # Shared TypeScript library
│   ├── package.json
│   └── src/
│       ├── mcp-client.ts     # MCP client wrapper (stdio + HTTP)
│       ├── chat.ts           # Chat session state, LLM tool loop
│       ├── types.ts          # TypeScript equivalents of Python types
│       └── hooks/
│           ├── use-chat.ts   # Chat state + message handling
│           ├── use-tools.ts  # MCP tool discovery + formatting for LLM
│           └── use-resources.ts  # MCP resource discovery + reading
├── tui/
│   ├── package.json
│   └── src/
│       ├── index.tsx         # Entry point: spawn MCP server, render app
│       ├── app.tsx           # Root component with useChat
│       └── components/
│           ├── message-list.tsx   # Scrollable message history
│           ├── message.tsx        # Single message (user or assistant)
│           ├── tool-call.tsx      # Inline tool call display
│           ├── input.tsx          # Text input with submit
│           └── status-bar.tsx     # Mode, connection, active run
```

## Implementation Plan

### Phase 1: Monorepo Setup

1. Create `frontend/` directory structure
2. Initialize npm workspaces:

```bash
cd frontend
npm init -y
# package.json: "workspaces": ["core", "tui"]
```

3. Set up `frontend/core/`:
   - `npm init -y`
   - Dependencies: `@modelcontextprotocol/sdk`, `@anthropic-ai/sdk`
   - TypeScript config targeting ES2022

4. Set up `frontend/tui/`:
   - `npm init -y`
   - Dependencies: `ink`, `ink-text-input`, `react`, `@anthropic-ai/sdk`
   - Workspace dependency on `core`: `"@stargazer/core": "workspace:*"`
   - TypeScript config

### Phase 2: Core Library — MCP Client

Implement `frontend/core/src/mcp-client.ts`:

1. Stdio connection factory:

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

export async function connectStdio(command: string, args: string[]): Promise<Client> {
    const transport = new StdioClientTransport({ command, args });
    const client = new Client({ name: "stargazer-tui", version: "1.0.0" });
    await client.connect(transport);
    return client;
}
```

2. HTTP connection factory (for browser, implemented now for completeness):

```typescript
export async function connectHttp(url: string): Promise<Client> {
    // Streamable HTTP transport
    ...
}
```

3. Typed wrapper methods: `listTools()`, `callTool()`, `listResources()`, `readResource()`, `getPrompt()`

### Phase 3: Core Library — Chat Engine

Implement `frontend/core/src/chat.ts`:

1. Chat state type:

```typescript
interface ChatState {
    messages: Message[];
    isStreaming: boolean;
    error: string | null;
}

interface Message {
    role: "user" | "assistant";
    content: string;
    toolCalls?: ToolCall[];
}

interface ToolCall {
    name: string;
    args: Record<string, unknown>;
    result?: string;
    status: "pending" | "running" | "complete" | "error";
}
```

2. LLM tool loop:
   - Send user message + available tools to Anthropic API
   - If response contains tool_use blocks, execute each via MCP client
   - Feed tool results back to LLM
   - Repeat until LLM responds with text only
   - Stream text tokens as they arrive

3. Export as a class or set of functions that hooks can wrap

### Phase 4: Core Library — React Hooks

Implement `frontend/core/src/hooks/`:

1. `use-chat.ts`:

```typescript
export function useChat(mcpClient: Client, llmApiKey: string) {
    const [state, dispatch] = useReducer(chatReducer, initialState);

    async function sendMessage(text: string) {
        dispatch({ type: "USER_MESSAGE", text });
        // Run LLM tool loop, dispatch events for streaming, tool calls, etc.
    }

    return { messages: state.messages, isStreaming: state.isStreaming, sendMessage };
}
```

2. `use-tools.ts`:
   - `useTools(client)` — returns list of available MCP tools, formatted for LLM tool_use
   - Refreshes on `notifications/tools/list_changed`

3. `use-resources.ts`:
   - `useResources(client)` — returns list of available resources
   - `readResource(uri)` — fetches resource content

### Phase 5: TUI Application

1. Entry point (`tui/src/index.tsx`):

```tsx
import { render } from "ink";
import { spawn } from "child_process";
import { connectStdio } from "@stargazer/core";
import { App } from "./app.js";

async function main() {
    const mcpClient = await connectStdio("stargazer", ["serve"]);
    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
        console.error("ANTHROPIC_API_KEY is required");
        process.exit(1);
    }
    render(<App mcpClient={mcpClient} apiKey={apiKey} />);
}

main();
```

2. Root component (`tui/src/app.tsx`):

```tsx
import { Box } from "ink";
import { useChat } from "@stargazer/core";
import { MessageList } from "./components/message-list.js";
import { Input } from "./components/input.js";
import { StatusBar } from "./components/status-bar.js";

export function App({ mcpClient, apiKey }) {
    const { messages, isStreaming, sendMessage } = useChat(mcpClient, apiKey);
    return (
        <Box flexDirection="column" height="100%">
            <StatusBar />
            <MessageList messages={messages} />
            <Input onSubmit={sendMessage} disabled={isStreaming} />
        </Box>
    );
}
```

3. Components:
   - `<MessageList>` — scrollable list, renders `<Message>` for each entry
   - `<Message>` — role indicator + text content + optional `<ToolCall>` children
   - `<ToolCall>` — bordered box showing tool name, args summary, result summary, spinner while running
   - `<Input>` — `ink-text-input` with Enter to submit
   - `<StatusBar>` — reads `stargazer://config` resource, shows mode + connection status

### Phase 6: Build + Distribution

1. Build with Bun:

```bash
cd frontend/tui
bun build --compile src/index.tsx --outfile stargazer-tui
```

2. Test the binary:

```bash
STARGAZER_MODE=local ANTHROPIC_API_KEY=sk-... ./stargazer-tui
```

3. Verify:
   - MCP server spawns as child process
   - Chat accepts input, calls LLM, renders response
   - Tool calls execute and render inline
   - Ctrl+C cleanly shuts down

### Phase 7: Testing

1. **Core library unit tests**:
   - Chat state reducer produces correct state transitions
   - MCP client wrapper correctly serializes/deserializes
   - Tool loop terminates correctly (no infinite loops)

2. **TUI smoke tests**:
   - App renders without error
   - Input accepts text and triggers sendMessage
   - Messages render with correct role indicators
   - Tool calls show spinner → result transition

## File Changes

| File | Change |
|------|--------|
| `frontend/package.json` | **New** — workspace root |
| `frontend/core/package.json` | **New** — shared library |
| `frontend/core/src/mcp-client.ts` | **New** — MCP client wrapper |
| `frontend/core/src/chat.ts` | **New** — chat engine with LLM tool loop |
| `frontend/core/src/types.ts` | **New** — TypeScript type definitions |
| `frontend/core/src/hooks/use-chat.ts` | **New** — chat React hook |
| `frontend/core/src/hooks/use-tools.ts` | **New** — tools React hook |
| `frontend/core/src/hooks/use-resources.ts` | **New** — resources React hook |
| `frontend/tui/package.json` | **New** — TUI app |
| `frontend/tui/src/index.tsx` | **New** — entry point |
| `frontend/tui/src/app.tsx` | **New** — root component |
| `frontend/tui/src/components/*.tsx` | **New** — UI components |

## Design Decisions

1. **Ink IS React**: Choosing Ink means TUI components use the same React model (hooks, state, context) as the browser. The core library's hooks work in both without modification.

2. **TUI binary ships without Python**: The compiled binary contains only TypeScript. It expects `stargazer` (the Python MCP server) to be available in PATH. Users who `git clone` the repo already have Python set up.

3. **LLM client in the TUI**: The TUI is an MCP host — it owns the LLM client and uses the MCP server for tools. The user provides their own API key via `ANTHROPIC_API_KEY`.

4. **Core library is not TUI-specific**: Everything in `frontend/core/` is rendering-agnostic. The browser will import the same hooks and get the same behavior with DOM components instead of Ink components.

5. **Bun for compilation**: `bun build --compile` produces a self-contained binary from TypeScript without a separate bundler or Node.js runtime. Single file, drop in PATH.
