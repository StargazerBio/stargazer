"""Tests for the MCP server's tools: `run_task`'s asset parameters taken by
CID, and the refusals every tool passes on to the client.

`_execute` (the `flyte.run` call) is swapped for one that returns the keyword
arguments it would run the task with, so these check what reaches the task
without the tools it runs. A refusal is a `ToolError`, the one exception whose
message the MCP server passes on to the client.
"""

import aiohttp
import pytest
from conftest import GATK_FIXTURES_DIR, GENERAL_FIXTURES_DIR
from mcp.server.mcpserver.exceptions import ToolError

import stargazer.utils.storage as _storage
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
    with pytest.raises(ToolError, match=r"known_sites: expected a list of CIDs"):
        await server.run_task(
            "base_recalibrator",
            {"alignment": alignment.cid, "ref": ref.cid, "known_sites": mills.cid},
        )


async def test_run_task_refuses_a_cid_not_in_the_index(ref):
    """An unknown CID is refused, naming the parameter and the CID."""
    with pytest.raises(ToolError, match=r"r1: no asset with CID 'bafkreinotthere'"):
        await server.run_task("bwa_mem2_mem", {"ref": ref.cid, "r1": "bafkreinotthere"})


async def test_run_task_refuses_a_cid_of_the_wrong_type(ref, r1):
    """An R1's CID given for `ref` is refused, naming both types."""
    with pytest.raises(
        ToolError, match=r"ref takes a Reference, but CID .* is of type R1"
    ):
        await server.run_task("bwa_mem2_mem", {"ref": r1.cid, "r1": r1.cid})


async def test_run_task_refuses_a_missing_required_parameter(ref):
    """A required parameter left out is refused by name."""
    with pytest.raises(ToolError, match=r"'r1'"):
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
    with pytest.raises(ToolError, match=r"no parameter 'reference'"):
        await server.run_task("samtools_faidx", {"reference": ref.cid})


async def test_run_workflow_refuses_an_unknown_workflow_by_name():
    """An unknown workflow is a ToolError naming it."""
    with pytest.raises(ToolError, match=r"Unknown workflow: 'nope'"):
        await server.run_workflow("nope", {})


UNKNOWN_CID = "bafkreiaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
FASTA = str(GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa")


class TestRefusalsReachTheClient:
    """A bad call to a storage or bundle tool is a ToolError carrying its reason."""

    async def test_upload_without_an_asset_key(self):
        """keyvalues with no `asset` key are refused, naming the registered keys."""
        with pytest.raises(ToolError, match=r"must include 'asset'.*'reference'"):
            await server.upload_file(FASTA, {"build": "GRCh38_TP53"})

    async def test_upload_with_a_field_that_does_not_parse(self):
        """A typed field whose value isn't JSON is refused, naming the field."""
        with pytest.raises(ToolError, match=r"duplicates_marked takes JSON \(bool\)"):
            await server.upload_file(
                FASTA, {"asset": "alignment", "duplicates_marked": "maybe"}
            )

    async def test_upload_of_a_missing_file(self):
        """A path with no file behind it is refused, naming the path."""
        with pytest.raises(ToolError, match=r"No such file.*nope\.fa"):
            await server.upload_file(
                str(GENERAL_FIXTURES_DIR / "nope.fa"),
                {"asset": "reference", "build": "x"},
            )

    async def test_update_of_a_cid_not_in_the_index(self):
        """Updating a CID the index doesn't hold is refused, naming the CID."""
        with pytest.raises(ToolError, match=rf"No index row for cid {UNKNOWN_CID}"):
            await server.update_file(UNKNOWN_CID, {"asset": "reference", "build": "x"})

    async def test_update_without_an_asset_key(self):
        """An update patch is validated like an upload."""
        with pytest.raises(ToolError, match=r"must include 'asset'"):
            await server.update_file(UNKNOWN_CID, {"build": "x"})

    async def test_publish_without_a_public_tier(self):
        """Publishing with no public tier configured is refused, saying so."""
        with pytest.raises(ToolError, match=r"no public tier to publish to"):
            await server.publish_file(UNKNOWN_CID)

    async def test_fetch_of_an_unknown_bundle(self):
        """An unknown bundle name is refused, naming the available ones."""
        with pytest.raises(ToolError, match=r"Bundle 'nope' not found. Available: \["):
            await server.fetch_resource_bundle("nope")

    async def test_download_the_gateway_refuses(self, monkeypatch):
        """A CID in neither the index nor the gateway is refused, naming the CID."""

        async def _refuse(url, dest):
            raise aiohttp.ClientResponseError(None, (), status=403, message="Forbidden")

        monkeypatch.setattr(_storage, "_fetch_http", _refuse)
        with pytest.raises(
            ToolError, match=rf"{UNKNOWN_CID} isn't in your storage.*403"
        ):
            await server.download_file(UNKNOWN_CID)
