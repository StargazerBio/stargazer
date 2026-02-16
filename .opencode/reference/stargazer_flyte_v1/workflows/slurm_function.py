from union import ImageSpec, task, workflow
from flytekitplugins.slurm import SlurmFunction

image = ImageSpec(
    name="flyteconnector",
    packages=[
        "flytekitplugins-slurm==1.15.3",
        "flytekit[connector]==1.16.0b0",
        "union",
        "union-runtime",
    ],
    apt_packages=[
        "git",
        "build-essential",
        "libmagic1",
        "vim",
        "openssh-client",
        "ca-certificates",
    ],
    env={"FLYTE_SDK_LOGGING_LEVEL": "10"},
    builder="union",
)


@task(
    container_image=image,
    task_config=SlurmFunction(
        ssh_config={
            "host": "44.223.100.92",
            "username": "ubuntu",
        },
        sbatch_conf={
            "partition": "debug",
            "job-name": "tiny-slurm",
            "output": "/home/ubuntu/fn_task.log",
        },
        script="""#!/bin/bash -i
echo Run function with sbatch...
# Run the user-defined task function
{task.fn}
""",
    ),
)
def plus_one(x: int) -> int:
    return x + 1


@task(container_image=image)
def greet(year: int) -> str:
    return f"Hello {year}!!!"


@workflow
def fn_wf(x: int) -> str:
    x = plus_one(x=x)
    msg = greet(year=x)
    return msg
