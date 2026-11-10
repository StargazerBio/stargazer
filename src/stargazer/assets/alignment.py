"""
### Alignment asset types for Stargazer.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.assets.asset import Asset


@dataclass
class Alignment(Asset):
    """BAM/CRAM alignment file asset.

    `source_cid` is the CID of the asset this BAM was made from: the R1 reads
    for an aligner's output, the input alignment for every later step.
    `reference_cid` is carried through every step. The format is the file
    name's extension. Fields are kept to what fits a new public file's 9
    metadata keys with the asset type and owner.
    """

    _asset_key: ClassVar[str] = "alignment"
    sample_id: str = ""
    sorted: str = ""
    duplicates_marked: bool = False
    bqsr_applied: bool = False
    tool: str = ""
    reference_cid: str = ""
    source_cid: str = ""


@dataclass
class AlignmentIndex(Asset):
    """BAI/CRAI alignment index file asset.

    A companion: `companion_of` is the CID of the Alignment it indexes.
    """

    _asset_key: ClassVar[str] = "alignment_index"
    sample_id: str = ""
    companion_of: str = ""


@dataclass
class BQSRReport(Asset):
    """BQSR recalibration table produced by GATK BaseRecalibrator.

    Carries alignment_cid linking to the Alignment it was produced from.
    """

    _asset_key: ClassVar[str] = "bqsr_report"
    sample_id: str = ""
    tool: str = ""
    alignment_cid: str = ""


@dataclass
class DuplicateMetrics(Asset):
    """Duplicate metrics text file produced by GATK MarkDuplicates.

    Carries alignment_cid linking to the Alignment it was produced from.
    """

    _asset_key: ClassVar[str] = "duplicate_metrics"
    sample_id: str = ""
    tool: str = ""
    alignment_cid: str = ""
