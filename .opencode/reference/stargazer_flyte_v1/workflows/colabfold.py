from flytekit import workflow
from flytekit.types.file import FlyteFile
from unionbio.tasks.colabfold import (
    sync_dbs,
    sync_mmcif,
    cf_search,
    af_predict_local,
    af_predict_hosted,
    visualize,
)
from unionbio.config import remote_protein_fasta
from unionbio.tasks.utils import fetch_remote_protein


@workflow
def cf_wf(
    db_uris: list[str], mmcif_uri: str, fasta: str = remote_protein_fasta
) -> FlyteFile:
    db_path = sync_dbs(uris=db_uris)
    mmcif_path = sync_mmcif(uri=mmcif_uri)
    prot = fetch_remote_protein(urls=[fasta])
    hitfile, msa = cf_search(prot=prot, db_path=db_path)
    af = af_predict_local(hitfile=hitfile, msa=msa, mmcif_loc=mmcif_path)
    return visualize(af_res=af)


@workflow
def cf_wf_lite(fasta: str = remote_protein_fasta) -> FlyteFile:
    prot = fetch_remote_protein(urls=[fasta])
    predicted = af_predict_hosted(prot=prot)
    return visualize(af_res=predicted)
