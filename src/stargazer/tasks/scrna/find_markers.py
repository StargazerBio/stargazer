"""
### Marker gene identification via differential expression for scRNA-seq data.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets.scrna import AnnData
from stargazer.tasks.scrna.env import scrna_env
from stargazer.utils import temp_dir


@scrna_env.task
async def find_markers(
    adata: AnnData,
    groupby: str = "leiden",
    method: str = "wilcoxon",
) -> AnnData:
    """Identify marker genes for each cluster using differential expression.

    Tests the log-normalized expression in .X, which scanpy's fold changes
    assume; the raw counts in .layers["counts"] would skew them.
    Results are stored in .uns["rank_genes_groups"].

    Args:
        adata: Clustered AnnData asset with log-normalized .X
        groupby: .obs column to group cells by (cluster labels)
        method: Statistical test method ("wilcoxon", "t-test", etc.)

    Returns:
        AnnData asset with ranked marker genes in .uns["rank_genes_groups"]
    """
    import scanpy as sc

    ad = sc.read_h5ad(await adata.fetch())

    sc.tl.rank_genes_groups(ad, groupby=groupby, method=method)

    out_path = temp_dir() / f"{adata.sample_id}_markers.h5ad"
    ad.write_h5ad(out_path)

    result = await AnnData.store(
        out_path,
        sample_id=adata.sample_id,
        organism=adata.organism,
        source_cid=adata.cid,
        n_obs=ad.n_obs,
        n_vars=ad.n_vars,
        stage="annotated",
    )
    return result
