"""
Unit tests for Anaerobic Digestion (AD) & Biogas Kinetic Engine.
"""

from backend.core.biogas_digestion import (
    FEEDSTOCK_CATALOG,
    AnaerobicDigesterEngine,
    FeedstockCharacteristics,
    FeedstockType,
)


def test_feedstock_catalog_properties() -> None:
    props = FEEDSTOCK_CATALOG[FeedstockType.CO_DIGESTION_MIX]
    assert isinstance(props, FeedstockCharacteristics)
    assert 10.0 <= props.total_solids_pct <= 20.0
    assert 70.0 <= props.volatile_solids_pct_ts <= 90.0
    assert props.methane_fraction_pct > 60.0
    assert 20.0 <= props.c_to_n_ratio <= 30.0  # Optimal C:N for stable methanogenesis


def test_mesophilic_vs_psychrophilic_temperature_effect() -> None:
    engine = AnaerobicDigesterEngine(digester_volume_m3=25.0)

    # 37C (mesophilic) vs 20C (cold ambient)
    res_meso = engine.simulate_digestion(
        feedstock_type=FeedstockType.CROP_RESIDUES,
        feed_mass_kg_day=150.0,
        override_temp_c=37.0,
    )
    res_cold = engine.simulate_digestion(
        feedstock_type=FeedstockType.CROP_RESIDUES,
        feed_mass_kg_day=150.0,
        override_temp_c=20.0,
    )

    # Mesophilic produces significantly more biogas and higher VS destruction
    assert res_meso.daily_biogas_m3 > res_cold.daily_biogas_m3
    assert res_meso.vs_destruction_efficiency_pct > res_cold.vs_destruction_efficiency_pct
    assert res_meso.vfa_tic_ratio < res_cold.vfa_tic_ratio


def test_co_digestion_biogas_yield() -> None:
    engine = AnaerobicDigesterEngine(digester_volume_m3=25.0, operating_temp_c=37.0)

    result = engine.simulate_digestion(
        feedstock_type=FeedstockType.CO_DIGESTION_MIX,
        feed_mass_kg_day=200.0,
        retention_days=25.0,
    )

    assert result.feedstock == FeedstockType.CO_DIGESTION_MIX
    assert result.daily_biogas_m3 > 0.0
    assert result.daily_methane_m3 > 0.0
    assert result.daily_co2_m3 > 0.0
    assert result.methane_content_pct == 62.5
    assert result.health_status == "stable_optimal"
    assert not result.acidification_hazard


def test_hydraulic_retention_time_scaling() -> None:
    engine = AnaerobicDigesterEngine(digester_volume_m3=25.0, operating_temp_c=37.0)

    # 15 days vs 30 days retention
    res_short = engine.simulate_digestion(
        feedstock_type=FeedstockType.DAIRY_MANURE,
        feed_mass_kg_day=100.0,
        retention_days=15.0,
    )
    res_long = engine.simulate_digestion(
        feedstock_type=FeedstockType.DAIRY_MANURE,
        feed_mass_kg_day=100.0,
        retention_days=30.0,
    )

    # Longer retention allows higher biodegradation / volatile solids breakdown
    assert res_long.vs_destruction_efficiency_pct > res_short.vs_destruction_efficiency_pct
    assert res_long.daily_methane_m3 > res_short.daily_methane_m3


def test_vfa_tic_acidification_alarm_on_overloading() -> None:
    engine = AnaerobicDigesterEngine(digester_volume_m3=5.0, operating_temp_c=37.0)

    # Extreme feed overloading on small 5 m3 tank (600 kg/day)
    res_overload = engine.simulate_digestion(
        feedstock_type=FeedstockType.CROP_RESIDUES,
        feed_mass_kg_day=600.0,
        retention_days=10.0,
    )

    assert res_overload.vfa_tic_ratio > 0.40
    assert res_overload.acidification_hazard is True
    assert res_overload.health_status == "sour_acidification_alarm"


def test_digestate_effluent_balance() -> None:
    engine = AnaerobicDigesterEngine(digester_volume_m3=20.0, operating_temp_c=37.0)

    res = engine.simulate_digestion(
        feedstock_type=FeedstockType.AQUAPONIC_SLUDGE,
        feed_mass_kg_day=250.0,
        retention_days=20.0,
    )

    # Effluent volume should roughly equal feed mass / 1000 with moisture ~92.5%
    assert 0.20 <= res.digestate_effluent_m3 <= 0.25
