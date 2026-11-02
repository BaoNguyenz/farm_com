"""
Agricultural Greenhouse Gas (GHG) Accounting & Carbon Footprint Engine.

Implements IPCC Tier 1 guidelines and GHG Protocol standards for precision farms:
- Scope 1: Direct soil nitrous oxide (N2O) emissions from nitrogen fertigation
- Scope 2: Indirect emissions from EVN grid electricity for irrigation pumps
- Carbon Offsetting: Soil organic carbon (SOC) sequestration from vegetative canopy cover
"""

from typing import List
from pydantic import BaseModel, Field

from backend.core.twin_state import PlotZone, FarmDigitalTwin


class CarbonEmissionFactors(BaseModel):
    """Emission coefficients based on IPCC Tier 1 & Vietnam EVN national grid benchmarks."""
    grid_electricity_kg_co2e_per_kwh: float = Field(0.7221, description="EVN Vietnam grid emission factor")
    pumping_energy_kwh_per_m3: float = Field(0.35, description="Electricity needed to pump 1 m3 water at 3 bar")
    n_fertilizer_direct_kg_co2e_per_kg_n: float = Field(4.164, description="Direct N2O volatilization GWP100 equivalent")
    daily_soil_sequestration_kg_co2e_per_m2: float = Field(0.0068, description="Soil carbon sink accrual under vegetative cover")


class ZoneCarbonFootprint(BaseModel):
    """Fine-grained carbon accounting per agricultural plot zone."""
    zone_id: str
    crop_type: str
    electricity_kwh: float
    electricity_emissions_kg_co2e: float
    nitrogen_kg: float
    fertilizer_emissions_kg_co2e: float
    carbon_sequestration_kg_co2e: float
    net_carbon_balance_kg_co2e: float


class FarmCarbonReport(BaseModel):
    """Consolidated farm-wide GHG audit and climate resilience rating."""
    farm_id: str
    elapsed_days: float
    total_electricity_kwh: float
    scope1_emissions_kg_co2e: float  # Fertilizer volatilization
    scope2_emissions_kg_co2e: float  # Grid pumping electricity
    total_gross_emissions_kg_co2e: float
    total_sequestration_kg_co2e: float
    net_footprint_kg_co2e: float
    carbon_intensity_kg_per_m2: float
    carbon_rating: str  # A_climate_positive, B_low_carbon, C_moderate, D_high_carbon
    zone_breakdowns: List[ZoneCarbonFootprint]


class CarbonAccountingEngine:
    """
    Computes real-time and cumulative carbon budgets for autonomous farm operations.
    """

    def __init__(self, factors: CarbonEmissionFactors | None = None) -> None:
        self.factors = factors or CarbonEmissionFactors()

    def calculate_zone_emissions(
        self,
        zone: PlotZone,
        water_liters_used: float = 0.0,
        nitrogen_applied_kg: float = 0.0,
        elapsed_days: float = 1.0,
        zone_area_m2: float = 25.0
    ) -> ZoneCarbonFootprint:
        """Calculates carbon footprint for a single plot zone."""
        # 1. Pumping energy and Scope 2 emissions
        water_m3 = water_liters_used / 1000.0
        electricity_kwh = water_m3 * self.factors.pumping_energy_kwh_per_m3
        elec_emissions = electricity_kwh * self.factors.grid_electricity_kg_co2e_per_kwh

        # 2. Synthetic N fertilization direct N2O emissions (Scope 1)
        fert_emissions = nitrogen_applied_kg * self.factors.n_fertilizer_direct_kg_co2e_per_kg_n

        # 3. Vegetative carbon sequestration credit
        # Sequestration is scaled by vegetative vigor (NDVI)
        sequestration_factor = max(0.2, min(1.0, zone.ndvi))
        sequestration = (
            zone_area_m2
            * self.factors.daily_soil_sequestration_kg_co2e_per_m2
            * elapsed_days
            * sequestration_factor
        )

        net_balance = (elec_emissions + fert_emissions) - sequestration

        return ZoneCarbonFootprint(
            zone_id=zone.id,
            crop_type=zone.crop_type,
            electricity_kwh=round(electricity_kwh, 3),
            electricity_emissions_kg_co2e=round(elec_emissions, 4),
            nitrogen_kg=round(nitrogen_applied_kg, 3),
            fertilizer_emissions_kg_co2e=round(fert_emissions, 4),
            carbon_sequestration_kg_co2e=round(sequestration, 4),
            net_carbon_balance_kg_co2e=round(net_balance, 4)
        )

    def calculate_farm_emissions(
        self,
        farm: FarmDigitalTwin,
        elapsed_days: float = 1.0,
        total_water_liters: float = 0.0,
        total_nitrogen_kg: float = 0.0
    ) -> FarmCarbonReport:
        """Calculates aggregated farm-wide carbon audit."""
        zone_count = max(1, len(farm.zones))
        water_per_zone = total_water_liters / zone_count
        n_per_zone = total_nitrogen_kg / zone_count

        zone_reports: List[ZoneCarbonFootprint] = []
        total_kwh = 0.0
        scope1_tot = 0.0
        scope2_tot = 0.0
        sequestration_tot = 0.0

        for zone in farm.zones:
            zr = self.calculate_zone_emissions(
                zone=zone,
                water_liters_used=water_per_zone,
                nitrogen_applied_kg=n_per_zone,
                elapsed_days=elapsed_days
            )
            zone_reports.append(zr)
            total_kwh += zr.electricity_kwh
            scope1_tot += zr.fertilizer_emissions_kg_co2e
            scope2_tot += zr.electricity_emissions_kg_co2e
            sequestration_tot += zr.carbon_sequestration_kg_co2e

        gross_emissions = scope1_tot + scope2_tot
        net_footprint = gross_emissions - sequestration_tot
        total_area = zone_count * 25.0
        intensity = net_footprint / total_area

        # Climate classification rating
        if net_footprint <= 0.0:
            rating = "A_climate_positive"
        elif intensity < 0.01:
            rating = "B_low_carbon"
        elif intensity < 0.05:
            rating = "C_moderate"
        else:
            rating = "D_high_carbon"

        return FarmCarbonReport(
            farm_id=farm.farm_id,
            elapsed_days=elapsed_days,
            total_electricity_kwh=round(total_kwh, 2),
            scope1_emissions_kg_co2e=round(scope1_tot, 3),
            scope2_emissions_kg_co2e=round(scope2_tot, 3),
            total_gross_emissions_kg_co2e=round(gross_emissions, 3),
            total_sequestration_kg_co2e=round(sequestration_tot, 3),
            net_footprint_kg_co2e=round(net_footprint, 3),
            carbon_intensity_kg_per_m2=round(intensity, 5),
            carbon_rating=rating,
            zone_breakdowns=zone_reports
        )
