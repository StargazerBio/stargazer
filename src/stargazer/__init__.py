"""
### Stargazer: bioinformatics workflow orchestration on Flyte v2.

Every file is a typed asset identified by its IPFS CID, computed locally
from the bytes. The bytes live in an object store, the metadata in a
queryable index, and shared public data on Pinata's public network; tasks
find their inputs by querying that metadata rather than by path.

spec: [docs/architecture/overview.md](../architecture/overview.md)
"""

__version__ = "0.1.0"

from stargazer.utils.pinata import PinataClient
from stargazer.utils.storage import StorageClient, default_client, get_client

__all__ = [
    "PinataClient",
    "StorageClient",
    "__version__",
    "default_client",
    "get_client",
]
