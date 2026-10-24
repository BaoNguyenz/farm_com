"""
Market & Economic Analyst Agent
Evaluates crop harvest maturity (GDD), current spot prices, EVN Time-of-Use (TOU) electricity tariffs,
and optimizes operation costs (e.g., deferring heavy pump loads to off-peak hours).
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.agents.base_agent import BaseFarmAgent, AgentOpinion, AgentRole, DebateVote
from backend.core.twin_state import FarmDigitalTwin
import time


class MarketAgent(BaseFarmAgent):
    """
    Agricultural Economics & Market Strategist Agent.
    Monitors wholesale commodity market prices, EVN electricity TOU tariffs,
    and conducts cost-benefit trade-offs on energy-intensive farm operations.
    """

    # Vietnam EVN 3-Tier Time-of-Use (TOU) Schedule for Agriculture / Medium Voltage
    # Rates in VND / kWh (approximate standard tariff structure)
    TARIFF_RATES = {
        "off_peak": 1133.0,   # 22:00 -> 04:00
        "normal": 1685.0,     # 04:00 -> 09:30, 11:30 -> 17:00, 20:00 -> 22:00
        "peak": 3076.0        # 09:30 -> 11:30, 17:00 -> 20:00
    }

    # Standard wholesale prices in Lam Dong / Central Highlands (VND/kg or VND/stem)
    SPOT_PRICES = {
        "Strawberries": {"price_vnd": 180000, "unit": "kg", "trend": "+12%", "status": "high_demand", "yield_kg_m2": 1.2},
        "Arabica Coffee": {"price_vnd": 95000, "unit": "kg", "trend": "+3%", "status": "stable", "yield_kg_m2": 0.8},
        "Bell Pepper": {"price_vnd": 35000, "unit": "kg", "trend": "-5%", "status": "slight_oversupply", "yield_kg_m2": 2.5},
        "Hydrangea": {"price_vnd": 120000, "unit": "stem_bunch", "trend": "+8%", "status": "high_demand", "yield_kg_m2": 1.0}
    }

    def __init__(self):
        super().__init__(
            agent_id="agent_market",
            role=AgentRole.MARKET.value,
            expertise_domain="economics"
        )

    def get_electricity_tariff(self, hour: Optional[float] = None) -> Dict[str, Any]:
        """
        Determines active EVN TOU electricity tariff tier and rate per kWh.
        If hour is not provided, uses current local time hour.
        """
        if hour is None:
            now = datetime.now()
            hour = now.hour + now.minute / 60.0

        if (hour >= 22.0) or (hour < 4.0):
            tier = "off_peak"
        elif (9.5 <= hour < 11.5) or (17.0 <= hour < 20.0):
            tier = "peak"
        else:
            tier = "normal"

        rate = self.TARIFF_RATES[tier]
        peak_rate = self.TARIFF_RATES["peak"]
        savings_vs_peak = round(((peak_rate - rate) / peak_rate) * 100.0, 1)

        return {
            "tier": tier,
            "rate_vnd_kwh": rate,
            "hour": round(hour, 2),
            "is_peak": tier == "peak",
            "is_off_peak": tier == "off_peak",
            "savings_vs_peak_pct": savings_vs_peak
        }

    def estimate_pumping_cost(self, water_volume_liters: float, tier: str = "normal") -> Dict[str, float]:
        """
        Estimates energy required and financial cost to pump a given volume of water.
        Benchmark: 3.5 kW pump delivers 15,000 L/h => ~0.233 kWh per 1,000 Liters.
        """
        kwh_per_1000l = 0.233
        energy_kwh = (water_volume_liters / 1000.0) * kwh_per_1000l
        rate = self.TARIFF_RATES.get(tier, self.TARIFF_RATES["normal"])
        cost_vnd = energy_kwh * rate
        peak_cost_vnd = energy_kwh * self.TARIFF_RATES["peak"]
        potential_savings = max(0.0, peak_cost_vnd - cost_vnd)

        return {
            "water_volume_liters": water_volume_liters,
            "energy_kwh": round(energy_kwh, 2),
            "rate_vnd_kwh": rate,
            "cost_vnd": round(cost_vnd, 0),
            "potential_savings_vs_peak_vnd": round(potential_savings, 0)
        }

    async def evaluate(self, farm: FarmDigitalTwin) -> AgentOpinion:
        tariff_info = self.get_electricity_tariff()
        is_peak = tariff_info["is_peak"]

        harvest_candidates: List[Dict[str, Any]] = []
        total_estimated_value_vnd = 0.0

        for zone in farm.zones:
            crop_meta = self.SPOT_PRICES.get(zone.crop_type, {"price_vnd": 50000, "yield_kg_m2": 1.0, "unit": "kg"})
            if zone.growth_stage in ["harvest_ready", "fruiting"] and zone.accumulated_gdd > 300.0:
                # 25 m2 per plot
                est_yield_kg = 25.0 * crop_meta["yield_kg_m2"]
                est_val = est_yield_kg * crop_meta["price_vnd"]
                total_estimated_value_vnd += est_val

                harvest_candidates.append({
                    "zone_id": zone.id,
                    "crop": zone.crop_type,
                    "stage": zone.growth_stage,
                    "gdd": zone.accumulated_gdd,
                    "est_yield": est_yield_kg,
                    "est_value_vnd": round(est_val, 0),
                    "spot_price_vnd": crop_meta["price_vnd"]
                })

        urgency = "low"
        if is_peak:
            rec = (
                f"EVN PEAK TARIFF WINDOW ACTIVE ({tariff_info['rate_vnd_kwh']:,.0f} VND/kWh). "
                f"Defer heavy electrical pumps/lighting until off-peak window (22:00) unless critical moisture stress occurs."
            )
            urgency = "medium"
        else:
            rec = f"Electricity window favorable ({tariff_info['tier'].upper()} - {tariff_info['rate_vnd_kwh']:,.0f} VND/kWh). "

        if harvest_candidates:
            zone_ids = [hc["zone_id"] for hc in harvest_candidates]
            rec += (
                f" High spot commodity values: {len(harvest_candidates)} plots ready for market "
                f"({', '.join(zone_ids[:3])}) with gross projected yield value: {total_estimated_value_vnd:,.0f} VND."
            )

        reasoning = (
            f"Electricity pricing tier: {tariff_info['tier']} ({tariff_info['rate_vnd_kwh']:,.0f} VND/kWh). "
            f"Identified {len(harvest_candidates)} zones meeting thermal GDD maturity thresholds. "
            f"Lam Dong wholesale market premiums: Strawberries at 180,000 VND/kg (+12%), Hydrangeas at 120,000 VND."
        )

        return AgentOpinion(
            agent_id=self.agent_id,
            role=self.role,
            confidence=0.90,
            recommendation=rec,
            urgency=urgency,
            data_points={
                "electricity_tariff": tariff_info,
                "harvest_candidates": harvest_candidates,
                "projected_harvest_value_vnd": total_estimated_value_vnd,
                "spot_prices": self.SPOT_PRICES
            },
            reasoning=reasoning,
            timestamp=time.time()
        )

    def vote_on_proposal(self, proposal: Dict[str, Any], context: Dict[str, Any]) -> DebateVote:
        """
        Evaluates operational proposals from an economic lens.
        Defends operating margins by vetoing non-emergency high-power actions during peak tariff.
        """
        action_type = proposal.get("action_type", "")
        urgency = proposal.get("urgency", "low")
        tariff_tier = context.get("tariff_tier", self.get_electricity_tariff()["tier"])

        if any(k in action_type.lower() for k in ("irrigat", "pump", "water")):
            if tariff_tier == "peak" and urgency != "critical":

                return DebateVote(
                    agent_id=self.agent_id,
                    topic="irrigation_pumping",
                    vote_choice="REJECT",
                    confidence=0.88,
                    rationale=(
                        f"Current electricity tier is PEAK ({self.TARIFF_RATES['peak']:,.0f} VND/kWh). "
                        f"Irrigation is non-critical ({urgency}); deferring will save ~63% in pumping power costs."
                    )
                )

        return DebateVote(
            agent_id=self.agent_id,
            topic="farm_operation",
            vote_choice="APPROVE",
            confidence=0.85,
            rationale="Proposed action aligns with farm economic viability and energy budget constraints."
        )


