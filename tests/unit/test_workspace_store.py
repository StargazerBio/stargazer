"""Tests for `app.workspace_store`, the object-store home of user workspaces.

Runs the real `flyte.storage` calls against a local directory root, so the
same code path that talks to S3 on the tenant is exercised here — no mocks.
"""

from pathlib import Path

import pytest

from app import config
from app import workspace_store as ws

ALICE = "387300641116005877"
BOB = "111111111111111111"
NB = "# /// script\n# ///\nimport marimo\n"


@pytest.fixture(autouse=True)
def _root(tmp_path, monkeypatch):
    """Point the store at a fresh local directory for every test."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", str(tmp_path / "store"))


async def test_round_trip_is_byte_identical():
    """A created notebook reads back exactly as written."""
    await ws.create_workspace_notebook(ALICE, "qc.py", NB)
    assert await ws.get_workspace_notebook(ALICE, "qc.py") == NB


async def test_missing_notebook_reads_none():
    """Reading a notebook that was never written returns None."""
    assert await ws.get_workspace_notebook(ALICE, "nope.py") is None


async def test_list_is_scoped_to_the_user():
    """Each user lists only their own notebooks, sorted."""
    await ws.create_workspace_notebook(ALICE, "b.py", NB)
    await ws.create_workspace_notebook(ALICE, "a.py", NB)
    await ws.create_workspace_notebook(BOB, "bobs.py", NB)
    assert await ws.list_workspace(ALICE) == ["a.py", "b.py"]
    assert await ws.list_workspace(BOB) == ["bobs.py"]


async def test_list_of_new_user_is_empty():
    """A user with nothing stored lists an empty workspace."""
    assert await ws.list_workspace(ALICE) == []


async def test_nested_files_are_not_notebooks():
    """Files in folders, a `.py` among them, never list as notebooks."""
    await ws.create_workspace_notebook(ALICE, "live.py", NB)
    root = Path(ws.workspace_uri(ALICE))
    for rel in ("lib/helpers.py", "data/counts.csv"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x\n")
    assert await ws.list_workspace(ALICE) == ["live.py"]


async def test_create_refuses_to_overwrite():
    """Creating over an existing notebook raises and keeps the original."""
    await ws.create_workspace_notebook(ALICE, "qc.py", NB)
    with pytest.raises(ws.NotebookExistsError):
        await ws.create_workspace_notebook(ALICE, "qc.py", "changed\n")
    assert await ws.get_workspace_notebook(ALICE, "qc.py") == NB


async def test_update_overwrites():
    """Update replaces an existing notebook's source."""
    await ws.create_workspace_notebook(ALICE, "qc.py", NB)
    await ws.update_workspace_notebook(ALICE, "qc.py", "changed\n")
    assert await ws.get_workspace_notebook(ALICE, "qc.py") == "changed\n"


async def test_delete_is_idempotent():
    """Deleting removes the notebook, and deleting again still succeeds."""
    await ws.create_workspace_notebook(ALICE, "qc.py", NB)
    await ws.delete_workspace_notebook(ALICE, "qc.py")
    await ws.delete_workspace_notebook(ALICE, "qc.py")
    assert await ws.list_workspace(ALICE) == []


@pytest.mark.parametrize(
    "bad", ["../x.py", "a/b.py", "", ".py", "x.txt", "_private.py"]
)
async def test_bad_filename_is_rejected(bad):
    """Filenames that could escape the prefix or aren't notebooks are refused."""
    with pytest.raises(ValueError):
        await ws.get_workspace_notebook(ALICE, bad)


@pytest.mark.parametrize("bad", ["", "..", "a/b", "../387300641116005877"])
async def test_bad_subject_is_rejected(bad):
    """A subject that could escape the users prefix is refused."""
    with pytest.raises(ValueError):
        await ws.list_workspace(bad)


def test_workspace_uri_layout():
    """The workspace prefix sits under users/<subject>/workspace."""
    assert ws.workspace_uri(ALICE) == f"{config.WORKSPACE_ROOT}/users/{ALICE}/workspace"
