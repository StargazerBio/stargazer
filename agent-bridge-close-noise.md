---
title: agent-bridge-close-noise
status: doing
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

## Plan

On `fix/agent-bridge-close-noise`.

- [ ] Test first, in `tests/unit/test_proxy.py`: `agent_bridge` called with a stand-in panel socket whose `receive()` returns `websocket.disconnect` and whose `close()` raises `WebSocketDisconnect(1006)`, as starlette's does on a dropped client. It must return; today it raises.
- [ ] `agent_bridge`'s `finally` closes under `suppress(RuntimeError, WebSocketDisconnect)`.

Related: [[agent-mcp]], [[marimo-terminal]], [[board]].
