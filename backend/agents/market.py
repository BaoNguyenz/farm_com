"""
Market & Economic Analyst Agent
Evaluates crop harvest maturity (GDD), current spot prices, electricity tariff windows,
and trade-offs of immediate vs. deferred farm operations.
"""
from backend.agents.base_agent import BaseFarmAgent, AgentOpinion
from backend.core.twin_state import FarmDigitalTwin
import time

class MarketAgent(BaseFarmAgent):
    def __init__(self):
        super().__init__(agent_id="agent_market", role="Agricultural Economics & Market Strategist")

    async def evaluate(self, farm: FarmDigitalTwin) -> AgentOpinion:
        # Mock crop prices (VND/kg or USD/kg)
        market_rates = {
            "Strawberries": {"current": 180000, "trend": "+12%", "status": "peak_demand"},
            "Arabica Coffee": {"current": 95000, "trend": "+3%", "status": "stable"},
            "Bell Pepper": {"current": 35000, "trend": "-5%", "status": "slight_oversupply"},
            "Hydrangea": {"current": 120000, "trend": "+8%", "status": "high_demand"}
        }
        
        harvest_ready = []
        for zone in farm.zones:
            if zone.growth_stage in ["harvest_ready", "fruiting"] and zone.accumulated_gdd > 300.0:
                harvest_ready.append(zone.id)

        rec = "Current off-peak electricity window active (favorable for pump operation). "
        if harvest_ready:
            rec += f"Strawberry wholesale price is surging (+12%); prioritize harvest readiness in zones: {', '.join(harvest_ready)}."
        else:
            rec += "Maintain standard vegetative growth regime."

        return AgentOpinion(
            agent_id=self.agent_id,
            role=self.role,
            confidence=0.88,
            recommendation=rec,
            urgency="low",
            data_points={
                "electricity_tariff": "off-peak",
                "harvest_candidates": harvest_ready,
                "spot_prices": market_rates
            },
            reasoning="Wholesale commodity prices in Lam Dong market indicate premium margins on Grade-A Strawberries and Hydrangeas.",
            timestamp=time.time()
        )
