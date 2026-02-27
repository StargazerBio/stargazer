"""
GATK CreateSequenceDictionary task for reference genome.
"""

from stargazer.types import Reference
from stargazer.types.reference import SequenceDict
from stargazer.config import gatk_env
from stargazer.utils import _run


@gatk_env.task
async def create_sequence_dictionary(ref: Reference) -> Reference:
    """
    Create a sequence dictionary (.dict file) using GATK CreateSequenceDictionary.

    Args:
        ref: Reference object containing the FASTA file

    Returns:
        Reference object with the .dict sequence dictionary file added
    """
    # Fetch all reference files to cache
    await ref.fetch()

    # Get the cached reference file path
    if not ref.fasta or not ref.fasta.path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_file_path = ref.fasta.path

    # Verify the reference file exists
    if not ref_file_path.exists():
        raise FileNotFoundError(f"Reference file {ref.build} not found in cache")

    # Check if we already have the .dict
    if ref.sequence_dictionary is not None:
        return ref

    # Run GATK CreateSequenceDictionary
    dict_path = ref_file_path.parent / f"{ref_file_path.stem}.dict"
    cmd = [
        "gatk",
        "CreateSequenceDictionary",
        "-R",
        str(ref_file_path),
        "-O",
        str(dict_path),
    ]
    await _run(cmd, cwd=str(ref_file_path.parent))

    if not dict_path.exists():
        raise FileNotFoundError(
            f"Sequence dictionary file {dict_path.name} was not created"
        )

    # Upload .dict file and attach to reference
    seq_dict = SequenceDict()
    await seq_dict.update(
        dict_path, build=ref.build, tool="gatk_CreateSequenceDictionary"
    )
    ref.sequence_dictionary = seq_dict

    return ref
