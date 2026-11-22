"""
Unit test suite for Verra VM0042 MRV Carbon Accounting & Merkle Tree Attestation.
"""

import pytest

from backend.core.carbon_mrv import (
    CarbonMRVEngine,
    CreditStatus,
    EvidenceType,
    MRVEvidenceRecord,
)


def test_additionality_assessment_positive():
    """Verify additionality calculation under Verra VM0042 rules."""
    engine = CarbonMRVEngine()
    # Baseline: 28.0 t C/ha, Project: 32.5 t C/ha over 3.0 ha
    assessment = engine.evaluate_additionality(
        baseline_soc_t_c_ha=28.0,
        project_soc_t_c_ha=32.5,
        farm_area_ha=3.0,
    )

    # Delta C = 4.5 t C/ha
    assert assessment.net_additionality_t_c_ha == 4.5
    # 4.5 * 3.667 = 16.5 t CO2e/ha * 3 ha = 49.5 t CO2e
    assert 48.0 <= assessment.total_gross_co2e_tonnes <= 51.0

    # 15% buffer pool deduction
    expected_buffer = assessment.total_gross_co2e_tonnes * 0.15
    assert abs(assessment.buffer_pool_tonnes - expected_buffer) < 0.1

    # 5% uncertainty discount
    expected_uncertainty = assessment.total_gross_co2e_tonnes * 0.05
    assert abs(assessment.uncertainty_discount_tonnes - expected_uncertainty) < 0.1

    # Net VCUs = 80% of gross
    assert assessment.net_mintable_vcu > 38.0
    assert assessment.market_value_usd == round(assessment.net_mintable_vcu * 25.0, 2)
    assert assessment.market_value_vnd > 20000000.0  # > 20M VND


def test_additionality_negative_or_zero():
    """Verify zero additionality when project soil carbon does not exceed baseline."""
    engine = CarbonMRVEngine()
    assessment = engine.evaluate_additionality(
        baseline_soc_t_c_ha=30.0,
        project_soc_t_c_ha=29.0,  # degraded relative to baseline
        farm_area_ha=2.0,
    )

    assert assessment.net_additionality_t_c_ha == 0.0
    assert assessment.total_gross_co2e_tonnes == 0.0
    assert assessment.net_mintable_vcu == 0.0
    assert assessment.market_value_usd == 0.0


def test_merkle_tree_construction_and_determinism():
    """Verify SHA-256 Merkle tree calculation over empirical field evidence."""
    engine = CarbonMRVEngine()

    records = [
        MRVEvidenceRecord(
            record_id="REC-001",
            evidence_type=EvidenceType.SOIL_CORE_LAB,
            plot_id="PLOT-01",
            timestamp_utc="2026-11-20T08:00:00Z",
            measured_metric="soc_combustion_pct",
            value=2.45,
            unit="pct_c",
            laboratory_or_sensor="Eurofins Agroscience",
        ),
        MRVEvidenceRecord(
            record_id="REC-002",
            evidence_type=EvidenceType.UAV_MULTISPECTRAL,
            plot_id="PLOT-01",
            timestamp_utc="2026-11-21T09:30:00Z",
            measured_metric="mean_ndre_canopy",
            value=0.62,
            unit="index",
            laboratory_or_sensor="UAV-Alpha Micasense",
        ),
        MRVEvidenceRecord(
            record_id="REC-003",
            evidence_type=EvidenceType.AMENDMENT_RECEIPT,
            plot_id="PLOT-01",
            timestamp_utc="2026-11-22T07:15:00Z",
            measured_metric="biochar_applied_tonnes",
            value=3.0,
            unit="tonnes",
            laboratory_or_sensor="Dalat Pyrolysis Batch #409",
        ),
        MRVEvidenceRecord(
            record_id="REC-004",
            evidence_type=EvidenceType.IOT_MATRIC_TENSION,
            plot_id="PLOT-01",
            timestamp_utc="2026-11-22T10:00:00Z",
            measured_metric="mean_matric_suction_kpa",
            value=24.5,
            unit="kPa",
            laboratory_or_sensor="Teros-21 Soil Sensor",
        ),
    ]

    root_hash, leaf_hashes = engine.build_merkle_tree(records)

    assert len(root_hash) == 64
    assert len(leaf_hashes) == 4
    # Determinism check: running again must give exact same root
    root_hash_2, _ = engine.build_merkle_tree(records)
    assert root_hash == root_hash_2

    # Tampering test: altering one value alters the root
    records[0].value = 2.46
    root_tampered, _ = engine.build_merkle_tree(records)
    assert root_hash != root_tampered


def test_merkle_tree_empty_and_odd_nodes():
    """Verify Merkle tree handles empty list and odd number of leaves gracefully."""
    engine = CarbonMRVEngine()

    empty_root, empty_leaves = engine.build_merkle_tree([])
    assert len(empty_root) == 64
    assert len(empty_leaves) == 0

    odd_records = [
        MRVEvidenceRecord(
            record_id=f"REC-{i}",
            evidence_type=EvidenceType.SOIL_CORE_LAB,
            plot_id="PLOT-01",
            timestamp_utc="2026-11-20T08:00:00Z",
            measured_metric="soc_pct",
            value=2.0 + i * 0.1,
            unit="pct",
            laboratory_or_sensor="Lab",
        )
        for i in range(3)
    ]
    odd_root, odd_leaves = engine.build_merkle_tree(odd_records)
    assert len(odd_root) == 64
    assert len(odd_leaves) == 3


def test_mint_carbon_certificate_lifecycle():
    """Verify minting and asset properties of Verified Carbon Units."""
    engine = CarbonMRVEngine()
    assessment = engine.evaluate_additionality(
        baseline_soc_t_c_ha=26.0,
        project_soc_t_c_ha=30.0,
        farm_area_ha=2.5,
    )
    records = [
        MRVEvidenceRecord(
            record_id="REC-101",
            evidence_type=EvidenceType.SOIL_CORE_LAB,
            plot_id="PLOT-02",
            timestamp_utc="2026-11-22T08:00:00Z",
            measured_metric="soc_t_c_ha",
            value=30.0,
            unit="t_c_ha",
            laboratory_or_sensor="AgriLab",
        )
    ]

    cert = engine.mint_carbon_certificate(assessment, records, farm_area_ha=2.5)

    assert cert.certificate_id.startswith("VCU-")
    assert cert.status == CreditStatus.MINTED
    assert cert.area_ha == 2.5
    assert cert.net_credits_issued_t_co2e == assessment.net_mintable_vcu
    assert len(cert.merkle_root_hash) == 64
    assert cert.retired_by is None


def test_retire_carbon_certificate_success():
    """Verify permanent retirement of carbon certificate."""
    engine = CarbonMRVEngine()
    assessment = engine.evaluate_additionality(25.0, 28.0, 2.0)
    cert = engine.mint_carbon_certificate(assessment, [])

    retired = engine.retire_certificate(
        cert=cert,
        retiring_entity="Vinamilk ESG Offsetting Fund",
        reason="Offsetting 2026 Scope 1 Dairy Logistics Emissions",
    )

    assert retired.status == CreditStatus.RETIRED
    assert retired.retired_by == "Vinamilk ESG Offsetting Fund"
    assert "Logistics" in (retired.retirement_reason or "")


def test_retire_already_retired_raises_error():
    """Verify double retirement of a carbon credit raises ValueError."""
    engine = CarbonMRVEngine()
    assessment = engine.evaluate_additionality(25.0, 28.0, 2.0)
    cert = engine.mint_carbon_certificate(assessment, [])

    engine.retire_certificate(cert, "Entity A", "Reason A")

    with pytest.raises(ValueError, match="already retired"):
        engine.retire_certificate(cert, "Entity B", "Reason B")
