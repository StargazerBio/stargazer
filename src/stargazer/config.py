import flyte

# Default task environment for standard bioinformatics tools (CPU-based)
# Uses base Python image with common bioinformatics tools installed
default_env = flyte.TaskEnvironment(
    name="default",
    image=flyte.Image.from_base("broadinstitute/gatk"),
    resources=flyte.Resources(
        cpu=4,
        memory="16Gi",
    ),
)
