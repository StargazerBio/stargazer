"""
### Quality control and cell/gene filtering for scRNA-seq data.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

import stargazer.utils.storage as _storage
from stargazer.assets.scrna import AnnData
from stargazer.config import logger, scrna_env

# Mitochondrial prefix, ribosomal prefixes and hemoglobin pattern per organism.
# Mouse gene symbols are title case, human ones upper case.
GENE_PATTERNS = {
    "human": ("MT-", ("RPS", "RPL"), "^HB[^(P)]"),
    "mouse": ("mt-", ("Rps", "Rpl"), "^Hb[^(p)]"),
}


@scrna_env.task
async def qc_filter(
    adata: AnnData,
    min_genes: int = 100,
    min_cells: int = 3,
    max_pct_mt: float = 20.0,
    batch_key: str = "",
) -> AnnData:
    """Filter low-quality cells and genes from raw scRNA-seq data.

    Applies standard QC filters: minimum gene/cell thresholds, mitochondrial
    gene percentage, and scrublet doublet detection. The mitochondrial,
    ribosomal and hemoglobin genes are picked by the input asset's
    `organism` ("human" or "mouse", any case).

    Args:
        adata: Raw AnnData asset (.h5ad)
        min_genes: Minimum number of genes expressed per cell
        min_cells: Minimum number of cells a gene must be expressed in
        max_pct_mt: Maximum mitochondrial gene percentage allowed per cell
        batch_key: Column in .obs to use as batch for scrublet (empty = no batch)

    Returns:
        Filtered AnnData asset with QC metrics in .obs

    Raises:
        ValueError: If the asset's `organism` is empty or not a supported one.
    """
    import scanpy as sc

    logger.info(adata.to_dict())
    patterns = GENE_PATTERNS.get(adata.organism.lower())
    if patterns is None:
        raise ValueError(
            f"AnnData {adata.sample_id!r} has organism {adata.organism!r}; "
            f"set its organism field to one of: {', '.join(GENE_PATTERNS)}"
        )
    mt, ribo, hb = patterns
    ad = sc.read_h5ad(await adata.fetch())

    sc.pp.filter_cells(ad, min_genes=min_genes)
    sc.pp.filter_genes(ad, min_cells=min_cells)

    ad.var["mt"] = ad.var_names.str.startswith(mt)
    ad.var["ribo"] = ad.var_names.str.startswith(ribo)
    ad.var["hb"] = ad.var_names.str.contains(hb)

    sc.pp.calculate_qc_metrics(
        ad, qc_vars=["mt", "ribo", "hb"], inplace=True, log1p=True
    )

    sc.pp.scrublet(ad, batch_key=batch_key or None)

    ad = ad[ad.obs["pct_counts_mt"] < max_pct_mt]
    ad = ad[~ad.obs["predicted_doublet"]]

    out_path = _storage.default_client.local_dir / f"{adata.sample_id}_qc_filtered.h5ad"
    ad.write_h5ad(out_path)

    result = AnnData(
        sample_id=adata.sample_id,
        organism=adata.organism,
        source_cid=adata.cid,
    )
    await result.update(out_path, n_obs=ad.n_obs, n_vars=ad.n_vars, stage="qc_filtered")
    logger.info(result.to_dict())
    return result
