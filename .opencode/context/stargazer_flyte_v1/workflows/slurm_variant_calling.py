from union import ImageSpec, workflow
from flytekitplugins.slurm import SlurmRemoteScript, SlurmTask

image = ImageSpec(
    name="slurm-connector-workflow",
    packages=[
        "git+https://github.com/flyteorg/flytekit.git#plugins/flytekitplugins-slurm"
    ],
    env={"FLYTE_SDK_LOGGING_LEVEL": "10"},
    builder="union",
)

remote_config = {
    "host": "44.223.100.92",
    "username": "ubuntu",
}

bwa = SlurmTask(
    name="bwa",
    task_config=SlurmRemoteScript(
        ssh_config=remote_config,
        batch_script_path="/home/ubuntu/pryce/scripts/bwa.sh",
        batch_script_args=[
            "-r",
            "/home/ubuntu/pryce/outputs/GRCh38_chr21.fasta",
            "-1",
            "/home/ubuntu/pryce/outputs/SRR812824-sub_1.fastq",
            "-2",
            "/home/ubuntu/pryce/outputs/SRR812824-sub_2.fastq",
            "-o",
            "/home/ubuntu/pryce/outputs/SRR812824-sub",
        ],
        sbatch_conf={
            "partition": "debug",
            "job-name": "tiny-slurm",
        },
    ),
)

haplocall = SlurmTask(
    name="haplotype-caller",
    task_config=SlurmRemoteScript(
        ssh_config=remote_config,
        batch_script_path="/home/ubuntu/pryce/scripts/haplocaller.sh",
        batch_script_args=[
            "-r",
            "/home/ubuntu/pryce/outputs/GRCh38_chr21.fasta",
            "-b",
            "/home/ubuntu/pryce/outputs/SRR812824-sub.sorted.bam",
            "-o",
            "/home/ubuntu/pryce/outputs/VCFs",
        ],
        sbatch_conf={
            "partition": "debug",
            "job-name": "tiny-slurm",
        },
    ),
)


@workflow
def wf():
    al = bwa()
    call = haplocall()
    al >> call
