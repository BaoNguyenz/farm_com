"""
Farm Commander (Council Orchestrator) Agent
Collects multi-agent deliberations, reconciles competing priorities,
and generates definitive, actionable commands.
"""
from typing import List, Dict, Any
from backend.agents.base_agent import AgentOpinion
from backend.core.twin_state import FarmDigitalTwin, ActionLog
import time

class FarmCouncilVerdict:
    def __init__(self, opinions: List[AgentOpinion], executive_summary: str, scheduled_actions: List[Dict[str, Any]]):
        self.opinions = opinions
        self.executive_summary = executive_summary
        self.scheduled_actions = scheduled_actions
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "executive_summary": self.executive_summary,
            "opinions": [op.model_dump() for op in self.opinions],
            "scheduled_actions": self.scheduled_actions
        }

class CommanderAgent:
    def __init__(self, agronomist, irrigation, market):
        self.agronomist = agronomist
        self.irrigation = irrigation
        self.market = market

    async def convene_council(self, farm: FarmDigitalTwin) -> FarmCouncilVerdict:
        """
        Runs the full deliberation loop:
        1. Query all specialized agents
        2. Synthesize trade-offs
        3. Dispatch actions to farm digital twin
        """
        # Run agent evaluations
        op_agro = await self.agronomist.evaluate(farm)
        op_irri = await self.irrigation.evaluate(farm)
        op_mark = await self.market.evaluate(farm)
        
        opinions = [op_agro, op_irri, op_mark]
        scheduled_actions = []
        
        # Synthesize Irrigation Requirements
        parched = op_irri.data_points.get("zones", [])
        for pz in parched:
            action = {
                "type": "irrigate_zone",
                "zone_id": pz["zone_id"],
                "duration_minutes": int(pz["needed_mm"] * 3),
                "volume_mm": pz["needed_mm"],
                "status": "queued"
            }
            scheduled_actions.append(action)
            farm.action_history.append(ActionLog(
                agent_name="Commander (Consensus)",
                action_type="irrigate",
                target_zone=pz["zone_id"],
                parameters=action,
                rationale=f"Approved based on ET0 deficit ({pz['needed_mm']}mm) with support from Hydrology agent."
            ))
            
            # Apply immediate digital twin effect (recharge soil moisture)
            target = farm.get_zone(pz["zone_id"])
            if target:
                target.soil_moisture_pct = min(85.0, target.soil_moisture_pct + pz["needed_mm"] * 1.5)
                if target.health_status == "water_stressed":
                    target.health_status = "recovering"

        # Check for pathology alerts from Agronomist
        if op_agro.urgency == "critical" or op_agro.data_points.get("low_biomass_count", 0) > 0:
            scheduled_actions.append({
                "type": "deploy_drone_spectrometer",
                "target_zones": op_agro.data_points.get("target_zones", []),
                "status": "queued"
            })

        summary = (
            f"Council concluded at {time.strftime('%H:%M:%S')}. "
            f"Approved {len(scheduled_actions)} actions. "
            f"Irrigation dispatched for {len(parched)} dry zones during {op_mark.data_points.get('electricity_tariff')} electricity tariffs. "
            f"Plant health vigilance status: {op_agro.urgency.upper()}."
        )

        return FarmCouncilVerdict(
            opinions=opinions,
            executive_summary=summary,
            scheduled_actions=scheduled_actions
        )
