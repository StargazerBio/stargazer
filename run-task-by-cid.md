---
title: run-task-by-cid
status: done
priority: low
created: 2026-11-16
pr: 152
---

The MCP server's `run_task` fills a task's asset parameters from one `assemble(**filters)` call, and every filter must match every asset. Its own docstring says what follows: assets with different keys, a reference's `build` and a sample's `sample_id`, can't be filled from one call. So it can't run `bwa_mem`, `haplotype_caller`, `base_recalibrator` or any other task that takes a reference and a sample's file (read from `server.py`, 2026-11-16; not driven).

Take each asset parameter by CID instead, in `inputs` beside the scalars:

```json
{"task_name": "bwa_mem2_mem", "inputs": {"ref": "bafk…", "r1": "bafk…", "r2": "bafk…"}}
```

An agent finds the CIDs with `query_files`, which it already has.

## Plan

- [x] `run_task(task_name, inputs)`: a parameter whose hint is an asset type takes a CID, looked up in the index and specialized; a `list[Asset]` takes a list of CIDs. A CID that isn't found, or is the wrong type, is refused by name. `filters` and `_asset_key_for_hint`'s matching go.
- [x] `docs/architecture/mcp-server.md`, `docs/guides/mcp-server.md`, `docs/architecture/overview.md`. `runtime/notebook_agent.md` needed nothing: it doesn't describe `run_task`'s arguments.
- [x] Refusals in `run_task` and `run_workflow` are `ToolError`s, the only exception whose message MCPServer passes to the client.

Moot if the server goes (ticket [[skills-replace-mcp]]).

## Choices

- CIDs resolve against the user's own index only; a public-only CID is refused, with a message to store it first (`upload_file` or `fetch_resource_bundle`).
- An explicit `null` for an optional asset parameter passes `None`; an omitted one takes the task's default.

## Verification recipe: run_task by CID

An agent finds CIDs with `query_files` and runs a task taking assets with different keys by passing each CID in `inputs`. Bad calls come back with a message naming the parameter.

### Sub-features

- **C1** a reference and a sample's reads fill one task by CID; the output links both.
- **C2** a CID of the wrong type is refused naming the parameter and both types, and the message reaches the client.
- **C3** a legacy `filters` call is refused naming the first missing parameter.

### How to get to it (user POV)

Any MCP client of `stargazer` (Claude Code, OpenCode, the notebook's agent panel): `run_task`.

### Driving it

Preconditions: docker. The gatk image built from the checkout (it carries bwa-mem2 and samtools; the MCP server runs inside it, Flyte in-process):

```bash
pixi run python -c "import flyte,sys; sys.path.insert(0,'cli'); from docker_task_tests import build_image; from stargazer.config import PROJECT_ROOT; from stargazer.tasks.gatk.env import gatk_env; flyte.init(root_dir=PROJECT_ROOT); print(build_image(gatk_env.image))"
docker run --rm --platform linux/amd64 -v "$PWD/tests/fixtures/general:/fixtures:ro" -v "$V:/verify:ro" \
  -e STARGAZER_LOCAL=/tmp/run/local -e STARGAZER_STORE_ROOT=/tmp/run/store -e STARGAZER_INDEX_URL=/tmp/run/index.db -e PINATA_JWT= \
  <image> sh -c 'uv pip install --quiet --target /tmp/pk mcp==2.3.0 && PYTHONPATH=/tmp/pk python /verify/client.py'
```

`$V/client.py`:

```python
"""Drive the stargazer MCP server over stdio like a client: run_task by CID."""

import asyncio
import json
import os
import subprocess
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FX = "/fixtures"


def payload(result):
    """The tool result's JSON, or its error text."""
    texts = [c.text for c in result.content if hasattr(c, "text")]
    if result.is_error:
        return {"ERROR": "".join(texts)}
    parsed = [json.loads(t) if t.strip()[:1] in "[{" else t for t in texts]
    return parsed[0] if len(parsed) == 1 else parsed


async def main():
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "stargazer.server"], env=dict(os.environ)
    )
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()

        async def call(name, args):
            out = payload(await s.call_tool(name, args))
            print(f"\n>>> {name} {json.dumps(args)}\n{json.dumps(out, indent=1)[:1500]}", flush=True)
            return out

        tools = (await s.list_tools()).tools
        rt = next(t for t in tools if t.name == "run_task")
        print("run_task inputSchema:", json.dumps(rt.input_schema))

        ref = await call("upload_file", {"path": f"{FX}/GRCh38_TP53.fa", "keyvalues": {"asset": "reference", "build": "GRCh38_TP53"}})
        r1 = await call("upload_file", {"path": f"{FX}/NA12829_TP53_R1.fq.gz", "keyvalues": {"asset": "r1", "sample_id": "NA12829"}})
        r2 = await call("upload_file", {"path": f"{FX}/NA12829_TP53_R2.fq.gz", "keyvalues": {"asset": "r2", "sample_id": "NA12829"}})

        await call("run_task", {"task_name": "bwa_mem2_mem", "filters": {"build": "GRCh38_TP53"}})
        await call("run_task", {"task_name": "bwa_mem2_mem", "inputs": {"ref": r1["cid"], "r1": r1["cid"]}})
        await call("run_task", {"task_name": "bwa_mem2_index", "inputs": {"ref": ref["cid"]}})
        aln = await call("run_task", {"task_name": "bwa_mem2_mem", "inputs": {"ref": ref["cid"], "r1": r1["cid"], "r2": r2["cid"]}})

        rows = await call("query_files", {"keyvalues": {"asset": "alignment"}})
        local = await call("download_file", {"cid": aln["cid"]})
        kv = aln["keyvalues"]
        flagstat = subprocess.run(["samtools", "flagstat", local], capture_output=True, text=True, check=True).stdout
        sq = subprocess.run(["samtools", "view", "-H", local], capture_output=True, text=True, check=True).stdout
        print("\nCHECK alignment rows:", len(rows), "sample_id:", kv.get("sample_id"),
              "reference_cid==ref:", kv.get("reference_cid") == ref["cid"],
              "source_cid==r1:", kv.get("source_cid") == r1["cid"])
        print("CHECK @SQ lines:", [l for l in sq.splitlines() if l.startswith("@SQ")])
        print("CHECK flagstat:\n" + flagstat)


asyncio.run(main())
```

Passes when: exit 0; the wrong-type call prints `ref takes a Reference, but CID '…' is of type R1` (C2); the `filters` call prints `'bwa_mem2_mem' requires 'ref'` (C3); `bwa_mem2_mem` returns an alignment whose `reference_cid` and `source_cid` are the reference's and R1's CIDs, and flagstat shows ~16k reads, >99% mapped (C1).

### Gotchas

- MCPServer (mcp 2.x) hides a plain exception's message from the client (`Error executing tool run_task`); only a `ToolError`'s text gets through. A unit test calling the function directly can't see this.
- `bwa_mem2_mem` needs the reference's bwa-mem2 index companions: run `bwa_mem2_index` on the reference's CID first.
- A tool returning a list comes back as one content block per item, not one JSON array.
- mcp 2.x's client types are snake_case (`input_schema`, `is_error`).

## Evidence (2026-11-16, PR 152)

Measured, in `stargazer-gatk:78c8ea591c41cacb1ec68cade764588b` built from the branch: C2 and C3 refused with the messages above; `bwa_mem2_index` stored 5 companions; `bwa_mem2_mem` stored `NA12829_aligned.bam` with `sample_id=NA12829`, `reference_cid` = ref, `source_cid` = R1; flagstat 15992 primary, 99.91% mapped, 99.65% properly paired; one `@SQ chr17:7658421-7697490`. Unit tier: 9 new tests in `tests/unit/test_server.py`, each seen failing first.

## Outcome

Shipped in PR 152 (merge `6a6de31`): `run_task` takes each asset parameter as a CID from the user's index; refusals in `run_task` and `run_workflow` reach the client as `ToolError`s. Verified by the unit tier and a `bwa_mem2_mem` run by CIDs over a stdio MCP client in the gatk image (evidence above). No comments on the PR. Left: the other MCP tools' errors, ticket [[mcp-tool-errors-reach-client]].

Related: [[board]], [[skills-replace-mcp]], [[agent-mcp]]., [[mcp-tool-errors-reach-client]].
