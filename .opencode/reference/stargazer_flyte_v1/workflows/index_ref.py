from flytekit import workflow
from unionbio.config import remote_ref
from unionbio.tasks.utils import fetch_remote_reference
from unionbio.tasks.bwa import bwa_index
from unionbio.types import Reference


@workflow
def wf(ref_url: str = remote_ref) -> Reference:
    # Fetch remote inputs
    ref = fetch_remote_reference(url=ref_url)

    # Generate a bowtie2 index or load it from cache
    return bwa_index(ref=ref)
