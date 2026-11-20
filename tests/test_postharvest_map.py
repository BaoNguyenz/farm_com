"""
Unit tests for Modified Atmosphere Packaging (MAP) & Cold-Chain Compliance Engine.
"""

from backend.core.postharvest_map import (
    FILM_CATALOG,
    ColdChainAuditLog,
    MAPPackageDesignResult,
    ModifiedAtmospherePackagingEngine,
    PackagingFilmType,
)


def test_film_catalog_properties_and_selectivity_beta() -> None:
    film_ldpe = FILM_CATALOG[PackagingFilmType.LDPE_50_MICRON]
    film_pp = FILM_CATALOG[PackagingFilmType.MICRO_PERFORATED_PP]
    assert film_pp.o2_permeance_ml_m2_day_atm > 10000.0
    assert film_pp.co2_permeance_ml_m2_day_atm > film_pp.o2_permeance_ml_m2_day_atm
    # Selectivity ratio beta P_CO2 / P_O2 for polymer film LDPE is ~4.0
    assert 3.5 <= film_ldpe.selectivity_ratio_beta <= 4.5


def test_equilibrium_modified_atmosphere_solution() -> None:
    engine = ModifiedAtmospherePackagingEngine(PackagingFilmType.MICRO_PERFORATED_PP)

    # 0.5 kg strawberries in a 0.04 m2 package at 2C (R_O2 = 8.5 ml/kg*h)
    result = engine.solve_equilibrium_atmosphere(
        fruit_mass_kg=0.5,
        package_area_m2=0.04,
        storage_temp_c=2.0,
        fruit_r_o2_ml_kg_h=8.5,
    )

    assert isinstance(result, MAPPackageDesignResult)
    assert 2.0 <= result.equilibrium_o2_pct <= 6.0
    assert 10.0 <= result.equilibrium_co2_pct <= 18.0
    assert result.anaerobic_fermentation_risk is False
    assert result.package_status == "OPTIMAL_PRESERVATION_WINDOW"


def test_botrytis_gray_mold_fungal_suppression_under_high_co2() -> None:
    engine = ModifiedAtmospherePackagingEngine(PackagingFilmType.MICRO_PERFORATED_PP)

    res = engine.solve_equilibrium_atmosphere(
        fruit_mass_kg=0.5,
        package_area_m2=0.04,
        storage_temp_c=2.0,
        fruit_r_o2_ml_kg_h=8.5,
    )

    # Elevated CO2 (>10%) should achieve >80% mold inhibition
    assert res.botrytis_inhibition_pct >= 80.0


def test_hypoxia_alarm_when_package_underventilated() -> None:
    engine = ModifiedAtmospherePackagingEngine(PackagingFilmType.LDPE_50_MICRON)

    # Excess fruit mass (3.0 kg) squeezed into tiny pouch (0.015 m2)
    res_choked = engine.solve_equilibrium_atmosphere(
        fruit_mass_kg=3.0,
        package_area_m2=0.015,
        storage_temp_c=10.0,
        fruit_r_o2_ml_kg_h=18.0,
    )

    assert res_choked.equilibrium_o2_pct < 1.5
    assert res_choked.anaerobic_fermentation_risk is True
    assert res_choked.package_status == "CRITICAL_HYPOXIA_OFF_FLAVORS"


def test_cold_chain_degree_hours_compliance_transit() -> None:
    engine = ModifiedAtmospherePackagingEngine()

    # Optimal reefer truck transit (24 hours at 2.5C - 3.5C)
    temps = [2.5 + (0.5 if i % 2 == 0 else -0.2) for i in range(24)]
    audit = engine.audit_cold_chain_transit(lot_id="LOT_EXP_001", hourly_temperatures_c=temps)

    assert isinstance(audit, ColdChainAuditLog)
    assert audit.total_transit_hours == 24.0
    assert audit.cumulative_degree_hours < 15.0
    assert audit.cold_chain_breach is False
    assert audit.quality_grade == "GRADE_AAA_PREMIUM"


def test_cold_chain_breach_detection_and_downgrade() -> None:
    engine = ModifiedAtmospherePackagingEngine()

    # Severe cold chain breakdown: air conditioner failed, 12 hours at 14C
    temps_broken = [2.5] * 12 + [14.0] * 12
    audit = engine.audit_cold_chain_transit(lot_id="LOT_EXP_002", hourly_temperatures_c=temps_broken)

    assert audit.cold_chain_breach is True
    assert audit.temp_abuse_hours >= 12.0
    assert audit.quality_grade == "GRADE_B_DOMESTIC_DOWNGRADE"
