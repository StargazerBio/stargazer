"""
Alignment asset types for Stargazer.
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.types.asset import Asset


@dataclass
class Alignment(Asset):
    """BAM/CRAM alignment file asset.

    Carries reference_cid and r1_cid for provenance (PROV entity derivation).
    """

    _asset_key: ClassVar[str] = "alignment"
    sample_id: str = ""
    format: str = ""
    sorted: str = ""
    duplicates_marked: bool = False
    bqsr_applied: bool = False
    tool: str = ""
    reference_cid: str = ""
    r1_cid: str = ""


@dataclass
class AlignmentIndex(Asset):
    """BAI/CRAI alignment index file asset.

    Carries alignment_cid linking to the Alignment it indexes.
    """

    _asset_key: ClassVar[str] = "alignment_index"
    sample_id: str = ""
    alignment_cid: str = ""


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
