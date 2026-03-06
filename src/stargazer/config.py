import flyte

# GATK task environment for GATK-specific tools
# Uses GATK image with Java runtime and GATK tools
gatk_env = flyte.TaskEnvironment(
    name="gatk",
    image=flyte.Image.from_base("broadinstitute/gatk"),
    resources=flyte.Resources(
        cpu=4,
        memory="16Gi",
    ),
    cache="auto",
)
