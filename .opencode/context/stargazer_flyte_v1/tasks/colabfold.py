import os
import time
import base64
import subprocess
from io import BytesIO
from pathlib import Path
from flytekit import task, current_context, Resources, Deck
from flytekit.types.file import FlyteFile
from flytekit.types.directory import FlyteDirectory
from flytekit.extras.tasks.shell import subproc_execute
from union.actor import ActorEnvironment
from unionbio.config import logger
from unionbio.images import colabfold_img
from unionbio.types import Protein

DB_LOC = "/home/flytekit/colabfold_dbs"
MMCIF_LOC = str(Path(DB_LOC).joinpath("pdb"))
CPU = "30"

actor = ActorEnvironment(
    name="colabfold-actor",
    replica_count=1,
    ttl_seconds=600,
    requests=Resources(
        cpu=CPU,
        mem="100Gi",
        gpu="1",
    ),
    container_image=colabfold_img,
)


@actor.task
def sync_dbs(
    uris: list[str],
    output_loc: str = DB_LOC,
) -> str:
    os.makedirs(output_loc, exist_ok=True)

    for uri in uris:
        dl_cmd = [
            "gcloud",
            "storage",
            "rsync",
            "-R",
            uri,
            output_loc,
        ]

        cmd_str = " ".join(dl_cmd)
        logger.info(f"Downloading databases with command: {cmd_str}")
        start = time.time()
        subproc_execute(command=cmd_str, shell=True)
        elapsed = time.time() - start
        logger.info(f"Downloaded in {elapsed} seconds ({elapsed / 3600} hours)")
        logger.debug(f"Database files: {os.listdir(output_loc)}")

    return output_loc


@actor.task
def sync_mmcif(
    uri: str,
    output_loc: str = MMCIF_LOC,
) -> str:
    import zstandard as zstd
    import tarfile

    temp_dir = "/tmp/mmcif/"
    os.makedirs(output_loc, exist_ok=True)

    dl_cmd = [
        "gcloud",
        "storage",
        "rsync",
        "-R",
        uri,
        temp_dir,
    ]

    cmd_str = " ".join(dl_cmd)
    logger.info(f"Downloading databases with command: {cmd_str}")
    start = time.time()
    subproc_execute(command=cmd_str, shell=True)
    elapsed = time.time() - start
    logger.info(f"Downloaded in {elapsed} seconds ({elapsed / 3600} hours)")
    logger.debug(f"Database files: {os.listdir(temp_dir)}")

    # Loop over each file in the source directory
    for filename in os.listdir(temp_dir):
        if filename.endswith(".tar.zst"):
            src_path = os.path.join(temp_dir, filename)
            print(f"Decompressing {src_path}...")

            # Decompress the .zst file
            with open(src_path, "rb") as compressed_file:
                decompressor = zstd.ZstdDecompressor()
                with decompressor.stream_reader(compressed_file) as decompressed_stream:
                    # Extract the .tar content from the decompressed stream
                    with tarfile.open(fileobj=decompressed_stream, mode="r:") as tar:
                        tar.extractall(path=output_loc)

            print(f"Decompressed and extracted {src_path} to {output_loc}")

    return output_loc


@actor.task
def cf_search(
    prot: Protein,
    db_path: str = DB_LOC,
    outdir: str | None = None,
    search_args: list[str] | None = None,
) -> Protein:
    outdir = outdir or str(
        Path(current_context().working_directory).joinpath("outputs")
    )
    seq = prot.sequence.download()

    t = time.time()
    cmd = ["colabfold_search"]

    if search_args:
        cmd.extend(search_args)
    else:
        cmd.extend(
            [
                "--use-env",
                "1",
                "--use-templates",
                "1",
                "--db-load-mode",
                "2",
                "--db2",
                "pdb100_230517",
                "--threads",
                CPU,
            ]
        )

    cmd.extend([seq, db_path, outdir])

    logger.debug(f"Running MMSeqs search on {seq} with command:")
    logger.debug(" ".join(cmd))
    proc = subproc_execute(cmd)
    logger.debug(proc.output)
    logger.info(f"Created the following outputs in {time.time() - t} seconds:")
    logger.info(f"MSA files in {Path(outdir).resolve()}: {os.listdir(outdir)}")

    for fn in Path(outdir).iterdir():
        path = fn.resolve()
        if path.suffix == ".m8":
            prot.hitfile = FlyteFile(path=str(path))
        if path.suffix == ".a3m":
            prot.msa = FlyteFile(path=str(path))

    logger.debug(f"Returning {prot}")

    return prot


@actor.task
def af_predict_local(
    prot: Protein,
    mmcif_loc: str = MMCIF_LOC,
    outdir: str | None = None,
    batch_args: list[str] | None = None,
) -> Protein:
    outdir = outdir or str(
        Path(current_context().working_directory).joinpath("outputs")
    )
    msa = prot.msa.download()
    hits = prot.hitfile.download()
    logger.info(f"Running AlphaFold on {msa} and {hits}")

    t = time.time()
    cmd = [
        "colabfold_batch",
    ]

    if batch_args:
        cmd.extend(batch_args)
    else:
        cmd.extend(
            [
                "--amber",
                "--use-gpu-relax",
                "--random-seed",
                "0",
            ]
        )

    cmd.extend(
        [
            "--templates",
            "--pdb-hit-file",
            str(hits),
            "--local-pdb-path",
            mmcif_loc,
            str(msa),
            outdir,
        ]
    )

    logger.debug("Executing:")
    logger.debug(" ".join(cmd))
    proc = subproc_execute(cmd)
    logger.debug(proc.output)
    logger.info(f"Created the following outputs in {time.time() - t} seconds:")
    logger.info(f"Output files in {Path(outdir).resolve()}: {os.listdir(outdir)}")

    prot.predict_out = FlyteDirectory(path=outdir)
    return prot


@task(container_image=colabfold_img, requests=Resources(cpu="10", mem="50Gi", gpu="1"))
def af_predict_hosted(prot: Protein, outdir: str | None = None) -> Protein:
    outdir = outdir or str(
        Path(current_context().working_directory).joinpath("outputs")
    )
    seq = prot.sequence.download()

    logger.info(f"Running AlphaFold on {seq}")
    t = time.time()

    print(subprocess.check_output("nvidia-smi"))
    cmd = [
        "colabfold_batch",
        seq,
        outdir,
    ]

    logger.debug("Executing:")
    logger.debug(" ".join(cmd))
    proc = subproc_execute(cmd)
    logger.debug(proc.output)
    logger.info(f"Created the following outputs in {time.time() - t} seconds:")
    logger.info(f"Output files in {Path(outdir).resolve()}: {os.listdir(outdir)}")

    prot.predict_out = FlyteDirectory(path=outdir)
    return prot


@task(enable_deck=True, container_image=colabfold_img)
def visualize(af_res: Protein) -> FlyteFile:
    import plotly
    from graphein.protein.config import ProteinGraphConfig
    from graphein.protein.graphs import construct_graph
    from graphein.protein.visualisation import plotly_protein_structure_graph
    from PIL import Image

    af_dir = af_res.predict_out.download()
    logger.debug(f"Visualizing AlphaFold results in {af_dir}")

    # Select the highest confidence relaxed model
    pdb = list(Path(af_dir).glob("*relaxed_rank_001*"))[0]
    config = ProteinGraphConfig()
    g = construct_graph(config=config, path=pdb)
    p = plotly_protein_structure_graph(
        g,
        colour_edges_by="kind",
        colour_nodes_by="seq_position",
        label_node_ids=False,
        plot_title="Peptide backbone graph. Nodes coloured by position.",
        node_size_multiplier=1,
    )

    # Append structure to deck
    prot_deck = Deck("Structure")
    html = plotly.io.to_html(p)
    prot_deck.append(html)

    # Append prediction quality images to deck
    pred_qual = Deck("Prediction Quality")
    for i in list(Path(af_dir).glob("*.png")):
        with Image.open(i) as img:
            img_bytes = BytesIO()
            img.save(img_bytes, format="PNG")
            image_base64 = base64.b64encode(img_bytes.getvalue()).decode()
            pred_qual.append(
                f'<html><body><img src="data:image/png;base64,{image_base64}"/></body></html>'
            )

    # Write structure to file
    of = "structure.html"
    with open(of, "w") as f:
        p.write_html(f)

    return FlyteFile(path=of)
