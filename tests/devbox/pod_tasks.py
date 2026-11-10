"""Tasks the devbox tests run in pods.

Imported in those pods from the code bundle, so it imports only what
`gatk_env`'s image carries (stargazer and its dependencies), and nothing
from the tests' conftest.
"""

import json
from pathlib import Path

import flyte
from flyte.io import File

from stargazer.assets import R1, R2, Reference
from stargazer.assets.asset import Asset, assemble
from stargazer.config import STARGAZER_ENV_VARS
from stargazer.tasks.gatk.env import gatk_env
from stargazer.utils.storage import get_client

BUILD = "GRCh38"
SAMPLE_ID = "NA12829"
REFERENCE = "GRCh38_TP53.fa"
READS = ("NA12829_TP53_R1.fq.gz", "NA12829_TP53_R2.fq.gz")

env = flyte.TaskEnvironment(
    name="sg_devbox_tests",
    image=gatk_env.image,
    env_vars=STARGAZER_ENV_VARS,
    resources=flyte.Resources(cpu=1, memory=("256Mi", "512Mi")),
)


@env.task
async def produce(n: int, tag: str) -> list[str]:
    """Write n small files and store each as an asset; return their CIDs."""
    cids = []
    for i in range(n):
        path = get_client().local_dir / f"probe_{tag}_{i}.txt"
        path.write_text(f"{tag}:{i}")
        asset = await Asset.store(
            path, keyvalues={"asset": "devbox_probe", "tag": tag, "i": str(i)}
        )
        cids.append(asset.cid)
    return cids


@env.task
async def consume(tag: str) -> list[str]:
    """Find the tag's assets through the index and read each one back."""
    found = await assemble(asset="devbox_probe", tag=tag)
    return sorted([(await a.fetch()).read_text() for a in found])


@env.task
async def store_lane_r1(lane: str) -> R1:
    """Store an R1 carrying an extra `lane` key; return it."""
    path = get_client().local_dir / f"lane_{lane}.fq"
    path.write_text(f"@{lane}\nACGT\n+\nIIII\n")
    r1 = await R1.store(path, sample_id=lane, keyvalues={"lane": lane})
    return r1


def _describe(asset: Asset) -> dict:
    """What the extras test compares: the class, the file and the extra keys."""
    return {
        "type": type(asset).__name__,
        "cid": asset.cid,
        "keyvalues": asset.keyvalues,
    }


@env.task
async def describe_lane_r1s(handed: R1, lane: str) -> str:
    """Describe the R1 handed in, then each R1 `assemble(lane=...)` finds, as JSON."""
    found = await assemble(asset="r1", lane=lane)
    return json.dumps([_describe(a) for a in [handed, *found]])


@env.task
async def lane_round_trip(lane: str) -> str:
    """Store an R1 with an extra key in one pod and inspect it from another."""
    return await describe_lane_r1s(await store_lane_r1(lane), lane)


async def _local_copy(file: File, name: str) -> Path:
    """Download `file` into the cache directory under its original name."""
    dest = get_client().local_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    return Path(await file.download(dest))


@env.task
async def seed(reference: File, r1: File, r2: File) -> dict[str, str]:
    """Store the reference and the paired reads as assets; return their CIDs."""
    ref = await Reference.store(await _local_copy(reference, REFERENCE), build=BUILD)
    r1_path = await _local_copy(r1, READS[0])
    r2_path = await _local_copy(r2, READS[1])
    reads_1 = await R1.store(r1_path, sample_id=SAMPLE_ID)
    reads_2 = await R2.store(r2_path, sample_id=SAMPLE_ID, mate_cid=reads_1.cid)
    reads_1.mate_cid = reads_2.cid
    await get_client().upload(reads_1, r1_path)
    return {"reference": ref.cid, "r1": reads_1.cid, "r2": reads_2.cid}


@env.task
async def check(cohort_id: str) -> str:
    """Find the cohort's VCF, fetch it, and summarize it as JSON."""
    found = await assemble(asset="variants", sample_id=cohort_id)
    if len(found) != 1:
        raise ValueError(
            f"expected one VCF for cohort {cohort_id!r}, found {len(found)}"
        )
    lines = (await found[0].fetch()).read_text().splitlines()
    header = next(line for line in lines if line.startswith("#CHROM"))
    records = [line.split("\t") for line in lines if line and not line.startswith("#")]
    return json.dumps(
        {
            "samples": header.split("\t")[9:],
            "records": len(records),
            "contigs": sorted({r[0] for r in records}),
        }
    )
