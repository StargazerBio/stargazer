import os
import shutil
from mashumaro.mixins.json import DataClassJSONMixin
from dataclasses import dataclass
from flytekit.types.directory import FlyteDirectory
from flytekit import current_context
from pathlib import Path
from unionbio.tasks.helpers import gunzip_file, fetch_file
from unionbio.config import logger


@dataclass
class Reference(DataClassJSONMixin):
    """
    Represents a reference FASTA and associated index files.

    This class captures a directory containing a reference FASTA and optionally it's associated
    index files.

    Attributes:
        ref_name (str): Name or identifier of the raw sequencing sample.
        ref_dir (FlyteDirectory): Directory containing the reference and any index files.
        index_name (str): Index string to pass to tools requiring it. Some tools require just the
        ref name and assume index files are in the same dir, others require the index name.
        indexed_with (str): Name of tool used to create the index.
    """

    ref_name: str
    ref_dir: FlyteDirectory
    index_name: str | None = None
    indexed_with: str | None = None

    def get_ref_dict_fn(self):
        return Path(self.ref_name).with_suffix(".dict")

    def get_ref_path(self, unzip=True):
        fp = Path(self.ref_dir.path).joinpath(self.ref_name)
        if ".gz" in self.ref_name and unzip:
            unzipped = gunzip_file(fp)
            self.ref_name = unzipped.name
            return unzipped
        else:
            return fp

    def aggregate(self, target: Path = None) -> Path:
        """
        Explicitly aggregate the contents of the reference directory into
        another given directory. If None is provided, the current working
        is used.

        Args:
            target (Path): The target directory to move the reference files to.

        Returns:
            Path: The target directory containing the reference files.
        """
        target = target or Path(current_context().working_directory)
        logger.info(f"Aggregating reference files to {target}")
        self.ref_dir.download()
        os.makedirs(target, exist_ok=True)
        for f in os.listdir(self.ref_dir.path):
            fo = Path(self.ref_dir.path).joinpath(f)
            fd = Path(target).joinpath(f)
            shutil.move(fo, fd)
            logger.debug(f"Moved {fo} to {fd}")
        self.ref_dir.path = target
        return target

    @classmethod
    def from_remote(cls, url: str):
        ref = fetch_file(url, "/tmp")
        return cls(ref.name, FlyteDirectory(ref.parent))
