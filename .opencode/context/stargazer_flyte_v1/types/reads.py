import os
import shutil
from mashumaro.mixins.json import DataClassJSONMixin
from dataclasses import dataclass
from flytekit.types.file import FlyteFile
from flytekit import current_context
from pathlib import Path
from unionbio.config import logger
from unionbio.tasks.helpers import filter_dir


@dataclass
class Reads(DataClassJSONMixin):
    """
    Represents a sequencing reads sample via its associated fastq files.

    This class defines the structure for representing a sequencing sample. It includes
    attributes for the sample name and paths to the read files (R1 and R2).

    Attributes:
        sample (str): The name or identifier of the raw sequencing sample.
        filtered (bool): A boolean value indicating whether the reads have been filtered.
        filt_report (FlyteFile): A FlyteFile object representing the path to the filter report.
        uread (FlyteFile): A FlyteFile object representing the path to the unpaired read file.
        read1 (FlyteFile): A FlyteFile object representing the path to the raw R1 read file.
        read2 (FlyteFile): A FlyteFile object representing the path to the raw R2 read file.
    """

    sample: str
    filtered: bool | None = None
    filt_report: FlyteFile | None = None
    uread: FlyteFile | None = None
    read1: FlyteFile | None = None
    read2: FlyteFile | None = None

    def get_read_fnames(self):
        filt = "filt." if self.filtered else ""
        return (
            f"{self.sample}_1.{filt}fastq.gz",
            f"{self.sample}_2.{filt}fastq.gz",
        )

    def get_report_fname(self):
        return f"{self.sample}_fastq-filter-report.json"

    def aggregate(self, target: Path = None) -> Path:
        """
        Explicitly aggregate Reads files into another given directory.
        If None is provided, the current working is used.

        Args:
            target (Path): The target directory to move the reference files to.

        Returns:
            Path: The target directory containing the reference files.
        """
        target = target or Path(current_context().working_directory)
        logger.info(f"Aggregating Reads files to {target}")
        os.makedirs(target, exist_ok=True)
        if self.uread:
            self.uread.download()
            np = target.joinpath(Path(self.uread.path).name)
            if not np.exists():
                shutil.move(self.uread.path, target)
                self.uread.path = np
        elif self.read1 and self.read2:
            self.read1.download()
            self.read2.download()
            np1 = target.joinpath(Path(self.read1.path).name)
            np2 = target.joinpath(Path(self.read2.path).name)
            if not all([np1.exists(), np2.exists()]):
                shutil.move(self.read1.path, np1)
                shutil.move(self.read2.path, np2)
            self.read1.path = np1
            self.read2.path = np2
        else:
            logger.error("No read files found to aggregate!")
        return target

    @classmethod
    def make_all(
        cls, dir: Path, include: list[str] = ["*fast*"], exclude: list[str] = []
    ):
        samples = {}
        for fp in filter_dir(dir, include=include, exclude=exclude):
            logger.debug(f"Processing {fp}")
            fn = fp.name
            pfn = Path(fn)
            sufs = fp.suffixes
            while pfn.suffix:
                pfn = pfn.with_suffix("")
            fns = str(pfn).split("_")
            sample = fns[0]
            logger.debug(f"Found sample {sample}")

            if sample not in samples:
                samples[sample] = cls(sample=sample)

            if any(s in sufs for s in [".fastq", ".fasta", ".fq"]):
                mate = fns[-1]
                logger.debug(f"Found mate {mate} for {sample}")
                if "1" in mate:
                    samples[sample].read1 = FlyteFile(path=str(fp))
                elif "2" in mate:
                    samples[sample].read2 = FlyteFile(path=str(fp))
                else:
                    samples[sample].uread = FlyteFile(path=str(fp))
            elif "filter-report" in fn and ".json" in sufs:
                logger.debug(f"Found filter report for {sample}")
                samples[sample].filtered = True
                samples[sample].filt_report = FlyteFile(path=str(fp))

        logger.info(f"Created {samples} from {dir}")
        return list(samples.values())
