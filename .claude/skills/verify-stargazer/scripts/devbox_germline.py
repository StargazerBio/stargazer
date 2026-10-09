"""Drive the germline workflow on the devbox: seed its inputs, run it, check its output.

  seed          Store the TP53 reference and NA12829's reads from a pod, the way
                a task stores files (bytes to the devbox bucket, rows to the
                dashboard's index). Runs submitted from this machine can't
                write the devbox store themselves.
  run <cohort>  Submit `germline_short_variant_discovery` the way SDK code
                does: `flyte.init_from_config()` from the repo root, then
                `flyte.run(...)`. Every step runs in its own pod.
  check <cohort>
                From another pod, find the cohort's VCF with `assemble()`,
                fetch it, and print what it holds. Exits 0 when it names the
                sample and calls at least one variant.

Needs the devbox dashboard (`cli/devbox_dashboard.py`) and the devbox
storage exports from `features/devbox-germline.md`. The seed and check tasks
run on `gatk_env`'s image, which carries the stargazer package. Imported in
their pods too, so it imports nothing from `app/`.

Usage: uv run --all-extras python .claude/skills/verify-stargazer/scripts/devbox_germline.py seed|run|check [cohort]
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import flyte
from flyte.io import File

from stargazer.assets import R1, R2, Reference
from stargazer.assets.asset import assemble
from stargazer.config import PROJECT_ROOT, STARGAZER_ENV_VARS, gatk_env
from stargazer.utils.storage import default_client
from stargazer.workflows import germline_short_variant_discovery

BUILD = "GRCh38"
SAMPLE_ID = "NA12829"
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "general"
REFERENCE = "GRCh38_TP53.fa"
READS = ("NA12829_TP53_R1.fq.gz", "NA12829_TP53_R2.fq.gz")

# What a notebook pod launched from the devbox dashboard gets; `main` checks
# the shell exported the same, since `stargazer.config` forwards them to pods.
STORAGE = {
    "STARGAZER_STORE_ROOT": "s3://flyte-data/stargazer",
    "STARGAZER_INDEX_URL": "http://dashboard-flytesnacks-development.flyte.svc.cluster.local",
    "STARGAZER_OWNER": "devbox-user",
}

env = flyte.TaskEnvironment(
    name="sg_devbox_germline",
    image=gatk_env.image,
    env_vars=STARGAZER_ENV_VARS,
    resources=flyte.Resources(cpu=1, memory=("256Mi", "512Mi")),
)


async def _local_copy(file: File, name: str) -> Path:
    """Download `file` into the cache directory under its original name."""
    dest = Path(default_client.local_dir) / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    return Path(await file.download(dest))


@env.task
async def seed(reference: File, r1: File, r2: File) -> dict[str, str]:
    """Store the reference and the paired reads as assets; return their CIDs."""
    ref = Reference(build=BUILD)
    await ref.update(await _local_copy(reference, REFERENCE))
    r1_path = await _local_copy(r1, READS[0])
    r2_path = await _local_copy(r2, READS[1])
    reads_1, reads_2 = R1(sample_id=SAMPLE_ID), R2(sample_id=SAMPLE_ID)
    await reads_1.update(r1_path)
    await reads_2.update(r2_path, mate_cid=reads_1.cid)
    await reads_1.update(r1_path, mate_cid=reads_2.cid)
    return {"reference": ref.cid, "r1": reads_1.cid, "r2": reads_2.cid}


@env.task
async def check(cohort_id: str) -> str:
    """Find the cohort's VCF, fetch it, and summarize it as JSON."""
    found = await assemble(asset="variants", sample_id=cohort_id)
    if len(found) != 1:
        raise ValueError(
            f"expected one VCF for cohort {cohort_id!r}, found {len(found)}"
        )
    vcf = found[0]
    lines = (await vcf.fetch()).read_text().splitlines()
    header = next(line for line in lines if line.startswith("#CHROM"))
    records = [line.split("\t") for line in lines if line and not line.startswith("#")]
    return json.dumps(
        {
            "cid": vcf.cid,
            "keyvalues": vcf.to_keyvalues(),
            "samples": header.split("\t")[9:],
            "records": len(records),
            "contigs": sorted({r[0] for r in records}),
        }
    )


def _devbox_dashboard():
    """`cli/devbox_dashboard.py`, loaded from its path (it isn't a package)."""
    spec = importlib.util.spec_from_file_location(
        "devbox_dashboard", PROJECT_ROOT / "cli" / "devbox_dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(task, **inputs):
    """Run `task` on the devbox, print its URL, wait, and return the run.

    Raises the run's failure, so a failed run exits non-zero.
    """
    run = flyte.run(task, **inputs)
    print(f"run: {run.url}", flush=True)
    run.wait()
    run.raise_for_status()
    return run


def main(argv: list[str]) -> int:
    """Seed, run or check; 0 on success."""
    wrong = {k: os.environ.get(k) for k, v in STORAGE.items() if os.environ.get(k) != v}
    if wrong:
        raise SystemExit(f"export the devbox storage settings first; differs: {wrong}")
    config = PROJECT_ROOT / ".flyte" / "config.yaml"
    # Inputs and code bundles upload through the store port-forward.
    with _devbox_dashboard().storage_port_forward():
        match argv:
            case ["seed"]:
                flyte.init_from_config(config, root_dir=Path(__file__).parent)
                files = [
                    File.from_local_sync(str(FIXTURES / n)) for n in (REFERENCE, *READS)
                ]
                run = _run(seed, reference=files[0], r1=files[1], r2=files[2])
                print(json.dumps(run.outputs()[0], indent=2))
                return 0
            case ["run", cohort]:
                # The bundle root SDK code gets by default: the repo root.
                flyte.init_from_config(config, root_dir=PROJECT_ROOT)
                run = _run(
                    germline_short_variant_discovery,
                    build=BUILD,
                    sample_ids=[SAMPLE_ID],
                    cohort_id=cohort,
                )
                print(f"output: {run.outputs()[0]}")
                return 0
            case ["check", cohort]:
                flyte.init_from_config(config, root_dir=Path(__file__).parent)
                got = json.loads(_run(check, cohort_id=cohort).outputs()[0])
                print(json.dumps(got, indent=2))
                ok = got["samples"] == [SAMPLE_ID] and got["records"] > 0
                print(
                    "ok" if ok else "MISMATCH: expected NA12829 and at least one record"
                )
                return 0 if ok else 1
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
