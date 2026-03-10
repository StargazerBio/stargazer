"""
### Task environment and logger configuration for Stargazer.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

import flyte
from loguru import logger as logger  # noqa: PLC0414

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
