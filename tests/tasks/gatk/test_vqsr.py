"""
Tests for variant_recalibrator and apply_vqsr, each in its own pod.
"""

import shutil
from collections import Counter

import pytest
from conftest import GATK_FIXTURES_DIR, GENERAL_FIXTURES_DIR

import stargazer.utils.storage as _storage
from stargazer.assets import KnownSites, Reference, Variants
from stargazer.tasks.gatk.apply_vqsr import apply_vqsr
from stargazer.tasks.gatk.variant_recalibrator import variant_recalibrator
from stargazer.utils.storage import StorageClient


@pytest.mark.asyncio
async def test_apply_vqsr_uses_a_model_built_in_another_pod(
    isolated_storage, tmp_path, monkeypatch
):
    """apply_vqsr filters with a model whose pod, and its local files, are gone."""
    vcf = Variants(
        path=GATK_FIXTURES_DIR / "NA12829_TP53.vcf",
        sample_id="NA12829",
        variant_type="vcf",
        build="GRCh38",
    )
    ref = Reference(path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")
    mills = KnownSites(
        path=GATK_FIXTURES_DIR / "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf",
        build="GRCh38",
        resource_name="mills",
        training="true",
        truth="true",
        prior="12",
        vqsr_mode="INDEL",
    )

    model = await variant_recalibrator(
        vcf=vcf, ref=ref, resources=[mills], mode="INDEL"
    )

    # The second pod shares only the store and the index with the first.
    shutil.rmtree(isolated_storage.local_dir)
    monkeypatch.setattr(
        _storage,
        "default_client",
        StorageClient(
            local_dir=tmp_path / "second_pod",
            store_root=isolated_storage.store_root,
            index=isolated_storage.index,
        ),
    )

    filtered = await apply_vqsr(vcf=vcf, ref=ref, vqsr_model=model)

    lines = (await filtered.fetch()).read_text().splitlines()
    filters = Counter(line.split("\t")[6] for line in lines if line[0] != "#")
    assert filters == {".": 25, "PASS": 7, "VQSRTrancheINDEL90.00to100.00": 14}
