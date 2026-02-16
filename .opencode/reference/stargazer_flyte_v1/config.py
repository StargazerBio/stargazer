import logging
from pathlib import Path

# Setup the logger
logger = logging.getLogger(__name__)
console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter("[%(asctime)s %(levelname)s %(name)s] %(message)s")
)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)

# Default args
remote_ref = "https://github.com/unionai-oss/unionbio/raw/main/tests/assets/references/GRCh38_chr21.fasta"
remote_reads = [
    "https://github.com/unionai-oss/unionbio/raw/main/tests/assets/sequences/subsampled/SRR812824-sub_1.fastq",
    "https://github.com/unionai-oss/unionbio/raw/main/tests/assets/sequences/subsampled/SRR812824-sub_2.fastq",
]
remote_rgtag = "@RG\tID:SRR812824\tSM:Sample1\tLB:Library1\tPL:illumina\tPU:SRR812824.2"
remote_sites_vcf = "https://github.com/unionai-oss/unionbio/raw/main/tests/assets/sites/Mills_and_1000G_gold_standard_chr21.indels.hg38.vcf"
remote_sites_idx = "https://github.com/unionai-oss/unionbio/raw/main/tests/assets/sites/Mills_and_1000G_gold_standard_chr21.indels.hg38.vcf.idx"
remote_protein_fasta = "https://rest.uniprot.org/uniprotkb/P42212.fasta"

# Tool config
fastp_cpu = "3"

project_rt = Path(__file__).parent.parent.parent
prod_rt = project_rt.joinpath("src")
ws_rt = project_rt.joinpath("workspaces")
