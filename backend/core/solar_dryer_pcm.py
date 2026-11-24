"""
Solar Air Collector & Latent Heat Phase Change Material (PCM) Thermal Storage Engine.

Simulates solar-thermal hybrid post-harvest drying facility dynamics:
- Glazed flat-plate solar air collector with Hottel-Whillier-Bliss thermal equations.
- Paraffin wax PCM storage bed (melting range 44-48°C, latent heat of fusion 210 kJ/kg).
- Enthalpy tracking and liquid fraction dynamics during daytime charging and nighttime discharge.
- Automatic integration with Phase 23 Biogas Micro-CHP auxiliary waste heat for zero-fossil operation.
- Continuous 24/7 moisture removal preventing nighttime reabsorption and Aspergillus/Botrytis spoilage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class DryerOperatingMode(str, Enum):
    """Operational thermal state of the solar-PCM drying facility."""
    DIRECT_SOLAR_DRYING = "direct_solar_drying"
    PCM_CHARGING_SOLAR = "pcm_charging_solar"
    PCM_DISCHARGING_NIGHT = "pcm_discharging_night"
    AUXILIARY_BIOMASS_BOOST = "auxiliary_biomass_boost"
    STANDBY_PURGE = "standby_purge"


class SolarCollectorSpecs(BaseModel):
    """Geometric and thermal performance characteristics of glazed solar air collector."""
    collector_area_m2: float = Field(12.0, gt=0.0, description="Gross aperture area (m^2)")
    optical_efficiency_tau_alpha: float = Field(0.82, ge=0.5, le=0.95, description="Transmittance-absorptance product")
    heat_loss_coefficient_ul: float = Field(4.5, gt=0.0, description="Overall heat loss coefficient (W/m^2*K)")
    heat_removal_factor_fr: float = Field(0.78, ge=0.4, le=0.95, description="Collector heat removal factor F_R")
    air_mass_flow_rate_kg_s: float = Field(0.08, gt=0.0, description="Drying blower air mass flow (~250 m^3/h)")


class PCMBedSpecs(BaseModel):
    """Thermophysical specifications of paraffin wax phase change material bed."""
    pcm_mass_kg: float = Field(120.0, gt=0.0, description="Total encapsulated PCM mass in kg")
    melting_solidus_temp_c: float = Field(44.0, description="Temperature where melting begins (°C)")
    melting_liquidus_temp_c: float = Field(48.0, description="Temperature where melting is complete (°C)")
    latent_heat_of_fusion_kj_kg: float = Field(210.0, gt=0.0, description="Latent heat L_f (kJ/kg)")
    specific_heat_solid_kj_kg_k: float = Field(2.0, gt=0.0, description="Solid sensible specific heat")
    specific_heat_liquid_kj_kg_k: float = Field(2.4, gt=0.0, description="Liquid sensible specific heat")
    heat_transfer_ua_w_k: float = Field(220.0, gt=0.0, description="Overall thermal conductance UA (W/K)")


class SolarDryerThermalState(BaseModel):
    """Instantaneous thermal and energy balances across solar collector, PCM, and chamber."""
    timestamp_hour: float
    ambient_temp_c: float
    ambient_rh_pct: float
    solar_irradiance_w_m2: float
    collector_useful_heat_gain_w: float
    collector_outlet_temp_c: float
    pcm_temp_c: float
    pcm_liquid_fraction: float = Field(..., ge=0.0, le=1.0, description="Fraction of molten paraffin [0.0, 1.0]")
    pcm_stored_energy_kwh: float
    pcm_heat_exchange_w: float = Field(..., description="Positive = charging, Negative = discharging")
    chamber_inlet_temp_c: float
    chamber_air_rh_pct: float
    auxiliary_heat_supplied_w: float
    mode: DryerOperatingMode


@dataclass
class SolarDryerPCMEngine:
    """
    Simulates coupled solar collector, PCM thermal storage bed, and drying chamber temperatures.
    """
    AIR_SPECIFIC_HEAT_CP_J_KG_K: ClassVar[float] = 1005.0  # Air specific heat (J/kg*K)

    def __init__(
        self,
        collector_specs: SolarCollectorSpecs | None = None,
        pcm_specs: PCMBedSpecs | None = None,
    ) -> None:
        self.collector = collector_specs or SolarCollectorSpecs()
        self.pcm = pcm_specs or PCMBedSpecs()

    def calculate_collector_heat_gain(
        self,
        solar_irradiance_w_m2: float,
        ambient_temp_c: float,
        inlet_temp_c: float | None = None,
    ) -> tuple[float, float]:
        """
        Calculates useful solar heat collection Q_u and outlet air temperature:
        Q_u = A * F_R * [I * (tau*alpha) - U_L * (T_in - T_amb)]
        Delta T = Q_u / (m_dot * C_p)
        """
        t_in = inlet_temp_c if inlet_temp_c is not None else ambient_temp_c
        absorbed_flux = solar_irradiance_w_m2 * self.collector.optical_efficiency_tau_alpha
        thermal_losses = self.collector.heat_loss_coefficient_ul * max(0.0, t_in - ambient_temp_c)
        net_flux = max(0.0, absorbed_flux - thermal_losses)

        q_useful_w = self.collector.collector_area_m2 * self.collector.heat_removal_factor_fr * net_flux

        # Temperature rise across collector
        heat_capacity_rate = self.collector.air_mass_flow_rate_kg_s * self.AIR_SPECIFIC_HEAT_CP_J_KG_K
        delta_t = q_useful_w / heat_capacity_rate if heat_capacity_rate > 0 else 0.0
        t_out = round(t_in + delta_t, 2)

        return round(q_useful_w, 1), t_out

    def compute_pcm_liquid_fraction(self, pcm_temp_c: float) -> float:
        """Calculates fraction of molten liquid paraffin [0.0 = solid, 1.0 = liquid]."""
        if pcm_temp_c <= self.pcm.melting_solidus_temp_c:
            return 0.0
        if pcm_temp_c >= self.pcm.melting_liquidus_temp_c:
            return 1.0
        fraction = (pcm_temp_c - self.pcm.melting_solidus_temp_c) / (
            self.pcm.melting_liquidus_temp_c - self.pcm.melting_solidus_temp_c
        )
        return round(fraction, 3)

    def compute_pcm_stored_energy_kwh(self, pcm_temp_c: float, liquid_frac: float) -> float:
        """
        Total sensible + latent thermal energy stored in PCM relative to 20°C datum:
        E = M * [C_p,s * (T_solidus - 20) + f_l * L_f + C_p,l * max(0, T - T_liquidus)] / 3600
        """
        t_ref = 20.0
        t_sol = self.pcm.melting_solidus_temp_c
        t_liq = self.pcm.melting_liquidus_temp_c

        # Sensible solid
        sensible_solid = self.pcm.specific_heat_solid_kj_kg_k * max(0.0, min(pcm_temp_c, t_sol) - t_ref)
        # Latent fusion
        latent = liquid_frac * self.pcm.latent_heat_of_fusion_kj_kg
        # Sensible liquid
        sensible_liquid = self.pcm.specific_heat_liquid_kj_kg_k * max(0.0, pcm_temp_c - t_liq)

        total_kj = self.pcm.pcm_mass_kg * (sensible_solid + latent + sensible_liquid)
        return round(total_kj / 3600.0, 2)

    def step_dryer_thermal(
        self,
        current_pcm_temp_c: float,
        ambient_temp_c: float,
        ambient_rh_pct: float,
        solar_irradiance_w_m2: float,
        dt_seconds: float = 3600.0,  # 1 hour
        auxiliary_heat_available_w: float = 0.0,
        hour_of_day: float = 12.0,
    ) -> SolarDryerThermalState:
        """
        Simulates 1-step dynamic thermal balance across collector, PCM storage, and chamber.
        """
        q_solar_w, t_col_out = self.calculate_collector_heat_gain(
            solar_irradiance_w_m2=solar_irradiance_w_m2,
            ambient_temp_c=ambient_temp_c,
        )

        heat_capacity_rate = self.collector.air_mass_flow_rate_kg_s * self.AIR_SPECIFIC_HEAT_CP_J_KG_K

        # Heat exchanger effectiveness (epsilon-NTU method) for air-PCM bed
        ntu = self.pcm.heat_transfer_ua_w_k / heat_capacity_rate if heat_capacity_rate > 0 else 1.0
        effectiveness = 1.0 - math.exp(-ntu)

        aux_used_w = 0.0

        if solar_irradiance_w_m2 >= 200.0:
            # Daytime solar mode: hot air from collector transfers heat to PCM
            delta_t_available = t_col_out - current_pcm_temp_c
            if delta_t_available > 0:
                mode = DryerOperatingMode.PCM_CHARGING_SOLAR
                q_pcm_w = effectiveness * heat_capacity_rate * delta_t_available
                # Air temperature leaving PCM into drying chamber
                t_chamber_in = t_col_out - (q_pcm_w / heat_capacity_rate)
            else:
                mode = DryerOperatingMode.DIRECT_SOLAR_DRYING
                q_pcm_w = 0.0
                t_chamber_in = t_col_out
        else:
            # Night or overcast: PCM discharges into cooler incoming air
            delta_t_night = current_pcm_temp_c - ambient_temp_c
            if delta_t_night >= 3.0:
                mode = DryerOperatingMode.PCM_DISCHARGING_NIGHT
                discharge_w = effectiveness * heat_capacity_rate * delta_t_night
                q_pcm_w = -discharge_w  # negative indicates discharge
                t_chamber_in = ambient_temp_c + (discharge_w / heat_capacity_rate)
            else:
                # PCM exhausted: trigger auxiliary biogas CHP waste heat
                mode = DryerOperatingMode.AUXILIARY_BIOMASS_BOOST
                q_pcm_w = 0.0
                aux_used_w = auxiliary_heat_available_w if auxiliary_heat_available_w > 0 else 1800.0
                t_chamber_in = ambient_temp_c + (aux_used_w / heat_capacity_rate)

        # Update PCM temperature based on net heat exchange: dT = (Q_pcm * dt) / (M * C_eff)
        liquid_frac = self.compute_pcm_liquid_fraction(current_pcm_temp_c)
        if 0.0 < liquid_frac < 1.0:
            # High effective heat capacity in melting zone
            c_eff_j_kg_k = (self.pcm.latent_heat_of_fusion_kj_kg / (self.pcm.melting_liquidus_temp_c - self.pcm.melting_solidus_temp_c)) * 1000.0
        elif liquid_frac >= 1.0:
            c_eff_j_kg_k = self.pcm.specific_heat_liquid_kj_kg_k * 1000.0
        else:
            c_eff_j_kg_k = self.pcm.specific_heat_solid_kj_kg_k * 1000.0

        thermal_mass_j_k = self.pcm.pcm_mass_kg * c_eff_j_kg_k
        delta_pcm_t = (q_pcm_w * dt_seconds) / thermal_mass_j_k if thermal_mass_j_k > 0 else 0.0

        # Thermal inertia clamping
        new_pcm_temp = round(max(15.0, min(65.0, current_pcm_temp_c + delta_pcm_t)), 2)
        new_liquid_frac = self.compute_pcm_liquid_fraction(new_pcm_temp)
        stored_kwh = self.compute_pcm_stored_energy_kwh(new_pcm_temp, new_liquid_frac)

        # Psychrometrics: relative humidity inside chamber drops as temperature rises
        # Tetens equation approximation for saturation vapor pressure
        p_sat_amb = 0.61078 * math.exp((17.27 * ambient_temp_c) / (ambient_temp_c + 237.3))
        p_sat_cham = 0.61078 * math.exp((17.27 * t_chamber_in) / (t_chamber_in + 237.3))
        actual_vapor_p = (ambient_rh_pct / 100.0) * p_sat_amb
        chamber_rh = (actual_vapor_p / p_sat_cham) * 100.0
        chamber_rh_clamped = round(max(10.0, min(95.0, chamber_rh)), 1)

        return SolarDryerThermalState(
            timestamp_hour=hour_of_day,
            ambient_temp_c=ambient_temp_c,
            ambient_rh_pct=ambient_rh_pct,
            solar_irradiance_w_m2=solar_irradiance_w_m2,
            collector_useful_heat_gain_w=q_solar_w,
            collector_outlet_temp_c=t_col_out,
            pcm_temp_c=new_pcm_temp,
            pcm_liquid_fraction=new_liquid_frac,
            pcm_stored_energy_kwh=stored_kwh,
            pcm_heat_exchange_w=round(q_pcm_w, 1),
            chamber_inlet_temp_c=round(t_chamber_in, 2),
            chamber_air_rh_pct=chamber_rh_clamped,
            auxiliary_heat_supplied_w=round(aux_used_w, 1),
            mode=mode,
        )
