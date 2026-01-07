import gzip
import ftplib
import requests
from pathlib import Path
from typing import List
from flytekit.remote import FlyteRemote
from flytekit.configuration import Config
from unionbio.config import logger


def cache_hash(input: str | List[str]) -> str:
    """
    Generate a hash from a URI to use as a cache key.

    Args:
        url (str | List[str]): The URI or list of URIs to hash.

    Returns:
        str: The first 6 characters of the hash of the URI(s).
    """
    if isinstance(input, list):
        input = "".join(input)
    return str(hash(input))[:6]


def gunzip_file(gzip_file: Path) -> Path:
    # Ensure the input file exists
    if not gzip_file.exists():
        raise FileNotFoundError(f"{gzip_file} not found")

    # Ensure the file has a .gz extension
    if not gzip_file.suffix == ".gz":
        raise ValueError("Input file is not a gzip file")

    # Define the output file path
    output_file = gzip_file.with_suffix("")

    # Open input and output files
    with gzip.open(gzip_file, "rb") as f_in, open(output_file, "wb") as f_out:
        # Decompress and write to output file
        f_out.write(f_in.read())

    return output_file


def get_remote(local=None, config_file=None):
    """
    Get remote configuration settings and return a remote object.

    This function retrieves remote configuration settings, including the local flag and
    a configuration file, and uses them to create and return a remote object.

    Args:
        local (bool, optional): A flag indicating whether to use local settings. If True,
            the function will use local settings; if False, it will use remote settings.
            Defaults to None, which implies the use of default settings.
        config_file (str, optional): The path to a custom configuration file. If provided,
            this file will be used for configuration settings. Defaults to None.

    Returns:
        Remote: A remote object configured with the specified settings.
    """
    return FlyteRemote(
        config=Config.auto(
            config_file=(
                None
                if local
                else config_file
                if config_file is not None
                else str(Path.home() / ".flyte" / "config-sandbox.yaml")
            )
        ),
        default_project="flytesnacks",
        default_domain="development",
    )


def fetch_file(url: str, local_dir: str) -> Path:
    """
    Downloads a file from the specified URL.

    Args:
        url (str): The URL of the file to download.
        local_dir (Path): The directory where you would like this file saved.

    Returns:
        Path: The local path to the file.

    Raises:
        requests.HTTPError: If an HTTP error occurs while downloading the file.
    """
    url_parts = url.split("/")
    host = url_parts[2]
    prot = url_parts[0]
    fname = url_parts[-1]
    remote_dir = "/".join(url_parts[3:-1])
    local_path = Path(local_dir).joinpath(fname)
    logger.debug(f"File will be written to {local_path}")

    if prot == "ftp:":  # FTP
        logger.debug("Fetching FTP file..")
        ftp = ftplib.FTP(host)
        ftp.login()
        ftp.cwd(remote_dir)
        with open(local_path, "wb") as file:
            ftp.retrbinary(f"RETR {fname}", file.write)
        ftp.quit()
    elif prot == "http:" or prot == "https:":  # HTTP
        logger.debug("Fetching HTTP file..")
        try:
            headers = {"User-Agent": "My User Agent 1.0"}
            response = requests.get(url, headers=headers)
            logger.debug(response)
            with open(local_path, "wb") as file:
                file.write(response.content)
        except requests.HTTPError as e:
            print(f"HTTP error: {e}")
            raise e
    return local_path


def filter_dir(dir: Path, include: list[str] = ["*"], exclude: list[str] = []):
    """
    Filter the contents of a directory based on include and exclude patterns.

    Args:
        dir (Path): The directory whose contents you would like to filter.
        include (list[str], optional): A list of wildcarded patterns to include
            by passing to rglob. Defaults to ["*"].
        exclude (list[str], optional): A list of patterns to exclude. Defaults to [].

    Returns:
        list[Path]: A list of paths to the filtered contents of the directory.
    """
    logger.debug(f"Filtering {dir} with include={include} and exclude={exclude}")
    included = [f for pattern in include for f in dir.rglob(pattern)]
    logger.debug(f"Included: {included}")
    for f in included:
        if not any([f.match(p) for p in exclude]):
            logger.debug(f"Matched {f}")
            yield f
        else:
            logger.debug(f"Excluded {f}")
