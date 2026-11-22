---
title: mcp-stdio-stdout-noise
status: done
priority: low
created: 2026-11-16
pr: 170
---

Starting the MCP server over stdio (`python -m stargazer.server`) writes Flyte's image warning (`No python_version was given for the image, so it uses Python 3.14 from the local interpreter…`) to stdout at import, before the JSON-RPC session. stdout is the stdio transport, so the client gets four lines that aren't JSON-RPC and logs `Failed to parse JSONRPC message from server` with a traceback for each (measured with the `mcp` 2.x client, 2026-11-16, while verifying ticket [[mcp-tool-errors-reach-client]]). The session still works. The server's logging, Flyte's included, belongs on stderr in stdio mode.

The warning comes from `images.task_image()`'s `flyte.Image.from_pixi_script`, which builds on `from_debian_base` without a Python version (the pixi environment supplies Python, so there's no version to pin), while the domains' `env.py` import at `stargazer.server`'s import. Flyte's rich handler writes to stdout. So the fix has to take stdout away from logging before `server.py` imports the registry, in the import block PR 154 also edits (merged).

## Verification recipe

Drive a stdio session the way `.mcp.json` starts the server (`pixi run stargazer`): write `initialize`, `notifications/initialized`, `tools/list` and a `tools/call` of `list_tasks` to its stdin, one JSON object per line, and read stdout until the `list_tasks` reply arrives. Every stdout line must parse as JSON, and Flyte's warning should be on stderr. Run it with the tenant `.flyte/config.yaml` and with none. On 2026-11-21, `main` printed 3 non-JSON lines before the `initialize` reply; the branch printed 0 in both cases. `tests/unit/test_server_stdio.py` checks the first line.

## Outcome

Shipped as StargazerBio/stargazer#170 (merged 2026-11-22, 08c1247): `server.py` sets `DISABLE_RICH_LOGGING=1` before `init_flyte()`, so Flyte logs to stderr and stdout carries only JSON-RPC; `tests/unit/test_server_stdio.py` checks the first stdout line; `docs/architecture/mcp-server.md` says so. Verified with the recipe: 3 non-JSON stdout lines on `main`, 0 on the branch with the tenant config and with none. Nothing left.

Related: [[board]], [[mcp-tool-errors-reach-client]], [[robust-logging]].
