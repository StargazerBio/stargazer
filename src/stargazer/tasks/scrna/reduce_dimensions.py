"""
### PCA, neighbor graph, and UMAP dimensionality reduction for scRNA-seq data.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets.scrna import AnnData
from stargazer.tasks.scrna.env import scrna_env
from stargazer.utils import scratch_dir


@scrna_env.task
async def reduce_dimensions(
    adata: AnnData,
    n_pcs: int = 50,
    n_neighbors: int = 15,
) -> AnnData:
    """Compute PCA, k-nearest neighbor graph, and UMAP embedding.

    Operates on the highly variable gene subset to reduce noise. Embeddings
    are stored in .obsm for downstream clustering and visualization.

    Args:
        adata: AnnData asset with HVG annotations in .var
        n_pcs: Number of principal components to compute
        n_neighbors: Number of neighbors for the kNN graph

    Returns:
        AnnData asset with PCA (.obsm["X_pca"]), neighbors, and UMAP (.obsm["X_umap"])
    """
    import scanpy as sc

    ad = sc.read_h5ad(await adata.fetch())

    sc.tl.pca(ad, n_comps=n_pcs)
    sc.pp.neighbors(ad, n_neighbors=n_neighbors, n_pcs=n_pcs)
    sc.tl.umap(ad)

    out_path = scratch_dir() / f"{adata.sample_id}_reduced.h5ad"
    ad.write_h5ad(out_path)

    result = await AnnData.store(
        out_path,
        sample_id=adata.sample_id,
        organism=adata.organism,
        source_cid=adata.cid,
        n_obs=ad.n_obs,
        n_vars=ad.n_vars,
        stage="reduced",
    )
    return result
