"""
### Leiden community detection clustering for scRNA-seq data.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets.scrna import AnnData
from stargazer.tasks.scrna.env import scrna_env
from stargazer.utils import temp_dir


@scrna_env.task
async def cluster(
    adata: AnnData,
    resolution: float = 0.5,
    key_added: str = "leiden",
) -> AnnData:
    """Assign cells to clusters using the Leiden algorithm.

    Requires a precomputed neighbor graph (.uns["neighbors"]).
    Cluster labels are stored in .obs[key_added].

    Args:
        adata: AnnData asset with neighbor graph
        resolution: Leiden resolution parameter (higher = more clusters)
        key_added: .obs column name to store cluster labels

    Returns:
        AnnData asset with cluster labels in .obs
    """
    import scanpy as sc

    ad = sc.read_h5ad(await adata.fetch())

    sc.tl.leiden(
        ad, flavor="igraph", n_iterations=2, resolution=resolution, key_added=key_added
    )

    out_path = temp_dir() / f"{adata.sample_id}_clustered.h5ad"
    ad.write_h5ad(out_path)

    result = await AnnData.store(
        out_path,
        sample_id=adata.sample_id,
        organism=adata.organism,
        source_cid=adata.cid,
        n_obs=ad.n_obs,
        n_vars=ad.n_vars,
        stage="clustered",
    )
    return result
