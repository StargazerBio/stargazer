"""The germline workflow on the devbox.

A reference and one sample's paired reads are seeded from a pod, then
`germline_short_variant_discovery` runs the way SDK code submits it, every
step in its own pod, through to joint calling. The cohort's VCF is found and
read back from another pod.
"""

import json
import uuid

import pytest
from flyte.io import File

from stargazer.assets import Variants
from stargazer.config import PROJECT_ROOT
from stargazer.workflows import germline_short_variant_discovery

from . import pod_tasks

pytestmark = pytest.mark.devbox

FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "general"


@pytest.fixture(scope="module")
def cohort(dashboard, devbox_run) -> tuple[str, Variants]:
    """Seed the inputs, run the workflow for a fresh cohort; return its ID and VCF."""
    reference, r1, r2 = [
        File.from_local_sync(str(FIXTURES / name))
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
        ["NA12829"],
        "GRCh38",
    )


def test_cohort_vcf_found_from_another_pod(cohort, devbox_run):
    """Another pod finds the VCF by cohort, and it calls variants for the sample."""
    cohort_id, _ = cohort
    got = json.loads(devbox_run(pod_tasks.check, cohort_id=cohort_id).outputs()[0])
    assert got["samples"] == ["NA12829"]
    assert got["contigs"] == ["chr17:7658421-7697490"]
    assert got["records"] > 0
