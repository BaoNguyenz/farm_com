"""
Unit test suite for RothC-26.3 Soil Organic Carbon (SOC) Turnover Kinetics & Biochar Persistence.
"""

from backend.core.carbon_rothc import (
    CarbonAmendment,
    RothCKineticsEngine,
    RothCPools,
)


def test_rothc_temperature_modifier():
    """Verify temperature rate modifier a(T) scaling according to RothC sigmoid."""
    engine = RothCKineticsEngine()

    a_cold = engine.compute_temperature_modifier(5.0)
    a_moderate = engine.compute_temperature_modifier(20.0)
    a_warm = engine.compute_temperature_modifier(35.0)

    assert 0.0 < a_cold < a_moderate < a_warm
    assert 0.3 <= a_cold <= 0.7
    assert 2.0 <= a_moderate <= 3.5
    assert 4.5 <= a_warm <= 6.5

    # Sub-freezing boundary
    assert engine.compute_temperature_modifier(-20.0) == 0.0


def test_rothc_moisture_modifier():
    """Verify soil moisture deficit modifier b(M) decreases with dry soil."""
    engine = RothCKineticsEngine()

    b_saturated = engine.compute_moisture_modifier(0.0)
    b_moderate = engine.compute_moisture_modifier(25.0)
    b_dry = engine.compute_moisture_modifier(50.0)

    assert b_saturated == 1.0
    assert 0.5 <= b_moderate <= 0.7
    assert b_dry == 0.2  # minimum floor


def test_clay_protection_partitioning():
    """Verify higher clay content protects microbial carbon and suppresses CO2 respiration."""
    engine = RothCKineticsEngine()

    # Compare sandy soil (10% clay) vs heavy basalt clay (50% clay)
    _, f_co2_sand, f_bio_sand, f_hum_sand = engine.compute_clay_partitioning(10.0)
    _, f_co2_clay, f_bio_clay, f_hum_clay = engine.compute_clay_partitioning(50.0)

    assert f_co2_sand > f_co2_clay  # Sandy soils respire more CO2
    assert f_bio_clay > f_bio_sand  # Clay stabilizes more microbial biomass
    assert f_hum_clay > f_hum_sand  # Clay stabilizes more humified organic matter


def test_unfertilized_decay_step():
    """Verify natural decomposition of existing pools without organic inputs."""
    engine = RothCKineticsEngine()
    initial_pools = RothCPools(dpm=1.0, rpm=5.0, bio=2.0, hum=30.0, iom=5.0)

    step = engine.step_month(
        pools=initial_pools,
        temp_c=22.0,
        smd_mm=10.0,
        vegetated=True,
        amendment=None,
    )

    assert step.net_soc_change_t_c_ha < 0.0  # net loss of carbon without inputs
    assert step.co2_emitted_t_co2_ha > 0.0
    assert step.pools_after.dpm < initial_pools.dpm  # fast pool decayed
    assert step.pools_after.iom == initial_pools.iom  # inert pool does not decay


def test_crop_residue_amendment_partitioning():
    """Verify fresh crop residue increases DPM and RPM pools according to 1.44 ratio."""
    engine = RothCKineticsEngine()
    initial_pools = RothCPools(dpm=0.5, rpm=2.0, bio=1.0, hum=20.0, iom=4.0)

    amendment = CarbonAmendment(
        amendment_type="crop_residue",
        carbon_input_t_c_per_ha=2.0,
        dpm_rpm_ratio=1.44,
    )

    step = engine.step_month(
        pools=initial_pools,
        temp_c=20.0,
        amendment=amendment,
    )

    assert step.pools_after.dpm > initial_pools.dpm
    assert step.pools_after.rpm > initial_pools.rpm
    assert step.net_soc_change_t_c_ha > 0.0  # net positive carbon accumulation


def test_biochar_amendment_recalcitrance():
    """Verify biochar application partitions primarily to inert IOM pool with minimal immediate CO2."""
    engine = RothCKineticsEngine()
    initial_pools = RothCPools(dpm=0.5, rpm=2.0, bio=1.0, hum=20.0, iom=4.0)

    # 3.0 tonnes C/ha biochar with 95% recalcitrant inert fraction
    biochar = CarbonAmendment(
        amendment_type="biochar",
        carbon_input_t_c_per_ha=3.0,
        inert_biochar_fraction=0.95,
    )

    step = engine.step_month(
        pools=initial_pools,
        temp_c=22.0,
        amendment=biochar,
    )

    # 3.0 * 0.95 = 2.85 tonnes added to IOM
    expected_iom = initial_pools.iom + 2.85
    assert abs(step.pools_after.iom - expected_iom) < 0.05
    assert step.pools_after.total_soc > (initial_pools.total_soc + 2.0)


def test_anaerobic_digestate_amendment():
    """Verify anaerobic digestate directly enriches humified organic pool."""
    engine = RothCKineticsEngine()
    initial_pools = RothCPools(dpm=0.5, rpm=2.0, bio=1.0, hum=20.0, iom=4.0)

    digestate = CarbonAmendment(
        amendment_type="digestate",
        carbon_input_t_c_per_ha=1.5,
    )

    step = engine.step_month(
        pools=initial_pools,
        temp_c=20.0,
        amendment=digestate,
    )

    assert step.pools_after.hum > initial_pools.hum
    assert step.net_soc_change_t_c_ha > 0.0
