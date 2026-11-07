"""
Biophysical Crop Yield Forecasting, Monte Carlo Simulation & Harvest Logistics Engine.

Implements FAO 33 / FAO 66 Water Production Function combined with Thermal Growing Degree Day (GDD)
phenological development and Monte Carlo stochastic uncertainty modeling.
"""

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import numpy as np
from pydantic import BaseModel, Field

from backend.core.twin_state import FarmDigitalTwin, PlotZone


class CropPhenologyBenchmark(BaseModel):
    """Agronomic benchmarks per crop cultivar."""
    crop_name: str
    base_temp_c: float = Field(10.0, description="Base physiological threshold temperature")
    target_maturity_gdd: float = Field(600.0, description="Cumulative GDD required to reach full harvest maturity")
    potential_yield_kg_per_m2: float = Field(4.5, description="Theoretical maximum yield under zero water/nutrient stress")
    yield_response_factor_ky: float = Field(1.05, description="FAO Ky factor relating relative ET deficit to yield reduction")
    picking_rate_kg_per_hour: float = Field(18.0, description="Standard manual or robotic harvest rate per worker-hour")


class MonteCarloYieldMetrics(BaseModel):
    """Percentile confidence intervals from stochastic simulation runs."""
    p10_pessimistic_t_ha: float = Field(..., description="10th percentile yield forecast (tons/ha)")
    p50_median_t_ha: float = Field(..., description="50th percentile median yield forecast (tons/ha)")
    p90_optimistic_t_ha: float = Field(..., description="90th percentile yield forecast (tons/ha)")
    yield_risk_coefficient_pct: float = Field(..., description="Coefficient of variation (std / mean * 100%)")


class ZoneYieldForecast(BaseModel):
    """Fine-grained harvest yield projection for a single plot zone."""
    zone_id: str
    crop_type: str
    accumulated_gdd: float
    target_gdd: float
    maturity_percentage: float
    estimated_days_to_harvest: int
    projected_harvest_date: str
    expected_yield_kg: float
    expected_yield_t_ha: float
    water_stress_penalty_pct: float
    monte_carlo_metrics: MonteCarloYieldMetrics


class HarvestLogisticsPlan(BaseModel):
    """Resource provisioning and cold-chain logistics schedule."""
    total_expected_yield_kg: float
    total_crates_needed: int
    crate_weight_capacity_kg: float = 15.0
    labor_worker_shifts_needed: int
    cold_storage_volume_m3: float
    post_harvest_precooling_load_kwh: float
    earliest_harvest_date: str
    latest_harvest_date: str


class FarmYieldHarvestReport(BaseModel):
    """Consolidated enterprise farm harvest advisory and logistics roadmap."""
    farm_id: str
    generated_at_utc: str
    total_farm_expected_yield_tons: float
    average_maturity_pct: float
    zone_forecasts: list[ZoneYieldForecast]
    logistics_plan: HarvestLogisticsPlan


class YieldPredictionEngine:
    """
    Simulates crop development curves, evapotranspiration water-stress penalties,
    and Monte Carlo harvest projections.
    """

    CROP_BENCHMARKS: ClassVar[dict[str, CropPhenologyBenchmark]] = {
        "Strawberries": CropPhenologyBenchmark(
            crop_name="Strawberries",
            base_temp_c=10.0,
            target_maturity_gdd=550.0,
            potential_yield_kg_per_m2=3.8,
            yield_response_factor_ky=1.05,
            picking_rate_kg_per_hour=16.0,
        ),
        "Bell Peppers": CropPhenologyBenchmark(
            crop_name="Bell Peppers",
            base_temp_c=12.0,
            target_maturity_gdd=800.0,
            potential_yield_kg_per_m2=5.2,
            yield_response_factor_ky=1.15,
            picking_rate_kg_per_hour=24.0,
        ),
        "Tomatoes": CropPhenologyBenchmark(
            crop_name="Tomatoes",
            base_temp_c=10.0,
            target_maturity_gdd=750.0,
            potential_yield_kg_per_m2=6.5,
            yield_response_factor_ky=1.00,
            picking_rate_kg_per_hour=28.0,
        ),
    }

    DEFAULT_BENCHMARK: ClassVar[CropPhenologyBenchmark] = CropPhenologyBenchmark(
        crop_name="Generic Crop",
        base_temp_c=10.0,
        target_maturity_gdd=650.0,
        potential_yield_kg_per_m2=4.0,
        yield_response_factor_ky=1.00,
        picking_rate_kg_per_hour=20.0,
    )

    def get_benchmark(self, crop_type: str) -> CropPhenologyBenchmark:
        """Fetch crop benchmark parameters or default."""
        return self.CROP_BENCHMARKS.get(crop_type, self.DEFAULT_BENCHMARK)

    def forecast_zone(
        self,
        zone: PlotZone,
        avg_daily_temp_c: float = 22.0,
        zone_area_m2: float = 25.0,
        simulation_runs: int = 250,
        seed: int = 42,
    ) -> ZoneYieldForecast:
        """
        Compute biophysical yield and run Monte Carlo simulation for a plot zone.
        """
        benchmark = self.get_benchmark(zone.crop_type)

        # Phenological maturity calculation
        maturity_pct = min(100.0, round((zone.accumulated_gdd / benchmark.target_maturity_gdd) * 100.0, 1))
        remaining_gdd = max(0.0, benchmark.target_maturity_gdd - zone.accumulated_gdd)

        daily_gdd = max(0.0, avg_daily_temp_c - benchmark.base_temp_c)
        effective_daily_gdd = max(1.0, daily_gdd)
        days_to_harvest = int(np.ceil(remaining_gdd / effective_daily_gdd))

        harvest_date = datetime.now(UTC) + timedelta(days=days_to_harvest)
        harvest_date_str = harvest_date.strftime("%Y-%m-%d")

        # FAO 33 Water Production Function: 1 - Ya/Ym = Ky * (1 - ETa/ETc)
        # We proxy ETa/ETc from soil moisture pct (optimal ~65%) and ndwi
        moisture_ratio = min(1.0, max(0.2, zone.soil_moisture_pct / 65.0))
        et_ratio = min(1.0, max(0.3, (moisture_ratio * 0.7) + (min(1.0, zone.ndwi / 0.35) * 0.3)))
        et_deficit = max(0.0, 1.0 - et_ratio)

        yield_reduction_fraction = min(0.85, benchmark.yield_response_factor_ky * et_deficit)
        actual_yield_kg_m2 = benchmark.potential_yield_kg_per_m2 * (1.0 - yield_reduction_fraction)

        # Health status and vigor modifier
        if zone.health_status == "diseased":
            actual_yield_kg_m2 *= 0.75
        elif zone.health_status == "optimal":
            actual_yield_kg_m2 *= 1.05

        expected_kg = round(actual_yield_kg_m2 * zone_area_m2, 2)
        # 1 kg / m2 = 10 metric tons / hectare
        expected_t_ha = round(actual_yield_kg_m2 * 10.0, 2)

        # Monte Carlo stochastic simulation over remaining days
        rng = np.random.default_rng(seed)
        noise = rng.normal(loc=0.0, scale=0.08, size=simulation_runs)
        simulated_yields = np.clip(expected_t_ha * (1.0 + noise), a_min=expected_t_ha * 0.4, a_max=expected_t_ha * 1.5)

        p10 = float(np.percentile(simulated_yields, 10))
        p50 = float(np.percentile(simulated_yields, 50))
        p90 = float(np.percentile(simulated_yields, 90))
        cv_pct = float((np.std(simulated_yields) / (np.mean(simulated_yields) + 1e-6)) * 100.0)

        mc_metrics = MonteCarloYieldMetrics(
            p10_pessimistic_t_ha=round(p10, 2),
            p50_median_t_ha=round(p50, 2),
            p90_optimistic_t_ha=round(p90, 2),
            yield_risk_coefficient_pct=round(cv_pct, 2),
        )

        return ZoneYieldForecast(
            zone_id=zone.id,
            crop_type=zone.crop_type,
            accumulated_gdd=round(zone.accumulated_gdd, 1),
            target_gdd=benchmark.target_maturity_gdd,
            maturity_percentage=maturity_pct,
            estimated_days_to_harvest=days_to_harvest,
            projected_harvest_date=harvest_date_str,
            expected_yield_kg=expected_kg,
            expected_yield_t_ha=expected_t_ha,
            water_stress_penalty_pct=round(yield_reduction_fraction * 100.0, 1),
            monte_carlo_metrics=mc_metrics,
        )

    def forecast_farm(
        self,
        farm: FarmDigitalTwin,
        zone_area_m2: float = 25.0,
    ) -> FarmYieldHarvestReport:
        """
        Aggregate all zones into farm-level harvest forecasts and logistics roadmap.
        """
        zone_forecasts: list[ZoneYieldForecast] = []
        total_kg = 0.0
        maturity_sum = 0.0
        earliest_days = 999
        latest_days = 0

        temp_c = 22.0
        if hasattr(farm, "current_weather") and farm.current_weather is not None:
            temp_c = farm.current_weather.temp_c

        for zone in farm.zones:
            fc = self.forecast_zone(zone, avg_daily_temp_c=temp_c, zone_area_m2=zone_area_m2)
            zone_forecasts.append(fc)
            total_kg += fc.expected_yield_kg
            maturity_sum += fc.maturity_percentage
            earliest_days = min(earliest_days, fc.estimated_days_to_harvest)
            latest_days = max(latest_days, fc.estimated_days_to_harvest)

        zone_count = len(farm.zones) or 1
        avg_maturity = round(maturity_sum / zone_count, 1)

        # Logistics: 15kg crates, 8-hour worker shifts at average picking rate
        crate_capacity = 15.0
        crates_needed = int(np.ceil(total_kg / crate_capacity))

        # Average picking rate across farm: ~20 kg/hr -> 160 kg per 8hr shift
        avg_picking_rate_hr = 20.0
        total_labor_hours = total_kg / avg_picking_rate_hr
        worker_shifts = int(np.ceil(total_labor_hours / 8.0))

        # Cold storage: ~0.05 m3 per crate
        cold_storage_vol = round(crates_needed * 0.05, 2)
        # Pre-cooling energy: ~0.025 kWh per kg produce to chill from 24C to 4C
        precooling_kwh = round(total_kg * 0.025, 2)

        now = datetime.now(UTC)
        earliest_date = (now + timedelta(days=earliest_days)).strftime("%Y-%m-%d")
        latest_date = (now + timedelta(days=latest_days)).strftime("%Y-%m-%d")

        logistics = HarvestLogisticsPlan(
            total_expected_yield_kg=round(total_kg, 2),
            total_crates_needed=crates_needed,
            crate_weight_capacity_kg=crate_capacity,
            labor_worker_shifts_needed=worker_shifts,
            cold_storage_volume_m3=cold_storage_vol,
            post_harvest_precooling_load_kwh=precooling_kwh,
            earliest_harvest_date=earliest_date,
            latest_harvest_date=latest_date,
        )

        return FarmYieldHarvestReport(
            farm_id=farm.farm_id,
            generated_at_utc=now.isoformat(),
            total_farm_expected_yield_tons=round(total_kg / 1000.0, 3),
            average_maturity_pct=avg_maturity,
            zone_forecasts=zone_forecasts,
            logistics_plan=logistics,
        )
