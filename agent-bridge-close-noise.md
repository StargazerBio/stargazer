---
title: agent-bridge-close-noise
status: review
priority: low
created: 2026-10-30
pr: 142
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

- [x] Test first, in `tests/unit/test_proxy.py`: `agent_bridge` called with a stand-in panel socket whose `receive()` returns `websocket.disconnect` and whose `close()` raises `WebSocketDisconnect(1006)`, as starlette's does on a dropped client. It must return; today it raises.
- [x] `agent_bridge`'s `finally` closes under `suppress(RuntimeError, WebSocketDisconnect)`.

## Evidence (2026-11-09)

- Unit tier: 281 passed; the new test failed first with `WebSocketDisconnect` out of `agent_bridge` (measured).
- `ghcr.io/stargazerbio/debug:dispatch-installed-bundle` run locally: a client opened `/__sg__/agent/opencode`, sent a line and aborted its TCP connection. As built, one `Exception in ASGI application` in the container's log; with the branch's `proxy.py` mounted over the image's, none (measured).

## Verification recipe

BRIDGE-DROP: a panel client that drops its connection leaves no traceback in the pod's log.

1. `docker run -d --name sg -p 18080:8080 -v $PWD/runtime/proxy.py:/usr/local/lib/sg_proxy.py:ro <a Stargazer image>`, and wait for `GET /__sg__/ready` to return 200.
2. From the dev environment, connect and drop:

   ```python
   import asyncio, websockets
   async def main():
       ws = await websockets.connect("ws://localhost:18080/__sg__/agent/opencode")
       await ws.send('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1}}')
       await asyncio.sleep(3)
       ws.transport.abort()
       await asyncio.sleep(2)
   asyncio.run(main())
   ```

3. `docker logs sg 2>&1 | grep -c "Exception in ASGI application"`. Passes: 0. Fails as on `main`: 1, ending in `starlette.websockets.WebSocketDisconnect`.

Related: [[agent-mcp]], [[marimo-terminal]], [[board]].
