---
title: mcp-tool-errors-reach-client
status: backlog
priority: low
created: 2026-11-16
---

MCPServer (mcp 2.x) passes only a `ToolError`'s message on to the client; any other exception reaches it as a bare `Error executing tool <name>`, its text kept in the server's log (measured over stdio, 2026-11-16, while verifying ticket [[run-task-by-cid]]). `run_task` and `run_workflow` raise `ToolError`s since that ticket. The other tools in `src/stargazer/server.py` don't: `upload_file` and `update_file` let `build_asset()`'s `ValueError` through (a missing `asset` key, a reserved `_` key), `publish_file` and `update_file` their storage errors, so an agent gets no reason it can act on. Raise the refusals a caller can fix as `ToolError`s, and check over stdio that their messages arrive.

Related: [[board]], [[run-task-by-cid]].
