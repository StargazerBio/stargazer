"""Tests for Reference."""

import pytest
from conftest import make_client

import stargazer.utils.storage as _storage_mod
from stargazer.assets.reference import Reference, ReferenceIndex


async def test_contigs_from_the_store(tmp_path, monkeypatch):
    """contigs() reads a stored reference's index, as a pod that didn't make it would."""
    (tmp_path / "ref.fa").write_text(">chr1\nACGT\n>chr2\nAC\n")
    (tmp_path / "ref.fa.fai").write_text("chr1\t4\t6\t4\t5\nchr2\t2\t17\t2\t3\n")
    ref = Reference()
    await ref.update(tmp_path / "ref.fa", build="T")
    await ReferenceIndex().update(
        tmp_path / "ref.fa.fai", build="T", companion_of=ref.cid
    )

    pod = make_client(tmp_path / "storage", cache="pod")
    monkeypatch.setattr(_storage_mod, "default_client", pod)

    assert await Reference(cid=ref.cid).contigs() == ["chr1", "chr2"]


async def test_contigs_without_an_index_names_the_task_that_makes_one(tmp_path):
    (tmp_path / "ref.fa").write_text(">chr1\nACGT\n")
    ref = Reference()
    await ref.update(tmp_path / "ref.fa", build="T")

    with pytest.raises(FileNotFoundError, match="samtools_faidx"):
        await ref.contigs()
