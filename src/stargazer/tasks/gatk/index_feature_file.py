"""
### GATK IndexFeatureFile task for indexing VCF files.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets import KnownSites, KnownSitesIndex
from stargazer.tasks.gatk.env import gatk_env
from stargazer.utils import run, scratch_dir


@gatk_env.task
async def index_feature_file(known_sites: KnownSites) -> KnownSitesIndex:
    """
    Index a VCF file using GATK IndexFeatureFile.

    Required by tools like BaseRecalibrator that need random-access queries
    over known sites VCFs.

    Args:
        known_sites: KnownSites VCF asset to index

    Returns:
        KnownSitesIndex asset pointing to the generated .idx file
    """
    vcf_path = await known_sites.fetch()

    output_dir = scratch_dir()
    idx_path = vcf_path.with_suffix(vcf_path.suffix + ".idx")

    if not idx_path.exists():
        await run(
            ["gatk", "IndexFeatureFile", "-I", str(vcf_path)],
            cwd=str(output_dir),
        )

    index = await KnownSitesIndex.store(idx_path, companion_of=known_sites.cid)

    return index
