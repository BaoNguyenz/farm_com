"""
Agronomist (Plant Doctor) Agent
Analyzes NDVI/NDWI satellite indices and canopy status to identify diseased, stressed, or low-vigor crops.
"""
from typing import List
from backend.agents.base_agent import BaseFarmAgent, AgentOpinion, AgentRole
from backend.core.twin_state import FarmDigitalTwin
import time


class AgronomistAgent(BaseFarmAgent):
    """
    Chief Agronomist & Plant Doctor Agent.
    Evaluates canopy spectral indices, chlorophyll adequacy, and microclimate
    humidity-temperature vectors to detect fungal outbreak hazards.
    """
    def __init__(self):
        super().__init__(
            agent_id="agent_agronomist",
            role=AgentRole.AGRONOMIST.value,
            expertise_domain="agronomy"
        )

    async def evaluate(self, farm: FarmDigitalTwin) -> AgentOpinion:
        w = farm.current_weather
        stressed_zones: List[str] = []
        low_biomass_zones: List[str] = []
        fungal_hazard_zones: List[str] = []

        # Fungal sporulation index: high relative humidity (>80%) + temperate climate (16-26°C)
        is_fungal_weather = (w.humidity_percent >= 80.0 and 16.0 <= w.temp_c <= 28.0)

        for zone in farm.zones:
            # Chlorosis & low vegetative vigor
            if zone.ndvi < 0.45:
                low_biomass_zones.append(f"{zone.id} ({zone.crop_type}, NDVI: {zone.ndvi})")
            elif zone.ndwi < 0.12 or zone.health_status == "water_stressed":
                stressed_zones.append(f"{zone.id} ({zone.crop_type}, NDWI: {zone.ndwi})")

            # Fungal vulnerability
            if is_fungal_weather and zone.soil_moisture_pct > 80.0:
                fungal_hazard_zones.append(f"{zone.id} ({zone.crop_type})")

        urgency = "low"
        if len(fungal_hazard_zones) >= 2 or len(low_biomass_zones) >= 2:
            urgency = "critical"
        elif len(low_biomass_zones) > 0 or len(stressed_zones) > 0 or len(fungal_hazard_zones) > 0:
            urgency = "medium"

        reasoning = (
            f"Agronomic survey completed across {len(farm.zones)} plot zones. "
            f"Weather vector: {w.temp_c}°C, {w.humidity_percent}% RH. "
        )
        if fungal_hazard_zones:
            reasoning += f"High fungal outbreak risk in saturated zones: {', '.join(fungal_hazard_zones)}. "
        if low_biomass_zones:
            reasoning += f"Nitrogen chlorosis / low biomass observed in: {', '.join(low_biomass_zones)}. "

        if urgency == "critical":
            rec = f"EMERGENCY: Apply preventive bio-fungicide to {', '.join(fungal_hazard_zones)} and schedule foliar nutrition."
        elif urgency == "medium":
            rec = "Schedule soil pathogen inspection & foliar nitrogen spray for targeted zones."
        else:
            rec = "Canopy biophysical health optimal across all plot zones."

        return AgentOpinion(
            agent_id=self.agent_id,
            role=self.role,
            confidence=0.94,
            recommendation=rec,
            urgency=urgency,
            data_points={
                "stressed_count": len(stressed_zones),
                "low_biomass_count": len(low_biomass_zones),
                "fungal_risk_count": len(fungal_hazard_zones),
                "target_zones": stressed_zones + low_biomass_zones,
                "fungal_hazard_zones": fungal_hazard_zones,
                "ambient_rh_pct": w.humidity_percent
            },
            reasoning=reasoning,
            timestamp=time.time()
        )
