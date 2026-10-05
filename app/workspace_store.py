"""
### Workspace store — users' notebooks on object storage.

The durable home of every user's Workspace notebooks and own Snapshots. Each
notebook is one object, keyed by the user's Union subject:

    <WORKSPACE_ROOT>/users/<subject>/notebooks/<filename>
    <WORKSPACE_ROOT>/users/<subject>/snapshots/<filename>

Notebooks stay individually addressable so the dashboard can list a user's
notebooks and read one header without fetching the rest. Per-notebook pods
hydrate their `/workspace` from `workspace_uri()` at launch and write each
notebook back to its own key, so two running notebooks can never clobber each
other.

Reads and writes go through `flyte.storage`, listing and deletes through the
fsspec filesystem it resolves for the root (obstore on `s3://`, the local
filesystem for a plain path). The same calls work on the tenant and in tests.

The function names mirror the GitHub-fork helpers this module replaced, with
the fork and token arguments collapsed into the user's subject.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import asyncio
import re

import flyte.storage

from app import config

# Union subjects are opaque ids (numeric today). Anything that could form a
# path segment other than a single plain name is refused.
_SUBJECT_RE = re.compile(r"^[A-Za-z0-9_-]+$")
# A notebook filename: one plain segment ending in `.py`. `_`-prefixed files
# are reserved (they never list), and a leading dot is never a notebook.
_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.py$")


class NotebookExistsError(Exception):
    """Raised when creating a notebook whose key is already taken."""


def _subject_prefix(subject: str) -> str:
    """Return `<root>/users/<subject>`, refusing a subject that isn't one plain segment."""
    if not _SUBJECT_RE.match(subject or ""):
        raise ValueError(f"invalid user subject: {subject!r}")
    return f"{config.WORKSPACE_ROOT.rstrip('/')}/users/{subject}"


def workspace_uri(subject: str) -> str:
    """URI of the user's Workspace notebooks prefix (what a pod hydrates from)."""
    return f"{_subject_prefix(subject)}/notebooks"


def snapshots_uri(subject: str) -> str:
    """URI of the user's own Snapshots prefix."""
    return f"{_subject_prefix(subject)}/snapshots"


def _key(prefix: str, filename: str) -> str:
    """Join a validated notebook filename onto a prefix."""
    if ".." in filename or not _FILENAME_RE.match(filename or ""):
        raise ValueError(f"invalid notebook filename: {filename!r}")
    return f"{prefix}/{filename}"


def _fs(uri: str):
    """The fsspec filesystem `flyte.storage` resolves for `uri`."""
    return flyte.storage.get_underlying_filesystem(path=uri)


def _list_sync(prefix: str) -> list[str]:
    """Notebook filenames directly under `prefix`, sorted; empty if absent."""
    fs = _fs(prefix)
    try:
        entries = fs.ls(prefix, detail=False)
    except FileNotFoundError:
        return []
    names = (str(e).rstrip("/").rsplit("/", 1)[-1] for e in entries)
    return sorted(n for n in names if _FILENAME_RE.match(n) and not n.startswith("_"))


async def _list(prefix: str) -> list[str]:
    """Async wrapper over the blocking listing."""
    return await asyncio.to_thread(_list_sync, prefix)


async def _get(uri: str) -> str | None:
    """Read one notebook's UTF-8 source, or None if it doesn't exist."""
    if not await flyte.storage.exists(uri):
        return None
    chunks = [chunk async for chunk in flyte.storage.get_stream(uri)]
    return b"".join(chunks).decode("utf-8")


async def _put(uri: str, content: str) -> None:
    """Write one notebook's source as a single object (atomic per PUT)."""
    # Object stores have no directories; a local root does, and won't create
    # the parent on write. A no-op on S3.
    parent = uri.rsplit("/", 1)[0]
    await asyncio.to_thread(_fs(parent).makedirs, parent, exist_ok=True)
    await flyte.storage.put_stream(content.encode("utf-8"), to_path=uri)


async def _create(uri: str, content: str) -> None:
    """Write a new notebook, refusing to replace an existing one."""
    if await flyte.storage.exists(uri):
        raise NotebookExistsError(uri)
    await _put(uri, content)


def _delete_sync(uri: str) -> None:
    """Remove one object; a missing object is already deleted."""
    try:
        _fs(uri).rm(uri)
    except FileNotFoundError:
        pass


async def _delete(uri: str) -> None:
    """Idempotent delete of one notebook."""
    await asyncio.to_thread(_delete_sync, uri)


async def list_workspace(subject: str) -> list[str]:
    """List the user's Workspace notebook filenames, sorted."""
    return await _list(workspace_uri(subject))


async def list_snapshots(subject: str) -> list[str]:
    """List the user's own Snapshot filenames, sorted."""
    return await _list(snapshots_uri(subject))


async def get_workspace_notebook(subject: str, filename: str) -> str | None:
    """Read a Workspace notebook's source, or None if absent."""
    return await _get(_key(workspace_uri(subject), filename))


async def get_snapshot_notebook(subject: str, filename: str) -> str | None:
    """Read an own Snapshot's source, or None if absent."""
    return await _get(_key(snapshots_uri(subject), filename))


async def create_workspace_notebook(subject: str, filename: str, content: str) -> None:
    """Create a Workspace notebook. Raises `NotebookExistsError` if taken."""
    await _create(_key(workspace_uri(subject), filename), content)


async def create_snapshot_notebook(subject: str, filename: str, content: str) -> None:
    """Create an own Snapshot. Raises `NotebookExistsError` if taken."""
    await _create(_key(snapshots_uri(subject), filename), content)


async def update_workspace_notebook(subject: str, filename: str, content: str) -> None:
    """Overwrite a Workspace notebook's source."""
    await _put(_key(workspace_uri(subject), filename), content)


async def delete_workspace_notebook(subject: str, filename: str) -> None:
    """Delete a Workspace notebook. Idempotent."""
    await _delete(_key(workspace_uri(subject), filename))


async def delete_snapshot_notebook(subject: str, filename: str) -> None:
    """Delete an own Snapshot. Idempotent."""
    await _delete(_key(snapshots_uri(subject), filename))
