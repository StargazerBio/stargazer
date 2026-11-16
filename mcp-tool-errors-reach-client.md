---
title: mcp-tool-errors-reach-client
status: review
priority: low
created: 2026-11-16
pr: 154
---

MCPServer (mcp 2.x) passes only a `ToolError`'s message on to the client; any other exception reaches it as a bare `Error executing tool <name>`, its text kept in the server's log (measured over stdio, 2026-11-16, while verifying ticket [[run-task-by-cid]]). `run_task` and `run_workflow` raise `ToolError`s since that ticket. The other tools in `src/stargazer/server.py` don't: `upload_file` and `update_file` let `build_asset()`'s `ValueError` through (a missing `asset` key, a reserved `_` key), `publish_file` and `update_file` their storage errors, so an agent gets no reason it can act on. Raise the refusals a caller can fix as `ToolError`s, and check over stdio that their messages arrive.

## Choices

- One context manager, `_refusals()` in `server.py`, around the storage and bundle tools' calls (`upload_file`, `update_file`, `publish_file`, `fetch_resource_bundle`): it re-raises `ValueError` and `FileNotFoundError` as `ToolError` with the same message. `get_client()` stays outside it.
- `download_file` catches the gateway's `aiohttp.ClientResponseError` and names the CID and status.
- `Asset.from_keyvalues` names the field and its type in the `JSONDecodeError` for a typed value that doesn't parse.
- `query_files` and `delete_file` unchanged.

## Verification recipe: MCP tool refusals reach the client

An MCP client calling a storage or bundle tool badly gets the reason in the error result, not a bare `Error executing tool <name>`.

### Sub-features

- **E1** `upload_file`: no `asset` key, a reserved `_` key, a typed field that isn't JSON, a path with no file.
- **E2** `update_file`: a CID not in the index, a patch without `asset`.
- **E3** `publish_file`: no public tier, a CID not in storage, metadata over nine fields.
- **E4** `fetch_resource_bundle`: an unknown bundle.
- **E5** `download_file`: a CID neither the index nor the gateway serves.

### How to get to it (user POV)

Any MCP client of `stargazer` (Claude Code, OpenCode, the notebook's agent panel): call a tool with bad arguments.

### Driving it

Preconditions: a checkout with pixi; network for E5 (the public gateway). From the repo root, with `$V/client.py` below:

```bash
RUN_DIR=$HOME/.stargazer/verify-runs/mcp-errors && mkdir -p $RUN_DIR
STARGAZER_LOCAL=$RUN_DIR/local STARGAZER_STORE_ROOT=$RUN_DIR/store STARGAZER_INDEX_URL=$RUN_DIR/index.db \
  pixi run python $V/client.py $PWD/tests/fixtures/general 2>$RUN_DIR/stderr.log
rm -rf $RUN_DIR/local $RUN_DIR/store $RUN_DIR/index.db*
```

```python
"""Drive the stargazer MCP server over stdio and print what each refusal returns."""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FX = sys.argv[1]
GOOD = {"asset": "reference", "build": "GRCh38_TP53"}
UNKNOWN = "bafkreiaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


async def session(env, calls):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "stargazer.server"], env=env
    )
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        for label, name, args in calls:
            if callable(args):
                args = await args(s)
            res = await s.call_tool(name, args)
            text = "".join(c.text for c in res.content if hasattr(c, "text"))
            print(f"{label} [{name}] is_error={res.is_error}: {text[:400]}", flush=True)


async def ten_fields(s):
    kv = {"asset": "notes", **{f"k{i}": "v" for i in range(9)}}
    res = await s.call_tool("upload_file", {"path": f"{FX}/GRCh38_TP53.dict", "keyvalues": kv})
    return {"cid": json.loads(res.content[0].text)["cid"]}


async def main():
    base = dict(os.environ, PINATA_JWT="")
    await session(base, [
        ("R1", "upload_file", {"path": f"{FX}/GRCh38_TP53.fa", "keyvalues": {"build": "x"}}),
        ("R2", "upload_file", {"path": f"{FX}/GRCh38_TP53.fa", "keyvalues": {**GOOD, "_owner": "me"}}),
        ("R3", "upload_file", {"path": f"{FX}/GRCh38_TP53.fa", "keyvalues": {"asset": "alignment", "duplicates_marked": "maybe"}}),
        ("R4", "upload_file", {"path": f"{FX}/nope.fa", "keyvalues": GOOD}),
        ("R5", "update_file", {"cid": UNKNOWN, "keyvalues": GOOD}),
        ("R6", "update_file", {"cid": UNKNOWN, "keyvalues": {"build": "x"}}),
        ("R7", "publish_file", {"cid": UNKNOWN}),
        ("R8", "fetch_resource_bundle", {"bundle_name": "nope"}),
        ("R9", "download_file", {"cid": UNKNOWN}),
    ])
    # A non-empty key turns on the public tier; these refusals come before any request.
    await session(dict(base, PINATA_JWT="not-a-real-key"), [
        ("R10", "publish_file", {"cid": UNKNOWN}),
        ("R11", "publish_file", ten_fields),
    ])


asyncio.run(main())
```

Passes when: exit 0, every line `is_error=True`, and each carries its reason after `Error executing tool <name>: ` — R1/R6 `keyvalues must include 'asset'`, R2 `Reserved system keys ['_owner']`, R3 `duplicates_marked takes JSON (bool), got 'maybe'`, R4 `No such file or directory: '…/nope.fa'` (E1, E2); R5 `No index row for cid`; R7 `no public tier to publish to`, R10 `isn't in your storage`, R11 `at most 9 metadata fields … has 10` (E3); R8 `Bundle 'nope' not found. Available: [...]` (E4); R9 `isn't in your storage, and the public gateway refused it (403 Forbidden)` (E5).

### Gotchas

- Before the fix every line is the bare `Error executing tool <name>`; the reasons are only in the server's log (`stderr.log`), as rich tracebacks.
- The client logs `Failed to parse JSONRPC message from server` four times per server start: Flyte's image warning goes to stdout (ticket [[mcp-stdio-stdout-noise]]). Harmless to the run.
- R10 and R11 need a non-empty `PINATA_JWT` to turn the public tier on; both refusals come before any request to Pinata, so a fake key does.

## Evidence (2026-11-16, PR 154)

Measured with the recipe above: on `origin/main` (`cea2e03`) R1–R11 all returned only `Error executing tool <name>`; on the branch each returned the message listed under "Passes when", exit 0. Unit tier 329 passed; 8 new tests in `tests/unit/test_server.py` each seen failing first with the plain `ValueError`/`FileNotFoundError`/`JSONDecodeError`/`ClientResponseError`.

Related: [[board]], [[run-task-by-cid]], [[mcp-stdio-stdout-noise]].
