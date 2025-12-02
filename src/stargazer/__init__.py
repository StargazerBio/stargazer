"""
Stargazer: Bioinformatics workflow orchestration with IPFS and Flyte v2.

Combines IPFS decentralized storage (via Pinata) with Flyte v2 for
computational genomics pipelines. The core innovation is using IPFS Content
Identifiers (CIDs) as universal file identifiers, with query-based dataclass
hydration for bioinformatics-specific types.
"""

__version__ = "0.1.0"

# Pinata client
from stargazer.utils.pinata import (
    PinataClient,
    PinataFile,
)

__all__ = [
    # Version
    "__version__",
    # Pinata
    "PinataClient",
    "PinataFile",
]
