"""Check asset storage on the devbox: store files in one pod, find them in another.

Runs `devbox_probe_tasks.probe`: `produce` writes small files and stores each
as an asset (bytes to the devbox bucket, a row to the devbox dashboard's
index), then `consume` runs in a second pod, finds them with `assemble()` and
reads each back with `fetch()`. Exits 0 only when every file comes back with
its own contents.

Needs the devbox dashboard (`stargazer-users devbox`). The probe runs on the
dashboard's image recipe; that image carries the project's source, so a source
change since the last deploy builds it again (a few seconds from cache). The
storage port-forward is held open while the code bundle uploads.

Usage: uv run --all-extras python .claude/skills/verify-stargazer/scripts/devbox_storage_probe.py <tag>
"""

import importlib
import os
import sys
from pathlib import Path

import flyte

from app.admin_app import app_env
from app.onboard import DEVBOX_STORE_ROOT, DEVBOX_SUBJECT, storage_port_forward
from stargazer.config import PROJECT_ROOT

N = 3


def main(tag: str) -> int:
    """Run the probe once; 0 when every file reads back as written."""
    flyte.init_from_config(
        PROJECT_ROOT / ".flyte" / "config.yaml", root_dir=Path(__file__).parent
    )
    # The tasks module reads its image when imported, so it's imported only
    # once the dashboard image's address is known.
    os.environ["SG_PROBE_IMAGE"] = flyte.build(app_env.image).uri
    tasks = importlib.import_module("devbox_probe_tasks")
    assert (tasks.STORE_ROOT, tasks.OWNER) == (DEVBOX_STORE_ROOT, DEVBOX_SUBJECT)
    with storage_port_forward():
        run = flyte.run(tasks.probe, n=N, tag=tag)
    print(f"run: {run.url}")
    run.wait()
    got = run.outputs()[0]
    want = [f"{tag}:{i}" for i in range(N)]
    print(f"read back: {got}")
    print("ok" if got == want else f"MISMATCH: expected {want}")
    return 0 if got == want else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
