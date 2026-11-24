"""
Unit test suite for Solar Thermal Air Collector & Latent Heat PCM Energy Storage Engine.
"""

from backend.core.solar_dryer_pcm import (
    DryerOperatingMode,
    SolarDryerPCMEngine,
)


def test_solar_collector_useful_heat_gain():
    """Verify Hottel-Whillier-Bliss solar heat collection and air temperature rise."""
    engine = SolarDryerPCMEngine()

    # Midday Dalat sunshine: 800 W/m2, ambient 24°C
    q_useful, t_out = engine.calculate_collector_heat_gain(
        solar_irradiance_w_m2=800.0,
        ambient_temp_c=24.0,
    )

    # 12 m2 * 0.78 * (800 * 0.82) = ~6,140 W
    assert 5000.0 <= q_useful <= 7000.0
    # Air temperature rise: Delta T = 6140 / (0.08 * 1005) = ~76°C rise
    assert t_out > 50.0


def test_solar_collector_zero_night():
    """Verify zero solar heat gain during nighttime or heavy blackout."""
    engine = SolarDryerPCMEngine()
    q_useful, t_out = engine.calculate_collector_heat_gain(
        solar_irradiance_w_m2=0.0,
        ambient_temp_c=18.0,
    )
    assert q_useful == 0.0
    assert t_out == 18.0


def test_pcm_liquid_fraction_solidus_liquidus():
    """Verify paraffin wax phase transition liquid fraction f_l across 44-48°C."""
    engine = SolarDryerPCMEngine()

    # Below solidus (44°C)
    assert engine.compute_pcm_liquid_fraction(40.0) == 0.0
    assert engine.compute_pcm_liquid_fraction(44.0) == 0.0

    # Halfway melted at 46°C
    assert engine.compute_pcm_liquid_fraction(46.0) == 0.5

    # Above liquidus (48°C)
    assert engine.compute_pcm_liquid_fraction(48.0) == 1.0
    assert engine.compute_pcm_liquid_fraction(55.0) == 1.0


def test_pcm_stored_energy_enthalpy():
    """Verify sensible + latent thermal storage capacity in 120 kg paraffin bed."""
    engine = SolarDryerPCMEngine()

    # Solid at 20°C datum
    e_datum = engine.compute_pcm_stored_energy_kwh(20.0, 0.0)
    assert e_datum == 0.0

    # Molten at 48°C: Latent 120kg * 210 kJ/kg = 25,200 kJ / 3600 = 7.0 kWh + sensible
    e_molten = engine.compute_pcm_stored_energy_kwh(48.0, 1.0)
    assert 7.0 <= e_molten <= 9.5


def test_step_dryer_daytime_charging():
    """Verify midday solar operation charges PCM and regulates chamber humidity."""
    engine = SolarDryerPCMEngine()

    state = engine.step_dryer_thermal(
        current_pcm_temp_c=42.0,  # cool PCM bed
        ambient_temp_c=25.0,
        ambient_rh_pct=65.0,
        solar_irradiance_w_m2=750.0,
        hour_of_day=11.0,
    )

    assert state.mode in (DryerOperatingMode.PCM_CHARGING_SOLAR, DryerOperatingMode.DIRECT_SOLAR_DRYING)
    assert state.collector_useful_heat_gain_w > 4000.0
    assert state.pcm_heat_exchange_w > 0.0  # Heat transferred into PCM
    # Psychrometrics: heating ambient air lowers chamber RH significantly
    assert state.chamber_air_rh_pct < 35.0


def test_step_dryer_nighttime_discharging():
    """Verify nighttime PCM latent discharge keeps chamber warm and prevents condensation."""
    engine = SolarDryerPCMEngine()

    # Nighttime: 0 W/m2, cold ambient 16°C, high RH 85%, warm PCM 47°C
    state = engine.step_dryer_thermal(
        current_pcm_temp_c=47.0,
        ambient_temp_c=16.0,
        ambient_rh_pct=85.0,
        solar_irradiance_w_m2=0.0,
        hour_of_day=22.0,
    )

    assert state.mode == DryerOperatingMode.PCM_DISCHARGING_NIGHT
    # PCM warms incoming night air
    assert state.chamber_inlet_temp_c > 25.0
    # Warming prevents dew point condensation, keeping RH well below ambient 85%
    assert state.chamber_air_rh_pct < 75.0


def test_step_dryer_auxiliary_backup():
    """Verify auxiliary biogas CHP heat activates when PCM is exhausted at night."""
    engine = SolarDryerPCMEngine()

    # Cold PCM (18°C) equal to ambient (18°C), 0 solar
    state = engine.step_dryer_thermal(
        current_pcm_temp_c=18.0,
        ambient_temp_c=18.0,
        ambient_rh_pct=80.0,
        solar_irradiance_w_m2=0.0,
        auxiliary_heat_available_w=2000.0,
        hour_of_day=3.0,
    )

    assert state.mode == DryerOperatingMode.AUXILIARY_BIOMASS_BOOST
    assert state.auxiliary_heat_supplied_w >= 1800.0
    assert state.chamber_inlet_temp_c > state.ambient_temp_c
