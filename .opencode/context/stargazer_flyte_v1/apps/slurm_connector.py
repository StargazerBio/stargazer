from union import ImageSpec, Resources, Secret
from union.app import FlyteConnectorApp

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

slurm_connector_app = FlyteConnectorApp(
    name="slurm-connector-app",
    container_image=image,
    secrets=[Secret(key="flyte_slurm_private_key")],
    limits=Resources(cpu="1", mem="1Gi"),
)
