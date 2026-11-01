"""
Agronomist (Plant Doctor) Agent
Analyzes NDVI/NDWI satellite indices and canopy status to identify diseased, stressed, or low-vigor crops.
"""
from typing import List, Dict, Any
from backend.agents.base_agent import BaseFarmAgent, AgentOpinion, AgentRole, DebateVote
from backend.core.twin_state import FarmDigitalTwin
from backend.core.heat_stress import CanopyHeatStressController
from backend.core.fertigation import FertigationOptimizer
import time


class AgronomistAgent(BaseFarmAgent):
    """
    Chief Agronomist & Plant Doctor Agent.
    Evaluates canopy spectral indices, chlorophyll adequacy, microclimate
    humidity-temperature vectors for fungal sporulation, and heat stress dynamics.
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

        # Heat stress & thermal kinetics
        heat_assessment = CanopyHeatStressController.evaluate_thermal_stress(
            air_temp_c=w.temp_c,
            humidity_percent=w.humidity_percent,
            solar_radiation_mj=w.solar_radiation_mj
        )

        # Fertigation optimization
        fert_recipes = FertigationOptimizer.batch_optimize_farm(farm)

        urgency = "low"
        if len(fungal_hazard_zones) >= 2 or len(low_biomass_zones) >= 2 or heat_assessment.alert_level == "extreme_thermal_shock":
            urgency = "critical"
        elif len(low_biomass_zones) > 0 or len(stressed_zones) > 0 or len(fungal_hazard_zones) > 0 or heat_assessment.fogging_required:
            urgency = "medium"

        reasoning = (
            f"Agronomic survey completed across {len(farm.zones)} plot zones. "
            f"Weather vector: {w.temp_c}°C, {w.humidity_percent}% RH. "
        )
        if fungal_hazard_zones:
            reasoning += f"High fungal outbreak risk in saturated zones: {', '.join(fungal_hazard_zones)}. "
        if low_biomass_zones:
            reasoning += f"Nitrogen chlorosis / low biomass observed in: {', '.join(low_biomass_zones)}. "
        if heat_assessment.fogging_required:
            reasoning += f"Canopy heat stress: {heat_assessment.action_summary} "

        if heat_assessment.alert_level == "extreme_thermal_shock":
            rec = f"EMERGENCY: Extreme thermal shock detected ({w.temp_c}°C, VPD {heat_assessment.vpd_kpa} kPa). Immediate evaporative fogging required."
        elif urgency == "critical":
            rec = f"EMERGENCY: Apply preventive bio-fungicide to {', '.join(fungal_hazard_zones)} and schedule foliar nutrition."
        elif heat_assessment.fogging_required:
            rec = f"Canopy heat stress ({heat_assessment.alert_level}): Activate {heat_assessment.pulse_duration_seconds}s micro-fogging pulse."
        elif urgency == "medium":
            rec = "Schedule soil pathogen inspection & foliar nitrogen spray for targeted zones."
        else:
            rec = "Canopy biophysical health optimal across all plot zones."

        data_points: Dict[str, Any] = {
            "stressed_count": len(stressed_zones),
            "low_biomass_count": len(low_biomass_zones),
            "fungal_risk_count": len(fungal_hazard_zones),
            "target_zones": stressed_zones + low_biomass_zones,
            "fungal_hazard_zones": fungal_hazard_zones,
            "ambient_rh_pct": w.humidity_percent,
            "heat_stress": heat_assessment.model_dump(),
            "fertigation_recipes_count": len(fert_recipes)
        }

        return AgentOpinion(
            agent_id=self.agent_id,
            role=self.role,
            confidence=0.94,
            recommendation=rec,
            urgency=urgency,
            data_points=data_points,
            reasoning=reasoning,
            timestamp=time.time()
        )

    def vote_on_proposal(self, proposal: Dict[str, Any], context: Dict[str, Any]) -> DebateVote:
        domain = proposal.get("action_domain", "general")
        weight = self.get_domain_weight(domain)
        urgency = proposal.get("urgency", "low")

        action_type = proposal.get("action_type", "").lower()

        # Veto irrigation if soil pathogen risk is severe and soil is saturated
        if any(k in action_type for k in ("irrigat", "pump", "water")):
            weather = context.get("weather", {})
            rh = weather.get("humidity_percent", 50.0)
            if rh >= 85.0 and urgency != "critical":
                return DebateVote(
                    agent_id=self.agent_id,
                    topic=domain,
                    vote_choice="REJECT",
                    weight=weight,
                    confidence=0.95,
                    rationale=f"PATHOLOGY VETO: Ambient relative humidity is {rh:.1f}%. Excess watering will provoke Phytophthora root rot."
                )

        # Evaporative cooling approval
        if "fogging" in action_type or "cooling" in action_type:
            return DebateVote(
                agent_id=self.agent_id,
                topic=domain,
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.95,
                rationale="Agronomist approves evaporative fogging to restore optimal leaf transpiration."
            )

        return DebateVote(
            agent_id=self.agent_id,
            topic=domain,
            vote_choice="APPROVE",
            weight=weight,
            confidence=0.9 if weight >= 2.0 else 0.8,
            rationale=f"{self.role} approves proposal in domain '{domain}' (urgency: {urgency})."
        )
