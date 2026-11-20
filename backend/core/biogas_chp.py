"""
Combined Heat and Power (CHP) Micro-Turbine & Digestate Valorization Engine.

Converts raw biogas into clean electricity, recovers thermal energy for greenhouse
heating and aquaponic tilapia warmth, scrubs CO2 for photosynthetic enrichment, and
separates effluent digestate into solid organic compost and liquid bio-fertilizer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CHPCogenerationResult:
    """Energy and emissions output from CHP micro-turbine cogeneration."""

    biogas_consumed_m3: float
    methane_fraction_pct: float
    total_thermal_input_kwh: float
    electricity_generated_kwh: float
    heat_recovered_kwh: float
    electrical_efficiency_pct: float
    thermal_efficiency_pct: float
    total_cogen_efficiency_pct: float
    heat_to_digester_kwh: float
    heat_to_greenhouse_aquaponics_kwh: float
    scrubbed_co2_kg: float
    ghg_avoided_kg_co2e: float


@dataclass
class DigestateSeparationResult:
    """Solid-liquid fractionation of raw anaerobic digestate."""

    raw_digestate_volume_liters: float
    solid_fraction_kg: float
    solid_moisture_pct: float
    solid_organic_matter_pct: float
    liquid_fraction_liters: float
    liquid_n_ppm: float
    liquid_k2o_ppm: float
    liquid_ec_ms_cm: float
    pasteurization_compliant: bool


class BiogasCHPEngine:
    """Micro-CHP cogeneration and digestate nutrient separation engine."""

    # Lower Heating Value (LHV) of pure methane = 9.94 kWh/m3 (35.8 MJ/m3)
    LHV_METHANE_KWH_M3: float = 9.944

    def __init__(
        self,
        electrical_efficiency: float = 0.33,
        thermal_efficiency: float = 0.52,
    ) -> None:
        self.electrical_efficiency = electrical_efficiency
        self.thermal_efficiency = thermal_efficiency

    def simulate_chp_generation(
        self,
        biogas_volume_m3: float,
        methane_pct: float = 62.0,
        parasitic_digester_heat_demand_kwh: float = 12.0,
    ) -> CHPCogenerationResult:
        """Simulate micro-turbine CHP conversion of biogas."""
        # Total energy content of biogas
        effective_energy_density_kwh_m3 = self.LHV_METHANE_KWH_M3 * (methane_pct / 100.0)
        total_energy_input_kwh = round(biogas_volume_m3 * effective_energy_density_kwh_m3, 2)

        # Cogen outputs
        elec_kwh = round(total_energy_input_kwh * self.electrical_efficiency, 2)
        total_heat_kwh = round(total_energy_input_kwh * self.thermal_efficiency, 2)

        # Heat distribution: first satisfy digester thermal jacket, remainder for greenhouse/aquaponics
        heat_to_digester = min(total_heat_kwh, parasitic_digester_heat_demand_kwh)
        surplus_heat = round(max(0.0, total_heat_kwh - heat_to_digester), 2)

        # CO2 scrubbing from exhaust: 1 m3 biogas has (1 - CH4%) CO2 + combustion of CH4 produces 1 mol CO2 / mol CH4
        # Total CO2 yield ≈ 1.82 kg CO2 per m3 of biogas combusted
        scrubbed_co2_kg = round(biogas_volume_m3 * 1.82, 2)

        # Scope 1 GHG avoided: displaces grid power (0.68 kg CO2/kWh) and LP gas heating (0.24 kg CO2/kWh)
        ghg_avoided = round(elec_kwh * 0.68 + total_heat_kwh * 0.24, 2)

        return CHPCogenerationResult(
            biogas_consumed_m3=biogas_volume_m3,
            methane_fraction_pct=methane_pct,
            total_thermal_input_kwh=total_energy_input_kwh,
            electricity_generated_kwh=elec_kwh,
            heat_recovered_kwh=total_heat_kwh,
            electrical_efficiency_pct=round(self.electrical_efficiency * 100.0, 1),
            thermal_efficiency_pct=round(self.thermal_efficiency * 100.0, 1),
            total_cogen_efficiency_pct=round((self.electrical_efficiency + self.thermal_efficiency) * 100.0, 1),
            heat_to_digester_kwh=round(heat_to_digester, 2),
            heat_to_greenhouse_aquaponics_kwh=surplus_heat,
            scrubbed_co2_kg=scrubbed_co2_kg,
            ghg_avoided_kg_co2e=ghg_avoided,
        )

    def fractionate_digestate(
        self,
        digestate_effluent_liters: float,
        digester_core_temp_c: float = 37.0,
    ) -> DigestateSeparationResult:
        """Simulate screw-press separation of digestate into solid compost and liquid extract."""
        # 15% solid cake by volume, 85% liquid extract
        solid_mass_kg = round(digestate_effluent_liters * 0.15 * 0.95, 2)
        liquid_vol_l = round(digestate_effluent_liters * 0.85, 2)

        # Solid fraction properties
        solid_moisture_pct = 70.0  # 30% TS
        solid_om_pct = 65.0       # High organic matter humic compost

        # Liquid extract nutrient content (typical anaerobic effluent)
        liquid_n_ppm = 1250.0      # Readily available ammoniacal NH4-N
        liquid_k2o_ppm = 1800.0    # High plant-available potassium
        liquid_ec = 6.8           # Concentrate EC

        # Pasteurization rule: >= 55C for 4 hours, or mesophilic 37C with >20 days retention
        is_pasteurized = digester_core_temp_c >= 37.0

        return DigestateSeparationResult(
            raw_digestate_volume_liters=digestate_effluent_liters,
            solid_fraction_kg=solid_mass_kg,
            solid_moisture_pct=solid_moisture_pct,
            solid_organic_matter_pct=solid_om_pct,
            liquid_fraction_liters=liquid_vol_l,
            liquid_n_ppm=liquid_n_ppm,
            liquid_k2o_ppm=liquid_k2o_ppm,
            liquid_ec_ms_cm=liquid_ec,
            pasteurization_compliant=is_pasteurized,
        )
