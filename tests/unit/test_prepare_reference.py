"""Tests for `prepare_reference` skipping indices the reference already has."""

import pytest
from conftest import GENERAL_FIXTURES_DIR

import stargazer.workflows.gatk_data_preprocessing as wf
from stargazer.assets import AlignerIndex, Reference, ReferenceIndex, SequenceDict
from stargazer.tasks.general.bwa_mem2 import BWA_MEM2_INDEX_EXTENSIONS


@pytest.fixture
def ran(monkeypatch):
    """The names of the index tasks `prepare_reference` called, in order."""
    calls = []
    for name in ("samtools_faidx", "create_sequence_dictionary", "bwa_mem2_index"):

        async def record(ref, _name=name):
            """Record the call in place of running the tool."""
            calls.append(_name)

        monkeypatch.setattr(wf, name, record)
    return calls


async def store_reference():
    """Store the fixture reference and return it."""
    ref = Reference()
    await ref.update(GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")
    return ref


async def store_fai(ref):
    """Store the fixture `.fai` as a companion of `ref`."""
    await ReferenceIndex().update(
        GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa.fai",
        build="GRCh38",
        tool="samtools_faidx",
        companion_of=ref.cid,
    )


async def store_dict(ref):
    """Store the fixture `.dict` as a companion of `ref`."""
    await SequenceDict().update(
        GENERAL_FIXTURES_DIR / "GRCh38_TP53.dict",
        build="GRCh38",
        tool="gatk_CreateSequenceDictionary",
        companion_of=ref.cid,
    )


async def store_bwa_index(ref, tmp_path, extensions, aligner="bwa-mem2"):
    """Store one index file per extension, each named after the reference."""
    for ext in extensions:
        path = tmp_path / f"GRCh38_TP53.fa{ext}"
        path.write_bytes(ext.encode())
        await AlignerIndex().update(
            path,
            aligner=aligner,
            build="GRCh38",
            companion_of=ref.cid,
        )


async def test_no_companions_runs_every_index_task(ran):
    """A bare reference gets all three indices built."""
    ref = await store_reference()

    result = await wf.prepare_reference(build="GRCh38")

    assert ran == ["samtools_faidx", "create_sequence_dictionary", "bwa_mem2_index"]
    assert result.cid == ref.cid


async def test_all_companions_runs_no_index_task(ran, tmp_path):
    """A reference with every companion skips all three tasks."""
    ref = await store_reference()
    await store_fai(ref)
    await store_dict(ref)
    await store_bwa_index(ref, tmp_path, BWA_MEM2_INDEX_EXTENSIONS)

    result = await wf.prepare_reference(build="GRCh38")

    assert ran == []
    assert result.cid == ref.cid


async def test_only_fai_skips_faidx(ran):
    """A stored `.fai` skips only the FASTA index."""
    ref = await store_reference()
    await store_fai(ref)

    await wf.prepare_reference(build="GRCh38")

    assert ran == ["create_sequence_dictionary", "bwa_mem2_index"]


async def test_four_of_five_bwa_files_rebuilds_the_index(ran, tmp_path):
    """A bwa-mem2 index missing one file is built again."""
    ref = await store_reference()
    await store_fai(ref)
    await store_dict(ref)
    await store_bwa_index(
        ref,
        tmp_path,
        (".0123", ".amb", ".ann", ".bwt.2bit.64"),
    )

    await wf.prepare_reference(build="GRCh38")

    assert ran == ["bwa_mem2_index"]


async def test_bwa_index_is_not_bwa_mem2(ran, tmp_path):
    """An index made by `bwa` doesn't satisfy bwa-mem2."""
    ref = await store_reference()
    await store_fai(ref)
    await store_dict(ref)
    await store_bwa_index(
        ref,
        tmp_path,
        (".amb", ".ann", ".bwt", ".pac", ".sa"),
        aligner="bwa",
    )

    await wf.prepare_reference(build="GRCh38")

    assert ran == ["bwa_mem2_index"]
