---
title: agent-bridge-close-noise
status: backlog
priority: low
created: 2026-10-30
---

The proxy's agent bridge (`agent_bridge` in `runtime/proxy.py`) logs an
"Exception in ASGI application" traceback whenever the panel's client hangs
up abruptly. Its `finally` closes the websocket under
`suppress(RuntimeError)`, but on a socket the client already dropped,
starlette's `close()` raises `WebSocketDisconnect`. Seen in the
`stargazer:agent-mcp` container's log after each probe client disconnected.
Harmless (the agent is already killed), but it buries real errors in the pod
log. Suppress `WebSocketDisconnect` too, with a unit test that disconnects
mid-session and checks the bridge returns cleanly.

Related: [[agent-mcp]], [[marimo-terminal]].
