"""
### Normalization and log transformation for scRNA-seq data.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets.scrna import AnnData
from stargazer.tasks.scrna.env import scrna_env
from stargazer.utils import temp_dir


@scrna_env.task
async def normalize(adata: AnnData) -> AnnData:
    """Normalize counts and apply log1p transformation.

    Stores raw counts in .layers["counts"] before normalization so they
    are available for downstream differential expression analysis.

    Args:
        adata: QC-filtered AnnData asset

    Returns:
        Normalized and log-transformed AnnData asset
    """
    import scanpy as sc

    ad = sc.read_h5ad(await adata.fetch())

    ad.layers["counts"] = ad.X.copy()
    sc.pp.normalize_total(ad)
    sc.pp.log1p(ad)

    out_path = temp_dir() / f"{adata.sample_id}_normalized.h5ad"
    ad.write_h5ad(out_path)

    result = await AnnData.store(
        out_path,
        sample_id=adata.sample_id,
        organism=adata.organism,
        source_cid=adata.cid,
        n_obs=ad.n_obs,
        n_vars=ad.n_vars,
        stage="normalized",
    )
    return result
