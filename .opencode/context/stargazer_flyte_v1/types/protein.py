from pathlib import Path
from mashumaro.mixins.json import DataClassJSONMixin
from dataclasses import dataclass
from flytekit.types.file import FlyteFile
from flytekit.types.directory import FlyteDirectory
from unionbio.config import logger
from unionbio.tasks.helpers import filter_dir


@dataclass
class Protein(DataClassJSONMixin):
    """
    Represents a protein sequence and its associated metadata.

    This class defines the structure for representing a protein sequence along with attributes
    that describe the associated metadata.

    Attributes:
        sample (str): The name or identifier of the protein sequence.
        sequence (FlyteFile): A FlyteFile object representing the path to the protein sequence file.
        msa (FlyteFile): A FlyteFile representing evolutionary structural information.
        hitfil (FlyteFile): A FlyteFile capturing search results of similar proteins.
        genes (FlyteFile): A FlyteFile object representing the path to the gene sequence file.
        predict_out (FlyteDirectory): A FlyteDirectory object representing predicted structure files and associated
            confidence scores.

    """

    sample: str
    sequence: FlyteFile | None = None
    msa: FlyteFile | None = None
    hitfile: FlyteFile | None = None
    genes: FlyteFile | None = None
    predict_out: FlyteDirectory | None = None

    def get_prot_fname(self):
        return f"{self.sample}.fasta"

    def get_genes_fname(self):
        return f"{self.sample}.gff"

    @classmethod
    def make_all(
        cls,
        dir: Path,
        include: list[str] = ["*.fasta", "*.gff", "*.m8", "*.a3m", "*.pdb", "*.png"],
        exclude: list[str] = [],
    ) -> list:
        samples = {}
        for fp in filter_dir(dir, include=include, exclude=exclude):
            sample = "_".join(fp.stem.split("_")[:4])

            if sample not in samples:
                samples[sample] = cls(sample=sample)

            if fp.suffix == ".fasta":
                samples[sample].sequence = FlyteFile(path=str(fp))
            elif fp.suffix == ".m8":
                samples[sample].hitfile = FlyteFile(path=str(fp))
            elif fp.suffix == ".a3m":
                samples[sample].msa = FlyteFile(path=str(fp))
            elif fp.suffix == ".gff":
                samples[sample].genes = FlyteFile(path=str(fp))

        logger.info(f"Created following Protein objects from {dir}: {samples}")
        return list(samples.values())
