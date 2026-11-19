---
title: mcp-stdio-stdout-noise
status: later
priority: low
created: 2026-11-16
---

Starting the MCP server over stdio (`python -m stargazer.server`) writes Flyte's image warning (`No python_version was given for the image, so it uses Python 3.14 from the local interpreter…`) to stdout at import, before the JSON-RPC session. stdout is the stdio transport, so the client gets four lines that aren't JSON-RPC and logs `Failed to parse JSONRPC message from server` with a traceback for each (measured with the `mcp` 2.x client, 2026-11-16, while verifying ticket [[mcp-tool-errors-reach-client]]). The session still works. The server's logging, Flyte's included, belongs on stderr in stdio mode.

The warning comes from `images.task_image()`'s `flyte.Image.from_pixi_script`, which builds on `from_debian_base` without a Python version (the pixi environment supplies Python, so there's no version to pin), while the domains' `env.py` import at `stargazer.server`'s import. Flyte's rich handler writes to stdout. So the fix has to take stdout away from logging before `server.py` imports the registry, in the import block PR 154 also edits: it waits for that PR.

Related: [[board]], [[mcp-tool-errors-reach-client]], [[robust-logging]].
