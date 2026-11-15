"""
Greenhouse Heat Trapping and Pollination Foraging Cessation Benchmark Scenario.

Simulates extreme thermal buildup inside a closed CEA polyhouse (38°C, VPD 2.9 kPa):
1. Canopy heat stress and severe transpiration shutdown
2. Pollinator (Bombus) thermal foraging cessation (>32°C)
3. Emergency actuator dispatch (motorized ridge vents + evaporative wet pad cooling)
4. Anti-exhaust ventilation loss interlocking for CO2 enrichment
"""
import time
from typing import Any

from backend.benchmarks.base import (
    BaseScenarioBenchmark,
    ScenarioEvaluationResult,
    ScenarioMetric,
)
from backend.core.greenhouse_cea import GreenhouseCEAEngine
from backend.core.pollination import BioAcousticPollinationEngine
from backend.core.twin_state import FarmDigitalTwin, WeatherSnapshot


class GreenhouseHeatTrapScenario(BaseScenarioBenchmark):
    """
    Scenario 10: Greenhouse Heat Trapping & Pollination Foraging Cessation
    - Outside weather: 33°C, 24.5 MJ/m2 solar radiation
    - Closed polyhouse heat gain: internal temperature spikes to 38.2°C, VPD 2.9 kPa
    - Tests: microclimate regulation, cooling restoration, bumblebee foraging recovery, and CO2 interlock.
    """

    def __init__(self) -> None:
        super().__init__(
            scenario_id="scenario_greenhouse_heat_trap",
            scenario_name="Greenhouse Heat Trapping & Pollination Foraging Cessation",
            description="Evaluates automated ridge vent opening, evaporative pad-and-fan cooling, bumblebee foraging resumption, and CO2 anti-exhaust interlocking.",
            duration_hours=3.0,
        )
        self.greenhouse_engine = GreenhouseCEAEngine(greenhouse_id="GH-POLYHOUSE-01")
        self.pollination_engine = BioAcousticPollinationEngine()
        self.initial_temp_c = 38.2
        self.final_temp_c = 38.2
        self.final_vpd_kpa = 2.9
        self.co2_interlock_engaged = False
        self.foraging_resumed = False

    async def setup(self, farm: FarmDigitalTwin) -> None:
        """Injects extreme midday heat and closed-polyhouse trapped heat."""
        farm.current_weather = WeatherSnapshot(
            temp_c=33.5,
            temp_max=36.0,
            temp_min=24.0,
            humidity_percent=55.0,
            wind_speed_ms=1.2,
            solar_radiation_mj=24.5,
            precipitation_mm=0.0,
            cloud_cover_pct=10.0,
        )

        # Initially closed vents, trapped heat
        self.greenhouse_engine.actuators.roof_vent_pct = 10.0
        self.greenhouse_engine.actuators.side_curtain_pct = 5.0
        self.greenhouse_engine.actuators.pad_and_fan_active = False
        self.greenhouse_engine.actuators.co2_dosing_valve_open = True
        self.greenhouse_engine.actuators.co2_dosing_rate_kg_h = 4.5

        # Initial audit shows thermal foraging cessation
        audit = self.pollination_engine.audit_zone(
            zone_id="ZONE_GH_1",
            flower_count_per_m2=40,
            buzz_events_per_hour=140,
            ambient_temp_c=self.initial_temp_c,
        )
        self.foraging_resumed = not audit.foraging_thermal_stress

    async def step_scenario(self, farm: FarmDigitalTwin, elapsed_hours: float) -> None:
        """Executes emergency climate regulation, evaporative cooling, and anti-exhaust protection."""
        # Autonomous climate controller senses extreme heat: opens vents to 90%, activates wet pads
        microclimate = self.greenhouse_engine.regulate_microclimate(
            ambient_temp_c=farm.current_weather.temp_c if farm.current_weather else 33.5,
            ambient_humidity_pct=farm.current_weather.humidity_percent if farm.current_weather else 55.0,
            solar_radiation_mj=farm.current_weather.solar_radiation_mj if farm.current_weather else 24.5,
            target_temp_c=24.0,
        )

        self.final_temp_c = microclimate.air_temp_c
        self.final_vpd_kpa = microclimate.vpd_kpa
        # Interlock: CO2 valve must be shut off when roof vents are 90%
        self.co2_interlock_engaged = not microclimate.actuators.co2_dosing_valve_open

        # Pollination audit under regulated microclimate
        post_audit = self.pollination_engine.audit_zone(
            zone_id="ZONE_GH_1",
            flower_count_per_m2=40,
            buzz_events_per_hour=140,
            ambient_temp_c=self.final_temp_c,
        )
        self.foraging_resumed = not post_audit.foraging_thermal_stress and post_audit.visitations_per_flower >= 2.5

    async def evaluate_response(
        self,
        farm: FarmDigitalTwin,
        verdict: Any,
    ) -> ScenarioEvaluationResult:
        """Audits cooling response, VPD stabilization, pollinator resumption, and CO2 anti-exhaust interlock."""
        start_t = time.time()
        metrics: list[ScenarioMetric] = []

        # 1. Thermal Foraging Recovery (Temperature <= 28.5°C)
        cooling_passed = self.final_temp_c <= 28.5
        metrics.append(
            ScenarioMetric(
                name="Thermal Foraging Temperature Recovery",
                value=self.final_temp_c,
                target=28.5,
                unit="°C",
                passed=cooling_passed,
                description="Cools trapped greenhouse air below thermal shock threshold to allow pollinator foraging.",
            )
        )

        # 2. VPD Microclimate Stabilization (VPD <= 1.6 kPa)
        vpd_passed = self.final_vpd_kpa <= 1.6
        metrics.append(
            ScenarioMetric(
                name="Canopy VPD Stress Mitigation",
                value=self.final_vpd_kpa,
                target=1.6,
                unit="kPa",
                passed=vpd_passed,
                description="Reduces vapor pressure deficit to prevent stomatal closure and blossom desiccation.",
            )
        )

        # 3. Anti-Exhaust CO2 Loss Interlock
        metrics.append(
            ScenarioMetric(
                name="Anti-Exhaust CO2 Interlock Safety",
                value=1.0 if self.co2_interlock_engaged else 0.0,
                target=1.0,
                unit="binary",
                passed=self.co2_interlock_engaged,
                description="Safely disengages liquid CO2 injection during full ridge vent exhaust to prevent gas waste.",
            )
        )

        # 4. Bumblebee Buzz Sonication Resumption
        metrics.append(
            ScenarioMetric(
                name="Bumblebee Sonication Resumption",
                value=1.0 if self.foraging_resumed else 0.0,
                target=1.0,
                unit="binary",
                passed=self.foraging_resumed,
                description="Bumblebees actively resume sonication buzz pollination across blooming strawberry plots.",
            )
        )

        passed_count = sum(1 for m in metrics if m.passed)
        overall_score = round((passed_count / len(metrics)) * 100.0, 1)
        passed = overall_score >= 75.0
        grade = self.compute_composite_grade(overall_score)

        summary = (
            f"Greenhouse Heat Trapping Scenario completed with score {overall_score}%. "
            f"Internal temperature reduced from {self.initial_temp_c:.1f}°C to {self.final_temp_c:.1f}°C (VPD: {self.final_vpd_kpa:.2f} kPa). "
            f"CO2 interlock engaged: {self.co2_interlock_engaged}, Pollination foraging resumed: {self.foraging_resumed}."
        )

        return ScenarioEvaluationResult(
            scenario_id=self.scenario_id,
            scenario_name=self.scenario_name,
            passed=passed,
            score=overall_score,
            grade=grade,
            metrics=metrics,
            summary=summary,
            execution_time_ms=round((time.time() - start_t) * 1000.0, 2),
        )
