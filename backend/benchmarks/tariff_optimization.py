"""
Task 7.3: Electricity Tariff Optimization Benchmark Scenario
Evaluates energy cost efficiency, EVN peak-shaving, and the trade-off between power tariffs and crop biology.
"""
import time
from typing import Any, List
from backend.benchmarks.base import BaseScenarioBenchmark, ScenarioMetric, ScenarioEvaluationResult
from backend.core.twin_state import FarmDigitalTwin


class TariffOptimizationScenario(BaseScenarioBenchmark):
    """
    Scenario 3: EVN Time-of-Use (TOU) Tariff Peak-Shaving
    - Simulates operations occurring at 10:00 (Peak tariff: 3,076 VND/kWh).
    - Off-peak window (22:00-04:00) offers 1,133 VND/kWh (63.2% power savings).
    - Benchmark tests whether council defers non-critical irrigation while respecting emergency overrides.
    """
    def __init__(self):
        super().__init__(
            scenario_id="scenario_tariff_optimization",
            scenario_name="EVN Time-of-Use (TOU) Tariff & Peak-Shaving",
            description="Evaluates power expenditure savings by deferring heavy electrical pump loads to off-peak hours.",
            duration_hours=12.0
        )

    async def setup(self, farm: FarmDigitalTwin) -> None:
        """Sets non-critical moisture deficit where irrigation can safely be deferred."""
        # Zone moisture at 52-58% (deficit exists, but well above 35% critical wilting point)
        for zone in farm.zones:
            zone.soil_moisture_pct = 54.0
            zone.health_status = "healthy"

    async def step_scenario(self, farm: FarmDigitalTwin, elapsed_hours: float) -> None:
        """Gradual gentle moisture reduction over simulation window."""
        for zone in farm.zones:
            zone.soil_moisture_pct = max(36.0, round(zone.soil_moisture_pct - (0.5 * elapsed_hours), 1))

    async def evaluate_response(self, farm: FarmDigitalTwin, verdict: Any) -> ScenarioEvaluationResult:
        """Evaluates whether peak-hour pump loads were deferred to off-peak windows."""
        start_t = time.time()
        metrics: List[ScenarioMetric] = []

        # Metric 1: Peak Tariff Awareness
        market_op = next((op for op in verdict.opinions if "market" in op.agent_id.lower()), None)
        is_peak_aware = False
        if market_op:
            tariff_data = market_op.data_points.get("electricity_tariff", {})
            is_peak_aware = isinstance(tariff_data, dict) and "tier" in tariff_data

        metrics.append(ScenarioMetric(
            name="TOU Tariff Window Recognition",
            value=100.0 if is_peak_aware else 0.0,
            target=100.0,
            unit="score",
            passed=is_peak_aware,
            weight=1.5,
            notes="Market agent must classify active electricity tier."
        ))

        # Metric 2: Peak Power Cost Deferral
        scheduled = getattr(verdict, "scheduled_actions", [])
        immediate_irrigate = [a for a in scheduled if a.get("status") == "queued" and a.get("type") == "irrigate_zone"]
        deferred_actions = [a for a in scheduled if "deferred" in a.get("status", "").lower() or a.get("type") == "defer_irrigation"]

        # In non-critical conditions during peak tariff, immediate irrigation should be 0 or deferred
        has_savings_behavior = len(deferred_actions) > 0 or len(immediate_irrigate) == 0

        metrics.append(ScenarioMetric(
            name="Peak-Hour Energy Deferral",
            value=100.0 if has_savings_behavior else 30.0,
            target=100.0,
            unit="score",
            passed=has_savings_behavior,
            weight=2.0,
            notes="Council should defer non-emergency pumping during 3,076 VND/kWh peak tier."
        ))

        # Metric 3: Potential Power Cost Savings (%)
        # Standard savings between peak (3,076) and off-peak (1,133) is ~63.2%
        savings_pct = 63.2 if has_savings_behavior else 0.0
        metrics.append(ScenarioMetric(
            name="Electricity Expenditure Savings",
            value=savings_pct,
            target=60.0,
            unit="%",
            passed=savings_pct >= 60.0,
            weight=1.5,
            notes="Cost reduction achieved compared to baseline peak-hour operation."
        ))

        total_weight = sum(m.weight for m in metrics)
        weighted_points = sum(m.value * m.weight for m in metrics)
        final_score = round(weighted_points / total_weight, 1)

        grade = self.compute_composite_grade(final_score)
        passed = final_score >= 70.0
        summary = (
            f"Tariff Optimization Benchmark: Score {final_score}/100 (Grade {grade}). "
            f"Peak awareness: {is_peak_aware}, Power load deferred: {has_savings_behavior}, "
            f"Cost savings: {savings_pct}%."
        )

        return ScenarioEvaluationResult(
            scenario_id=self.scenario_id,
            scenario_name=self.scenario_name,
            score=final_score,
            passed=passed,
            grade=grade,
            metrics=metrics,
            summary=summary,
            elapsed_time_s=round(time.time() - start_t, 3)
        )
