"""
Integration test suite for RothC Soil Organic Carbon & Verra VM0042 MRV Carbon Credits REST API.
"""

from fastapi.testclient import TestClient

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.main import app

client = TestClient(app)


def test_get_carbon_mrv_telemetry():
    """Verify GET /api/v1/carbon-mrv/telemetry returns SOC pools, additionality, and Merkle root."""
    response = client.get("/api/v1/carbon-mrv/telemetry")
    assert response.status_code == 200
    data = response.json()

    assert "current_pools" in data
    assert data["total_soc_t_c_ha"] > 20.0
    assert "soil_carbon_health" in data
    assert "additionality" in data
    assert "merkle_root_hash" in data
    assert len(data["merkle_root_hash"]) == 64
    assert "monetization" in data


def test_post_simulate_rothc():
    """Verify POST /api/v1/carbon-mrv/simulate-rothc executes 1-month turnover with amendment."""
    payload = {
        "temp_c": 22.0,
        "smd_mm": 12.0,
        "vegetated": True,
        "amendment_type": "biochar",
        "carbon_input_t_c_per_ha": 3.0,
        "inert_biochar_fraction": 0.95,
    }
    response = client.post("/api/v1/carbon-mrv/simulate-rothc", json=payload)
    assert response.status_code == 200
    res = response.json()

    assert res["carbon_input_t_c_ha"] == 3.0
    assert res["pools_after"]["iom"] > res["pools_before"]["iom"]
    assert res["net_soc_change_t_c_ha"] > 0.0
    assert "modifiers" in res
    assert res["modifiers"]["net_rate_modifier_xi"] > 0.0


def test_post_evaluate_additionality():
    """Verify POST /api/v1/carbon-mrv/evaluate-additionality computes Verra VM0042 metrics."""
    payload = {
        "baseline_soc_t_c_ha": 26.0,
        "project_soc_t_c_ha": 32.0,
        "farm_area_ha": 2.5,
    }
    response = client.post("/api/v1/carbon-mrv/evaluate-additionality", json=payload)
    assert response.status_code == 200
    res = response.json()

    assert res["net_additionality_t_c_ha"] == 6.0
    assert res["total_gross_co2e_tonnes"] > 50.0
    assert res["buffer_pool_tonnes"] > 0.0
    assert res["net_mintable_vcu"] > 40.0
    assert res["market_value_usd"] > 1000.0


def test_post_issue_credits_success():
    """Verify POST /api/v1/carbon-mrv/issue-credits mints a certificate with Merkle root."""
    payload = {
        "baseline_soc_t_c_ha": 27.0,
        "project_soc_t_c_ha": 31.5,
        "farm_area_ha": 3.0,
        "evidence_records": [
            {
                "record_id": "REC-TEST-01",
                "evidence_type": "soil_core_lab",
                "plot_id": "PLOT-01",
                "timestamp_utc": "2026-11-22T08:00:00Z",
                "measured_metric": "soc_combustion_pct",
                "value": 2.65,
                "unit": "pct_c",
                "laboratory_or_sensor": "Eurofins Agroscience",
            }
        ],
    }
    response = client.post("/api/v1/carbon-mrv/issue-credits", json=payload)
    assert response.status_code == 200
    cert = response.json()

    assert cert["certificate_id"].startswith("VCU-")
    assert cert["status"] == "minted"
    assert cert["net_credits_issued_t_co2e"] > 0.0
    assert len(cert["merkle_root_hash"]) == 64

    # Test retirement on the newly minted certificate
    retire_payload = {
        "certificate_id": cert["certificate_id"],
        "retiring_entity": "AgriTech Carbon Offsetting Fund",
        "retirement_reason": "Net Zero 2026 Offset",
    }
    retire_res = client.post("/api/v1/carbon-mrv/retire-credits", json=retire_payload)
    assert retire_res.status_code == 200
    retired_cert = retire_res.json()
    assert retired_cert["status"] == "retired"
    assert retired_cert["retired_by"] == "AgriTech Carbon Offsetting Fund"


def test_post_issue_credits_no_additionality_rejected():
    """Verify certificate minting is rejected when project SOC <= baseline SOC."""
    payload = {
        "baseline_soc_t_c_ha": 30.0,
        "project_soc_t_c_ha": 28.0,  # no additionality
        "farm_area_ha": 3.0,
    }
    response = client.post("/api/v1/carbon-mrv/issue-credits", json=payload)
    assert response.status_code == 400
    assert "positive additionality" in response.json()["detail"]


def test_agent_council_debate_on_soil_carbon():
    """Verify Agronomist and Market agent votes on soil carbon proposals."""
    agronomist = AgronomistAgent()
    market = MarketAgent()

    # 1. Proposal for deep tillage: Agronomist issues carbon loss veto
    tillage_proposal = {"action_type": "deep_tillage", "action_domain": "soil_management"}
    agro_tillage_vote = agronomist.vote_on_proposal(proposal=tillage_proposal, context={})
    assert agro_tillage_vote.vote.lower() in ("reject", "veto")
    assert "SOIL CARBON LOSS VETO" in agro_tillage_vote.rationale

    # 2. Proposal for biochar application: Agronomist approves
    biochar_proposal = {"action_type": "apply_biochar", "action_domain": "soil_management"}
    agro_biochar_vote = agronomist.vote_on_proposal(proposal=biochar_proposal, context={})
    assert agro_biochar_vote.vote.lower() in ("approve", "accept")

    # 3. Proposal for Verra carbon credit issuance: Market agent endorses
    credit_proposal = {"action_type": "issue_carbon_credits", "action_domain": "carbon_offsetting"}
    market_credit_vote = market.vote_on_proposal(proposal=credit_proposal, context={})
    assert market_credit_vote.vote.lower() in ("approve", "accept")
    assert "VM0042" in market_credit_vote.rationale
