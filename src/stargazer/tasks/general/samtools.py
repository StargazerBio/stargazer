"""
### Samtools tasks for reference genome indexing.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets import Reference, ReferenceIndex
from stargazer.tasks.gatk.env import gatk_env
from stargazer.utils import run, temp_dir


@gatk_env.task
async def samtools_faidx(ref: Reference) -> ReferenceIndex:
    """
    Create a FASTA index (.fai file) using samtools faidx.

    Args:
        ref: Reference FASTA asset

    Returns:
        ReferenceIndex asset containing the .fai file
    """
    ref_path = await ref.fetch()

    output_dir = temp_dir()
    fai_path = output_dir / f"{ref_path.name}.fai"
    cmd = ["samtools", "faidx", str(ref_path), "--fai-idx", str(fai_path)]
    await run(cmd, cwd=str(output_dir))

    faidx = await ReferenceIndex.store(
        fai_path,
        build=ref.build,
        tool="samtools_faidx",
        companion_of=ref.cid,
    )

    return faidx
