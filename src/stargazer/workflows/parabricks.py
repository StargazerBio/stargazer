"""
Reference genome indexing workflow.

This workflow chains together:
1. Setup task to create a Reference object from a FASTA file
2. samtools faidx to create FASTA index
3. bwa index to create BWA alignment indices
"""
import flyte
from pathlib import Path

from stargazer.types import Reference
from stargazer.config import pb_env
from stargazer.tasks.samtools import samtools_faidx
from stargazer.tasks.bwa import bwa_index


@pb_env.task
async def wgs_call_snv(
    ref_name: str
) -> Reference:
    """
    Complete reference genome indexing workflow.

    Chains together:
    1. Create Reference object
    2. Run samtools faidx to create .fai index
    3. Run bwa index to create BWA alignment indices

    Args:
        fasta_path: Path to the local FASTA file
        ref_name: Optional name for the reference (defaults to filename)

    Returns:
        Reference object with FASTA, .fai, and BWA index files

    Example:
        flyte.init_from_config()
        run = flyte.run(
            wgs_call_snv,
            fasta_path="/data/genome.fa",
            ref_name="genome.fa"
        )
        print(run.url)
    """
    # Step 1: Create Reference object
    ref = await Reference.pinata_hydrate(ref_name=ref_name)

    # # Step 2: Create FASTA index with samtools
    # ref = await samtools_faidx(ref)

    # # Step 3: Create BWA index
    # ref = await bwa_index(ref)

    return ref

if __name__ == "__main__":
    import pprint
    flyte.init_from_config()
    r =  flyte.with_runcontext(mode="local").run(wgs_call_snv, ref_name="GRCh38_chr21.fasta")
    r.wait()
    pprint.pprint(r.outputs)
