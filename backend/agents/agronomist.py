"""
Agronomist (Plant Doctor) Agent
Analyzes NDVI/NDWI satellite indices and canopy status to identify diseased, stressed, or low-vigor crops.
"""
from backend.agents.base_agent import BaseFarmAgent, AgentOpinion
from backend.core.twin_state import FarmDigitalTwin
import time

class AgronomistAgent(BaseFarmAgent):
    def __init__(self):
        super().__init__(agent_id="agent_agronomist", role="Chief Agronomist & Plant Doctor")

    async def evaluate(self, farm: FarmDigitalTwin) -> AgentOpinion:
        stressed_zones = []
        low_biomass_zones = []
        
        for zone in farm.zones:
            if zone.ndvi < 0.45:
                low_biomass_zones.append(f"{zone.id} ({zone.crop_type}, NDVI: {zone.ndvi})")
            elif zone.ndwi < 0.12 or zone.health_status == "water_stressed":
                stressed_zones.append(f"{zone.id} ({zone.crop_type}, NDWI: {zone.ndwi})")

        urgency = "low"
        if len(low_biomass_zones) > 0 or len(stressed_zones) > 0:
            urgency = "medium" if len(low_biomass_zones) <= 1 else "critical"

        reasoning = (
            f"Spectrometry check: {len(farm.zones)} zones surveyed. "
            f"Found {len(stressed_zones)} water-stressed and {len(low_biomass_zones)} low-chlorophyll zones. "
        )
        if low_biomass_zones:
            reasoning += f"Warning: {', '.join(low_biomass_zones)} indicates canopy breakdown or nutrient deficiency."

        rec = "Canopy indices normal across all zones."
        if low_biomass_zones or stressed_zones:
            rec = f"Schedule soil pathogen inspection for {', '.join(low_biomass_zones + stressed_zones)}."

        return AgentOpinion(
            agent_id=self.agent_id,
            role=self.role,
            confidence=0.92,
            recommendation=rec,
            urgency=urgency,
            data_points={
                "stressed_count": len(stressed_zones),
                "low_biomass_count": len(low_biomass_zones),
                "target_zones": stressed_zones + low_biomass_zones
            },
            reasoning=reasoning,
            timestamp=time.time()
        )
