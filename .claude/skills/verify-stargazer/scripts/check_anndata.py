"""Check every AnnData asset in a run's local store against its file on disk.

For each record, the n_obs keyvalue must match the cell count in the file the
record points at, and no two samples at the same stage may share a file.
Prints one line per asset. Exits 1 on any mismatch.

Usage: uv run python .claude/skills/verify-stargazer/scripts/check_anndata.py [stage ...]
"""

import json
import os
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import anndata

warnings.filterwarnings("ignore")

local = Path(os.environ["STARGAZER_LOCAL"])
stages = set(sys.argv[1:])
records = json.loads((local / "stargazer_local.json").read_text())["_default"].values()

failed = False
files_by_stage = defaultdict(lambda: defaultdict(set))
for rec in records:
    kv = rec["keyvalues"]
    if kv.get("asset") != "anndata" or (stages and kv["stage"] not in stages):
        continue
    path = local / rec["rel_path"]
    on_disk = anndata.read_h5ad(path, backed="r").n_obs
    claimed = int(kv["n_obs"])
    files_by_stage[kv["stage"]][rec["rel_path"]].add(kv["sample_id"])
    # Raw seeds are registered without counts, so 0 means "not recorded".
    status = "ok" if claimed in (0, on_disk) else "MISMATCH"
    failed |= status != "ok"
    print(
        f"{status:8} {kv['stage']:12} {kv['sample_id']:6} keyvalue n_obs={claimed} file={rec['rel_path']} n_obs={on_disk}"
    )

for stage, files in files_by_stage.items():
    for rel_path, samples in files.items():
        if len(samples) > 1:
            failed = True
            print(
                f"SHARED   {stage:12} {rel_path} is claimed by samples {sorted(samples)}"
            )

sys.exit(1 if failed else 0)
