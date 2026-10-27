"""
### Notebook asset type for Stargazer.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.assets.asset import Asset


@dataclass
class Notebook(Asset):
    """A marimo notebook published from a user's workspace to the public tier.

    A workspace notebook is a plain file until its owner publishes it from
    the dashboard, which is the only thing that creates one. `title` and
    `description` are the notebook's declared `main_name` and
    `main_description`, and `slug` is its workspace filename's stem, which
    ties the public record to the notebook it came from.
    """

    _asset_key: ClassVar[str] = "notebook"
    title: str = ""
    description: str = ""
    slug: str = ""
