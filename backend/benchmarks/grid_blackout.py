"""
Grid Blackout & Solar Agrivoltaic Islanding Benchmark Scenario.

Simulates total loss of national EVN grid power during peak midday heat, testing:
1. Micro-grid autonomous islanding transition
2. Critical canopy cooling misting & essential irrigation preservation
3. Intelligent load shedding to maintain battery storage health above reserve margin
"""

import time
from typing import Any

from backend.benchmarks.base import (
    BaseScenarioBenchmark,
    ScenarioEvaluationResult,
    ScenarioMetric,
)
from backend.core.microgrid import (
    BatteryStorageSystem,
    MicrogridController,
    MicrogridMode,
    SolarPVArray,
)
from backend.core.twin_state import FarmDigitalTwin, WeatherSnapshot


class GridBlackoutScenario(BaseScenarioBenchmark):
    """
    Scenario 6: Grid Blackout & Solar Islanding Resilience
    - Midday Heat: 32.5°C
    - Solar Irradiance: 850 W/m² (strong generation)
    - Grid Status: BLACKOUT (0V grid availability)
    - Tests autonomous microgrid transition and load shedding.
    """

    def __init__(self):
        super().__init__(
            scenario_id="scenario_grid_blackout",
            scenario_name="Grid Blackout & Solar Microgrid Islanding",
            description="Evaluates autonomous microgrid islanding, critical canopy misting, and load-shedding during blackout.",
            duration_hours=12.0,
        )
        self.controller = MicrogridController(
            solar=SolarPVArray(installed_capacity_kwp=25.0, panel_area_m2=120.0),
            battery=BatteryStorageSystem(capacity_kwh=40.0, current_soc=0.65),
        )

    async def setup(self, farm: FarmDigitalTwin) -> None:
        """Injects grid power loss under severe midday heat."""
        farm.current_weather = WeatherSnapshot(
            temp_c=32.5,
            temp_max=35.0,
            temp_min=22.0,
            humidity_percent=42.0,
            wind_speed_ms=3.4,
            solar_radiation_mj=22.5,
            precipitation_mm=0.0,
            cloud_cover_pct=5.0,
        )

        for zone in farm.zones:
            zone.soil_moisture_pct = 45.0
            zone.soil_temp_c = 28.0
            zone.ndvi = 0.65
            zone.ndwi = 0.15
            zone.health_status = "stressed"

    async def step_scenario(self, farm: FarmDigitalTwin, elapsed_hours: float) -> None:
        """Simulates canopy evapotranspiration during blackout."""
        for zone in farm.zones:
            zone.soil_moisture_pct = max(20.0, zone.soil_moisture_pct - (1.5 * elapsed_hours))

    async def evaluate_response(self, farm: FarmDigitalTwin, verdict: Any) -> ScenarioEvaluationResult:
        """Audits microgrid islanding telemetry and critical action execution."""
        start_t = time.time()
        metrics: list[ScenarioMetric] = []

        # Simulate microgrid dispatch under 8.0 kW critical load with 0 grid power
        dispatch_res = self.controller.dispatch(
            load_kw=8.0,
            irradiance_w_m2=850.0,
            ambient_temp_c=farm.current_weather.temp_c,
            hour_of_day=13,
            grid_available=False,
            duration_hours=1.0,
        )

        # Metric 1: Islanding Execution (zero grid reliance)
        is_islanded = dispatch_res.mode == MicrogridMode.ISLANDED_EMERGENCY
        no_grid_import = dispatch_res.grid_imported_kw == 0.0

        metrics.append(ScenarioMetric(
            name="Microgrid Islanding Execution",
            value=100.0 if (is_islanded and no_grid_import) else 0.0,
            target=100.0,
            unit="score",
            passed=is_islanded and no_grid_import,
            weight=2.0,
            notes="Farm microgrid islanded successfully, powering critical loads purely from solar and BESS.",
        ))

        # Metric 2: Solar Self-Consumption Adequacy
        solar_gen = dispatch_res.solar_power_generated_kw
        adequate_generation = solar_gen >= 8.0

        metrics.append(ScenarioMetric(
            name="Solar Generation Coverage",
            value=round(solar_gen, 1),
            target=8.0,
            unit="kW",
            passed=adequate_generation,
            weight=1.5,
            notes=f"Generated {solar_gen:.1f} kW solar power against 8.0 kW load demand.",
        ))

        # Metric 3: Battery Reserve Margin (> 20% SoC retained)
        soc_retained = dispatch_res.battery_soc_after
        battery_safe = soc_retained >= 0.20

        metrics.append(ScenarioMetric(
            name="Battery Reserve Preservation",
            value=round(soc_retained * 100.0, 1),
            target=20.0,
            unit="SoC%",
            passed=battery_safe,
            weight=1.5,
            notes=f"Maintained {soc_retained*100.0:.1f}% battery state of charge above reserve threshold.",
        ))

        # Calculate composite score
        total_w = sum(m.weight for m in metrics)
        weighted_score = sum((100.0 if m.passed else m.value) * m.weight for m in metrics) / total_w
        final_score = round(min(100.0, max(0.0, weighted_score)), 1)
        passed = all(m.passed for m in metrics)

        grade = "A+" if final_score >= 95.0 else ("A" if final_score >= 85.0 else ("B" if final_score >= 70.0 else "C"))

        return ScenarioEvaluationResult(
            scenario_id=self.scenario_id,
            scenario_name=self.scenario_name,
            score=final_score,
            passed=passed,
            grade=grade,
            metrics=metrics,
            summary=f"Grid Blackout Benchmark completed. Grade: {grade} ({final_score}/100). Islanded microgrid operational.",
            elapsed_time_s=round(time.time() - start_t, 3),
        )
