import os
import shutil
from pathlib import Path
from mashumaro.mixins.json import DataClassJSONMixin
from dataclasses import dataclass
from flytekit import current_context
from flytekit.types.file import FlyteFile
from unionbio.config import logger
from unionbio.tasks.helpers import filter_dir


@dataclass
class VCF(DataClassJSONMixin):
    """
    Represents a VCF (Variant Call Format) file and its associated sample and index.

    This class defines the structure for representing a VCF file along with attributes
    that describe the associated sample and index.

    Attributes:
        sample (str): The name or identifier of the sample to which the VCF file belongs.
        caller (str): The name of the variant caller used to generate the VCF.
        vcf (FlyteFile): The VCF file.
        vcf_idx (FlyteFile): The index file for the VCF.

    """

    sample: str
    caller: str
    vcf: FlyteFile | None = None
    vcf_idx: FlyteFile | None = None

    def _get_state_str(self):
        state = f"{self.sample}_{self.caller}"
        return state

    def get_vcf_fname(self):
        return f"{self._get_state_str()}.g.vcf.gz"

    def get_vcf_idx_fname(self):
        return f"{self._get_state_str()}.g.vcf.gz.tbi"

    def aggregate(self, target: Path = None) -> Path:
        """
        Explicitly aggregate VCF and index into another given directory.
        If None is provided, the current working is used.

        Args:
            target (Path): The target directory to move the VCF and index files to.

        Returns:
            Path: The target directory containing the VCF and index files.
        """
        target = target or Path(current_context().working_directory)
        logger.info(f"Aggregating VCF and index to {target}")
        os.makedirs(target, exist_ok=True)
        self.vcf.download()
        np1 = target.joinpath(Path(self.vcf.path).name)
        if not np1.exists():
            shutil.move(self.vcf.path, np1)
        self.vcf.path = np1

        if self.vcf_idx:
            self.vcf_idx.download()
            np2 = target.joinpath(Path(self.vcf_idx.path).name)
            if not np2.exists():
                shutil.move(self.vcf_idx.path, np2)
            self.vcf_idx.path = np2

    @classmethod
    def make_all(
        cls, dir: Path, include: list[str] = ["*.vcf*"], exclude: list[str] = []
    ) -> list:
        samples = {}
        for fp in filter_dir(dir, include=include, exclude=exclude):
            stem = str(fp.stem).split(".")[0]
            sample, caller = stem.split("_")[0:2]

            if sample not in samples:
                samples[sample] = cls(sample=sample, caller=caller)

            if "tbi" in fp.name or "idx" in fp.name:
                samples[sample].vcf_idx = FlyteFile(path=str(fp))
            if "vcf" in fp.name and "tbi" not in fp.name and "idx" not in fp.name:
                samples[sample].vcf = FlyteFile(path=str(fp))

        logger.info(f"Created following VCF objects from {dir}: {samples}")
        return list(samples.values())
