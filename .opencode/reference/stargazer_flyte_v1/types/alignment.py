import os
import shutil
from mashumaro.mixins.json import DataClassJSONMixin
from dataclasses import dataclass, fields
from flytekit import current_context
from flytekit.types.file import FlyteFile
from pathlib import Path
from unionbio.config import logger
from unionbio.tasks.helpers import filter_dir


@dataclass
class Alignment(DataClassJSONMixin):
    """
    Represents a SAM (Sequence Alignment/Map) file and its associated sample and report.

    This class defines the structure for representing a SAM file along with attributes
    that describe the associated sample and report.

    Attributes:
        sample (str): The name or identifier of the sample to which the SAM file belongs.
        aligner (str): The name of the aligner used to generate the SAM file.
        alignment (FlyteFile): A FlyteFile object representing the path to the alignment file.
        alignment_report (FlyteFile): A FlyteFile object representing an associated report
            for performance of the aligner.
        sorted (bool): A boolean value indicating whether the SAM file has been sorted.
        deduped (bool): A boolean value indicating whether the SAM file has been deduplicated.
        bqsr_report (FlyteFile): A FlyteFile object representing a report from the Base Quality
            Score Recalibration (BQSR) process.
    """

    sample: str
    aligner: str
    format: str | None = None
    alignment: FlyteFile | None = None
    alignment_idx: FlyteFile | None = None
    alignment_report: FlyteFile | None = None
    sorted: bool | None = None
    deduped: bool | None = None
    recalibrated: bool | None = None
    dedup_metrics: FlyteFile | None = None
    bqsr_report: FlyteFile | None = None

    def _get_state_str(self):
        state = f"{self.sample}_{self.aligner}"
        if self.sorted:
            state += "_sorted"
        if self.deduped:
            state += "_deduped"
        if self.recalibrated:
            state += "_recal"
        return state

    def get_alignment_fname(self):
        return f"{self._get_state_str()}_aligned.{self.format}"

    def get_alignment_idx_fname(self):
        return f"{self._get_state_str()}_aligned.bam.bai"

    def get_report_fname(self):
        return f"{self._get_state_str()}_aligned_report.txt"

    def get_bqsr_fname(self):
        return f"{self._get_state_str()}_bqsr.table"

    def get_metrics_fname(self):
        return f"{self._get_state_str()}_metrics.txt"

    def aggregate(self, target: Path = None) -> Path:
        """
        Explicitly aggregate alignment and supporting files into another given directory.
        If None is provided, the current working is used.

        Args:
            target (Path): The target directory to move the VCF and index files to.

        Returns:
            Path: The target directory containing the VCF and index files.
        """
        target = target or Path(current_context().working_directory)
        logger.info(f"Aggregating alignment files to {target}")
        os.makedirs(target, exist_ok=True)
        for field in fields(self):
            at = getattr(self, field.name)
            if isinstance(at, FlyteFile):
                at.download()
                np = target.joinpath(Path(at.path).name)
                if not np.exists():
                    shutil.move(at.path, np)
                setattr(self, field.name, FlyteFile(path=np))
        return target

    @classmethod
    def make_all(
        cls,
        dir: Path,
        include: list[str] = ["*.bam*", "*.sam", "*report*"],
        exclude: list[str] = [],
    ) -> list:
        samples = {}
        for fp in filter_dir(dir, include=include, exclude=exclude):
            sample, aligner = fp.stem.split("_")[0:2]

            if sample not in samples:
                samples[sample] = cls(sample=sample, aligner=aligner)

            if "sorted" in fp.name:
                samples[sample].sorted = True
            else:
                samples[sample].sorted = False

            if "deduped" in fp.name:
                samples[sample].deduped = True
            else:
                samples[sample].deduped = False

            if "recal" in fp.name:
                samples[sample].recalibrated = True
            else:
                samples[sample].recalibrated = False

            if fp.name.endswith("bam"):
                samples[sample].format = "bam"
                samples[sample].alignment = FlyteFile(path=str(fp))
            elif fp.name.endswith("bam.bai"):
                samples[sample].alignment_idx = FlyteFile(path=str(fp))
            elif "sam" in fp.name:
                samples[sample].format = "sam"
                samples[sample].alignment = FlyteFile(path=str(fp))
            elif "report" in fp.name:
                samples[sample].alignment_report = FlyteFile(path=str(fp))

        logger.info(f"Created following Alignment objects from {dir}: {samples}")
        return list(samples.values())
