"""Tests for the MCP server's `run_task`: asset parameters taken by CID.

`_execute` (the `flyte.run` call) is swapped for one that returns the keyword
arguments it would run the task with, so these check what reaches the task
without the tools it runs.
"""

import pytest
from conftest import GATK_FIXTURES_DIR, GENERAL_FIXTURES_DIR

from stargazer import server
from stargazer.assets import R1, Alignment, KnownSites, Reference


@pytest.fixture(autouse=True)
def captured_kwargs(monkeypatch):
    """Make `run_task` return the kwargs it would run its task with."""

    async def _capture(info, kwargs):
        return kwargs

    monkeypatch.setattr(server, "_execute", _capture)


@pytest.fixture
async def ref():
    """A stored reference."""
    return await Reference.store(
        GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38_TP53"
    )


@pytest.fixture
async def r1():
    """A stored R1 for sample NA12829."""
    return await R1.store(
        GENERAL_FIXTURES_DIR / "NA12829_TP53_R1.fq.gz", sample_id="NA12829"
    )


async def test_run_task_fills_assets_with_different_keys_by_cid(ref, r1):
    """A reference and a sample's reads, which share no keyvalue, both fill."""
    kwargs = await server.run_task(
        "bwa_mem2_mem", {"ref": ref.cid, "r1": r1.cid, "read_group": {"ID": "rg1"}}
    )

    assert set(kwargs) == {"ref", "r1", "read_group"}
    assert type(kwargs["ref"]) is Reference
    assert (kwargs["ref"].cid, kwargs["ref"].build) == (ref.cid, "GRCh38_TP53")
    assert type(kwargs["r1"]) is R1
    assert (kwargs["r1"].cid, kwargs["r1"].sample_id) == (r1.cid, "NA12829")
    assert kwargs["r1"].path.name == "NA12829_TP53_R1.fq.gz"
    assert kwargs["read_group"] == {"ID": "rg1"}


async def test_run_task_fills_a_list_parameter_from_a_list_of_cids(ref):
    """A `list[Asset]` parameter takes a list of CIDs, in order."""
    alignment = await Alignment.store(
        GATK_FIXTURES_DIR / "NA12829_TP53_markdup.bam", sample_id="NA12829"
    )
    mills = await KnownSites.store(
        GATK_FIXTURES_DIR / "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf",
        build="GRCh38_TP53",
    )
    calls = await KnownSites.store(
        GATK_FIXTURES_DIR / "NA12829_TP53.vcf", build="GRCh38_TP53"
    )

    kwargs = await server.run_task(
        "base_recalibrator",
        {
            "alignment": alignment.cid,
            "ref": ref.cid,
            "known_sites": [calls.cid, mills.cid],
        },
    )

    assert [type(k) for k in kwargs["known_sites"]] == [KnownSites, KnownSites]
    assert [k.cid for k in kwargs["known_sites"]] == [calls.cid, mills.cid]
    assert type(kwargs["alignment"]) is Alignment


async def test_run_task_refuses_a_single_cid_for_a_list_parameter(ref):
    """A list parameter given one CID, not a list, is refused by name."""
    mills = await KnownSites.store(
        GATK_FIXTURES_DIR / "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf",
        build="GRCh38_TP53",
    )
    alignment = await Alignment.store(
        GATK_FIXTURES_DIR / "NA12829_TP53_markdup.bam", sample_id="NA12829"
    )
    with pytest.raises(TypeError, match=r"known_sites: expected a list of CIDs"):
        await server.run_task(
            "base_recalibrator",
            {"alignment": alignment.cid, "ref": ref.cid, "known_sites": mills.cid},
        )


async def test_run_task_refuses_a_cid_not_in_the_index(ref):
    """An unknown CID is refused, naming the parameter and the CID."""
    with pytest.raises(ValueError, match=r"r1: no asset with CID 'bafkreinotthere'"):
        await server.run_task("bwa_mem2_mem", {"ref": ref.cid, "r1": "bafkreinotthere"})


async def test_run_task_refuses_a_cid_of_the_wrong_type(ref, r1):
    """An R1's CID given for `ref` is refused, naming both types."""
    with pytest.raises(
        TypeError, match=r"ref takes a Reference, but CID .* is of type R1"
    ):
        await server.run_task("bwa_mem2_mem", {"ref": r1.cid, "r1": r1.cid})


async def test_run_task_refuses_a_missing_required_parameter(ref):
    """A required parameter left out is refused by name."""
    with pytest.raises(ValueError, match=r"'r1'"):
        await server.run_task("bwa_mem2_mem", {"ref": ref.cid})


async def test_run_task_passes_scalars_through():
    """A non-asset input reaches the task as given."""
    alignment = await Alignment.store(
        GATK_FIXTURES_DIR / "NA12829_TP53_markdup.bam", sample_id="NA12829"
    )

    kwargs = await server.run_task(
        "sort_sam", {"alignment": alignment.cid, "sort_order": "queryname"}
    )

    assert kwargs["sort_order"] == "queryname"
    assert kwargs["alignment"].cid == alignment.cid


async def test_run_task_refuses_an_unknown_input(ref):
    """An input the task has no parameter for is refused by name."""
    with pytest.raises(ValueError, match=r"no parameter 'reference'"):
        await server.run_task("samtools_faidx", {"reference": ref.cid})
