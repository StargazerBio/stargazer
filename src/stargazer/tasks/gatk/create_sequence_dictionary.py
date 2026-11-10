"""
### GATK CreateSequenceDictionary task for reference genome.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets import Reference, SequenceDict
from stargazer.tasks.gatk.env import gatk_env
from stargazer.utils import run, scratch_dir


@gatk_env.task
async def create_sequence_dictionary(ref: Reference) -> SequenceDict:
    """
    Create a sequence dictionary (.dict file) using GATK CreateSequenceDictionary.

    Args:
        ref: Reference FASTA asset

    Returns:
        SequenceDict asset containing the .dict file
    """
    ref_path = await ref.fetch()

    output_dir = scratch_dir()
    dict_path = output_dir / f"{ref_path.stem}.dict"
    dict_path.unlink(missing_ok=True)
    cmd = [
        "gatk",
        "CreateSequenceDictionary",
        "-R",
        str(ref_path),
        "-O",
        str(dict_path),
    ]
    await run(cmd, cwd=str(output_dir))

    seq_dict = await SequenceDict.store(
        dict_path,
        build=ref.build,
        tool="gatk_CreateSequenceDictionary",
        companion_of=ref.cid,
    )

    return seq_dict
