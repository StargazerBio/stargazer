from dataclasses import dataclass
from flyte.io import Dir, File

@dataclass
class Reference:
    """
    Represents a reference FASTA and associated index files.

    This class captures a directory containing a reference FASTA and optionally it's associated
    index files.

    Attributes:
        ref_name (str): Name or identifier of the raw sequencing sample.
        index_name (str): Index string to pass to tools requiring it. Some tools require just the
        ref name and assume index files are in the same dir, others require the index name.
        ref_dir (Dir): Directory containing the reference and any index files.
    """

    ref: File
    index: File
    ref_dir: Dir