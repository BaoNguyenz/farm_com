"""
Unit tests for Combined Heat and Power (CHP) Micro-Turbine & Digestate Valorization.
"""

from backend.core.biogas_chp import (
    BiogasCHPEngine,
    CHPCogenerationResult,
    DigestateSeparationResult,
)


def test_chp_power_and_heat_yield_scaling() -> None:
    engine = BiogasCHPEngine(electrical_efficiency=0.33, thermal_efficiency=0.52)

    # 15 m3 of biogas at 62% CH4
    cogen = engine.simulate_chp_generation(
        biogas_volume_m3=15.0,
        methane_pct=62.0,
        parasitic_digester_heat_demand_kwh=10.0,
    )

    assert isinstance(cogen, CHPCogenerationResult)
    assert cogen.biogas_consumed_m3 == 15.0
    assert cogen.electricity_generated_kwh > 25.0
    assert cogen.heat_recovered_kwh > 40.0
    assert cogen.electricity_generated_kwh < cogen.heat_recovered_kwh


def test_chp_cogen_efficiency_bounds() -> None:
    engine = BiogasCHPEngine(electrical_efficiency=0.33, thermal_efficiency=0.52)

    cogen = engine.simulate_chp_generation(biogas_volume_m3=20.0, methane_pct=60.0)

    assert cogen.electrical_efficiency_pct == 33.0
    assert cogen.thermal_efficiency_pct == 52.0
    assert cogen.total_cogen_efficiency_pct == 85.0


def test_waste_heat_dispatch_priority() -> None:
    engine = BiogasCHPEngine()

    # When heat demand of digester jacket is 15 kWh and total heat recovered is 45 kWh
    cogen = engine.simulate_chp_generation(
        biogas_volume_m3=15.0,
        parasitic_digester_heat_demand_kwh=15.0,
    )

    assert cogen.heat_to_digester_kwh == 15.0
    assert cogen.heat_to_greenhouse_aquaponics_kwh == round(cogen.heat_recovered_kwh - 15.0, 2)
    assert cogen.heat_to_greenhouse_aquaponics_kwh > 0.0


def test_scrubbed_co2_and_ghg_abatement() -> None:
    engine = BiogasCHPEngine()

    cogen = engine.simulate_chp_generation(biogas_volume_m3=10.0, methane_pct=60.0)

    # 10 m3 biogas produces ~18.2 kg CO2 scrubbed
    assert 17.0 <= cogen.scrubbed_co2_kg <= 19.5
    # Positive GHG abatement from displaced grid power & fossil heat
    assert cogen.ghg_avoided_kg_co2e > 20.0


def test_digestate_solid_liquid_separation() -> None:
    engine = BiogasCHPEngine()

    res = engine.fractionate_digestate(digestate_effluent_liters=500.0, digester_core_temp_c=37.0)

    assert isinstance(res, DigestateSeparationResult)
    assert res.raw_digestate_volume_liters == 500.0
    assert 60.0 <= res.solid_fraction_kg <= 80.0
    assert 400.0 <= res.liquid_fraction_liters <= 440.0
    assert res.liquid_n_ppm > 1000.0  # Rich in ammonium nitrogen
    assert res.liquid_k2o_ppm > 1500.0  # Rich in soluble potassium
    assert res.solid_organic_matter_pct > 60.0


def test_pasteurization_compliance_rule() -> None:
    engine = BiogasCHPEngine()

    # Core temperature 37C compliant vs 25C non-compliant
    res_warm = engine.fractionate_digestate(digestate_effluent_liters=100.0, digester_core_temp_c=37.0)
    res_cold = engine.fractionate_digestate(digestate_effluent_liters=100.0, digester_core_temp_c=25.0)

    assert res_warm.pasteurization_compliant is True
    assert res_cold.pasteurization_compliant is False
