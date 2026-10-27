"""
### Fetching a notebook file from GitHub for the dashboard's Open from GitHub.

`fetch_notebook` takes a link to one `.py` file on GitHub, either the page
(`github.com/<owner>/<repo>/blob/<ref>/<path>.py`) or the raw file
(`raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>.py`), and downloads
it from `raw.githubusercontent.com`. Only that host is ever fetched, so the
dashboard can't be pointed at an arbitrary URL, and the download stops at
`MAX_BYTES`. Each failure is a `GitHubFileError` whose message is for the
dashboard user and whose `status` is the response code.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

from pathlib import PurePosixPath
from urllib.parse import urlsplit

import httpx

RAW_HOST = "raw.githubusercontent.com"
MAX_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 20

# Tests swap in an `httpx.MockTransport`; None is httpx's real network.
TRANSPORT: httpx.AsyncBaseTransport | None = None

BAD_LINK = (
    "Paste a link to a .py file on GitHub, like "
    "https://github.com/<owner>/<repo>/blob/<commit>/<path>.py"
)


class GitHubFileError(Exception):
    """A GitHub file that can't be opened; the message is for the dashboard."""

    def __init__(self, message: str, status: int):
        """Carry the user-facing `message` and the HTTP `status` to answer with."""
        super().__init__(message)
        self.status = status


def raw_url(link: str) -> str:
    """The `raw.githubusercontent.com` URL of a GitHub `.py` file link.

    A page link's `blob/` segment is dropped; a raw link is kept as is. The
    query and fragment (`?plain=1`, `#L10`) are ignored. Raises
    `GitHubFileError` (400) for anything else.
    """
    parts = urlsplit(link.strip())
    segments = [s for s in parts.path.split("/") if s]
    if parts.scheme in ("http", "https") and segments and segments[-1].endswith(".py"):
        if (
            parts.netloc == "github.com"
            and len(segments) >= 5
            and segments[2] == "blob"
        ):
            return f"https://{RAW_HOST}/" + "/".join(segments[:2] + segments[3:])
        if parts.netloc == RAW_HOST and len(segments) >= 4:
            return f"https://{RAW_HOST}/" + "/".join(segments)
    raise GitHubFileError(BAD_LINK, 400)


async def fetch_notebook(link: str) -> tuple[str, str]:
    """Download the file a GitHub link names, as `(file_stem, source)`.

    Raises `GitHubFileError`: 400 for a link that isn't a GitHub `.py` file or
    a file that isn't text, 404 when GitHub doesn't have it, 413 when it's
    over `MAX_BYTES`, and 500 when GitHub can't be reached.
    """
    url = raw_url(link)
    body = bytearray()
    try:
        async with (
            httpx.AsyncClient(transport=TRANSPORT, timeout=TIMEOUT_SECONDS) as client,
            client.stream("GET", url) as resp,
        ):
            if resp.status_code == 404:
                raise GitHubFileError(
                    "That file wasn't found on GitHub. Check the link, and "
                    "that its repository is public.",
                    404,
                )
            if resp.status_code != 200:
                raise GitHubFileError(
                    f"GitHub answered {resp.status_code} for that file.", 500
                )
            async for chunk in resp.aiter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise GitHubFileError(
                        f"That file is too big to open as a notebook; the "
                        f"limit is {MAX_BYTES // 1024 // 1024} MB.",
                        413,
                    )
    except httpx.HTTPError as exc:
        raise GitHubFileError(f"Couldn't reach GitHub: {exc}", 500) from exc
    try:
        source = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GitHubFileError("That file isn't a marimo notebook.", 400) from exc
    return PurePosixPath(urlsplit(url).path).stem, source
