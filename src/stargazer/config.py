import flyte

# Create task environment for Parabricks tools
# Parabricks requires GPU resources
parabricks_env = flyte.TaskEnvironment(
    name="parabricks",
    image=flyte.Image.from_base("nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1"),
    resources=flyte.Resources(
        cpu=8,
        memory="32Gi",
        gpu="A100:1",  # Parabricks requires GPU
    ),
)