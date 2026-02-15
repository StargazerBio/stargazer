# Browser Implementation Plan

## Overview

Build a React web SPA that connects to a hosted Stargazer MCP server over Streamable HTTP. The LLM client runs server-side to protect API keys. The browser shares the `frontend/core/` library with the TUI for chat state and hooks.

## Prerequisites

- MCP server (`mcp_server.md`) — completed
- TUI (`tui.md`) — completed (establishes `frontend/core/`)
- Storage client refactor (`storage_client_refactor.md`) — completed
- STARGAZER_MODE configuration (`stargazer_mode_config.md`) — completed

## Current State

- MCP server exists at `src/stargazer/server.py`, supports stdio and HTTP transports
- `frontend/core/` exists with MCP client, chat engine, React hooks
- `frontend/tui/` exists and works
- No browser frontend

## Target State

```
frontend/
├── core/                     # Already exists (shared with TUI)
├── tui/                      # Already exists
└── web/
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── index.tsx         # Entry point: connect to MCP server, render app
        ├── app.tsx           # Root component with useChat
        └── components/
            ├── message-list.tsx   # Scrollable message history
            ├── message.tsx        # Message bubble with markdown
            ├── tool-call.tsx      # Expandable tool call card
            ├── input.tsx          # Text input with send button
            ├── sidebar.tsx        # File browser, run history
            └── file-upload.tsx    # Drag-and-drop file upload
```

Additionally, the Python server needs a chat endpoint for server-side LLM orchestration:

```
src/stargazer/
├── server.py                 # MCP server (already exists)
└── chat_endpoint.py          # Chat proxy: receives messages, runs LLM + tool loop, streams response
```

## Implementation Plan

### Phase 1: Server-Side Chat Endpoint

The browser cannot hold LLM API keys. Build a thin server-side endpoint that:

1. Receives user messages via HTTP POST
2. Runs the LLM ↔ MCP tool loop server-side
3. Streams the response back via SSE

Create `src/stargazer/chat_endpoint.py`:

```python
from starlette.applications import Starlette
from starlette.responses import StreamingResponse
from starlette.routing import Route
import anthropic

async def chat(request):
    body = await request.json()
    user_message = body["message"]
    history = body.get("history", [])

    client = anthropic.AsyncAnthropic()
    # Get available tools from MCP server
    tools = get_registered_tools()

    async def stream():
        # Run LLM tool loop
        messages = history + [{"role": "user", "content": user_message}]
        while True:
            response = await client.messages.create(
                model="claude-sonnet-4-5-20250929",
                messages=messages,
                tools=tools,
                stream=True,
            )
            # Stream text tokens as SSE events
            # Execute tool calls, yield tool results as SSE events
            # If no more tool calls, break
            ...

    return StreamingResponse(stream(), media_type="text/event-stream")

app = Starlette(routes=[Route("/chat", chat, methods=["POST"])])
```

2. Integrate with MCP server startup — when `--http` is passed, also mount the chat endpoint

3. Test: `curl -X POST localhost:8000/chat -d '{"message": "list available references"}'`

### Phase 2: Web App Setup

1. Add `web` to the frontend workspace:

```bash
cd frontend
npm init -w web -y
```

2. Install dependencies:
   - `react`, `react-dom`
   - `@modelcontextprotocol/sdk`
   - `vite`, `@vitejs/plugin-react`
   - Workspace dependency: `"@stargazer/core": "workspace:*"`

3. Create `vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
    plugins: [react()],
});
```

4. Create `index.html` with React mount point

### Phase 3: Core Integration

The browser uses `frontend/core/` differently than the TUI:

1. MCP client connects via HTTP instead of stdio:

```typescript
import { connectHttp } from "@stargazer/core";

const mcpClient = await connectHttp("https://stargazer.example.com/mcp");
```

2. Chat does NOT use the core `useChat` hook's LLM integration directly — instead it calls the server-side chat endpoint. Create a browser-specific chat adapter:

```typescript
// web/src/hooks/use-browser-chat.ts
export function useBrowserChat(serverUrl: string) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [isStreaming, setIsStreaming] = useState(false);

    async function sendMessage(text: string) {
        setMessages(prev => [...prev, { role: "user", content: text }]);
        setIsStreaming(true);

        const response = await fetch(`${serverUrl}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, history: messages }),
        });

        // Read SSE stream, dispatch messages/tool calls
        const reader = response.body.getReader();
        // ... parse SSE events, update state
        setIsStreaming(false);
    }

    return { messages, isStreaming, sendMessage };
}
```

3. The core hooks `useTools` and `useResources` still work directly — the browser connects to the MCP server over HTTP for resource/tool discovery

### Phase 4: Web Components

1. `<App>` — root component:

```tsx
export function App({ serverUrl }: { serverUrl: string }) {
    const { messages, isStreaming, sendMessage } = useBrowserChat(serverUrl);
    const mcpClient = useMcpClient(serverUrl);

    return (
        <div className="app">
            <Sidebar mcpClient={mcpClient} />
            <div className="chat">
                <MessageList messages={messages} />
                <Input onSubmit={sendMessage} disabled={isStreaming} />
            </div>
        </div>
    );
}
```

2. `<MessageList>` — scrollable div, auto-scrolls to bottom on new messages

3. `<Message>` — styled message with:
   - Role indicator (user/assistant)
   - Markdown rendering for assistant messages
   - Nested `<ToolCall>` components for tool invocations

4. `<ToolCall>` — expandable card:
   - Header: tool name + status icon (spinner, checkmark, error)
   - Expandable body: input args (JSON) + result

5. `<Input>` — text input with send button, Enter to submit, Shift+Enter for newline

6. `<Sidebar>` — panels for:
   - File browser (reads `stargazer://references`, `stargazer://samples` resources)
   - Run history (reads `stargazer://runs` resource)
   - Config display (reads `stargazer://config` resource)

7. `<FileUpload>` — drag-and-drop zone:
   - Accepts files, uploads via the server
   - Shows upload progress
   - After upload, displays file metadata

### Phase 5: File Handling

Browser-specific file operations:

1. **Upload**: Drag-and-drop or file picker → multipart POST to server → server calls `upload_file` MCP tool → returns file metadata to browser

2. **Download**: Output files have Pinata gateway URLs (public or signed). Browser renders download links directly. No MCP tool needed for the actual download — just the URL.

3. **File browser**: Sidebar queries `stargazer://references` and `stargazer://samples` resources to show available data

### Phase 6: Build + Deployment

1. Build static SPA:

```bash
cd frontend/web
npm run build  # vite build → dist/
```

2. Deployment options:
   - Serve `dist/` from the same server running the MCP server
   - Or deploy to a CDN with the MCP server URL configured via env var

3. The hosted server runs:
   - `stargazer serve --http` (MCP server + chat endpoint)
   - Static file serving for the SPA (or separate CDN)

### Phase 7: Testing

1. **Component tests**:
   - Message renders with correct role styling
   - Tool call card expands/collapses
   - Input submits on Enter, supports Shift+Enter

2. **Integration tests**:
   - Chat endpoint receives message, returns streamed response
   - File upload flow works end-to-end
   - MCP resource queries populate sidebar

3. **E2E tests** (Playwright):
   - Full chat flow: type message → see response → tool calls render
   - File upload drag-and-drop
   - Sidebar shows available data

## File Changes

| File | Change |
|------|--------|
| `src/stargazer/chat_endpoint.py` | **New** — server-side LLM proxy with SSE streaming |
| `src/stargazer/server.py` | **Modified** — mount chat endpoint when running in HTTP mode |
| `frontend/web/package.json` | **New** — web app |
| `frontend/web/vite.config.ts` | **New** — Vite config |
| `frontend/web/index.html` | **New** — HTML shell |
| `frontend/web/src/index.tsx` | **New** — entry point |
| `frontend/web/src/app.tsx` | **New** — root component |
| `frontend/web/src/hooks/use-browser-chat.ts` | **New** — server-side chat adapter |
| `frontend/web/src/components/*.tsx` | **New** — UI components |

## Design Decisions

1. **Server-side LLM is the key asymmetry**: The browser cannot hold API keys. The chat endpoint runs the same LLM ↔ tool loop that the TUI runs locally, but on the server. This is the one place where TUI and browser architectures diverge.

2. **Browser-specific chat hook**: The browser uses `useBrowserChat` instead of the core `useChat` hook. The core hook calls the LLM directly (for TUI). The browser hook calls the server-side chat endpoint. Both produce the same `{ messages, isStreaming, sendMessage }` interface, so components don't care which one is used.

3. **MCP resources still direct**: The browser connects to the MCP server over HTTP for tool/resource discovery. Only the LLM interaction is proxied — resource reads and tool listings go directly to the MCP server.

4. **Vite for simplicity**: Vite provides fast dev server, HMR, and optimized production builds with minimal config. No need for Next.js since this is a pure SPA with no SSR requirements.

5. **File upload goes through the server**: The browser cannot call `upload_file` MCP tool directly with a local path (the file is on the user's machine, not the server). File uploads use a multipart HTTP endpoint on the server, which then calls the MCP tool.

6. **Static SPA deployment**: The browser app is a static bundle. It can be served from the same server or a CDN. The only dynamic dependency is the MCP server URL, configured at build time or via runtime config.
