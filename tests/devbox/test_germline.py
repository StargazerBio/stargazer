"""The germline workflow on the devbox.

A reference and one sample's paired reads are seeded from a pod, then
`germline_short_variant_discovery` runs the way SDK code submits it, every
step in its own pod, through to joint calling. The cohort's VCF is found and
read back from another pod.
"""

import json
import uuid

import pytest
from conftest import GENERAL_FIXTURES_DIR
from flyte.io import File

from stargazer.assets import Variants
from stargazer.workflows import germline_short_variant_discovery

from . import pod_tasks


@pytest.fixture(scope="module")
def cohort(devbox_run) -> tuple[str, Variants]:
    """Seed the inputs, run the workflow for a fresh cohort; return its ID and VCF."""
    reference, r1, r2 = [
        File.from_local_sync(str(GENERAL_FIXTURES_DIR / name))
        for name in (pod_tasks.REFERENCE, *pod_tasks.READS)
    ]
    devbox_run(pod_tasks.seed, reference=reference, r1=r1, r2=r2)
    cohort_id = f"cohort-{uuid.uuid4().hex[:8]}"
    run = devbox_run(
        germline_short_variant_discovery,
        build=pod_tasks.BUILD,
        sample_ids=[pod_tasks.SAMPLE_ID],
        cohort_id=cohort_id,
    )
    return cohort_id, run.outputs()[0]


def test_workflow_joint_calls_the_cohort(cohort):
    """The workflow returns the cohort's joint-called VCF."""
    cohort_id, vcf = cohort
    assert (vcf.caller, vcf.sample_id, vcf.source_samples, vcf.build) == (
        "joint_call_gvcfs",
        cohort_id,
        [pod_tasks.SAMPLE_ID],
        pod_tasks.BUILD,
    )


def test_cohort_vcf_found_from_another_pod(cohort, devbox_run):
    """Another pod finds the VCF by cohort, and it calls variants for the sample."""
    cohort_id, _ = cohort
    got = json.loads(devbox_run(pod_tasks.check, cohort_id=cohort_id).outputs()[0])
    assert got["samples"] == [pod_tasks.SAMPLE_ID]
    assert got["contigs"] == ["chr17:7658421-7697490"]
    assert got["records"] > 0


def test_cohort_vcf_walks_back_to_its_reference(cohort, index_query):
    """From the cohort's VCF, CID links alone lead to the reference it was called against."""
    _, vcf = cohort

    # One query: each call opens its own port-forward.
    by_cid = {
        row["cid"]: row
        for row in index_query({"asset": ["variants", "alignment", "r1", "reference"]})
    }
    (gvcf_cid,) = vcf.source_cids
    (alignment_cid,) = json.loads(by_cid[gvcf_cid]["keyvalues"]["source_cids"])

    tools = []
    reference_cids = set()
    kv = by_cid[alignment_cid]["keyvalues"]
    while kv["asset"] == "alignment":
        tools.append(kv["tool"])
        reference_cids.add(kv["reference_cid"])
        kv = by_cid[kv["source_cid"]]["keyvalues"]

    assert tools == ["gatk_mark_duplicates", "gatk_sort_sam", ""]
    assert kv["asset"] == "r1"
    assert len(reference_cids) == 1
    (reference_cid,) = reference_cids
    assert reference_cid
    assert by_cid[reference_cid]["keyvalues"]["asset"] == "reference"
    assert by_cid[reference_cid]["keyvalues"]["build"] == pod_tasks.BUILD
