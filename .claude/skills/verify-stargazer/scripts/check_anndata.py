"""Check every AnnData asset in a run's index against its stored file.

For each row, the n_obs keyvalue must match the cell count in the file the
row points at. Every sample seen at any stage must appear at every stage it
was run through: the index keeps one row per CID, so two samples producing
byte-identical files show up as one sample missing from that stage. Prints
one line per asset. Exits 1 on any mismatch or missing sample.

Usage: uv run python .claude/skills/verify-stargazer/scripts/check_anndata.py [stage ...]
"""

import json
import os
import sqlite3
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import anndata

warnings.filterwarnings("ignore")

index = Path(os.environ["STARGAZER_INDEX_URL"].removeprefix("sqlite://")).expanduser()
stages = set(sys.argv[1:])
conn = sqlite3.connect(index)
rows = conn.execute("SELECT cid, uri, name, keyvalues FROM assets").fetchall()
conn.close()

failed = False
samples_by_stage = defaultdict(set)
for cid, uri, name, keyvalues in rows:
    kv = json.loads(keyvalues)
    if kv.get("asset") != "anndata" or (stages and kv["stage"] not in stages):
        continue
    on_disk = anndata.read_h5ad(Path(uri), backed="r").n_obs
    claimed = int(kv["n_obs"])
    samples_by_stage[kv["stage"]].add(kv["sample_id"])
    # Raw seeds are registered without counts, so 0 means "not recorded".
    status = "ok" if claimed in (0, on_disk) else "MISMATCH"
    failed |= status != "ok"
    print(
        f"{status:8} {kv['stage']:12} {kv['sample_id']:6} keyvalue n_obs={claimed} "
        f"file={name} n_obs={on_disk} cid={cid[:16]}…"
    )

everyone = set().union(*samples_by_stage.values()) if samples_by_stage else set()
for stage, samples in sorted(samples_by_stage.items()):
    for missing in sorted(everyone - samples):
        failed = True
        print(f"MISSING  {stage:12} {missing:6} has no asset at this stage")

sys.exit(1 if failed else 0)
