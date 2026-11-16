---
title: mcp-stdio-stdout-noise
status: backlog
priority: low
created: 2026-11-16
---

Starting the MCP server over stdio (`python -m stargazer.server`) writes Flyte's image warning (`No python_version was given for the image, so it uses Python 3.14 from the local interpreter…`) to stdout at import, before the JSON-RPC session. stdout is the stdio transport, so the client gets four lines that aren't JSON-RPC and logs `Failed to parse JSONRPC message from server` with a traceback for each (measured with the `mcp` 2.x client, 2026-11-16, while verifying ticket [[mcp-tool-errors-reach-client]]). The session still works. The server's logging, Flyte's included, belongs on stderr in stdio mode.

Related: [[board]], [[mcp-tool-errors-reach-client]], [[robust-logging]].
