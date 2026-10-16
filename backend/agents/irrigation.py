"""
Irrigation & Hydrology Agent
Calculates Penman-Monteith Evapotranspiration, current soil moisture deficit, and generates water delivery commands.
"""
from backend.agents.base_agent import BaseFarmAgent, AgentOpinion
from backend.core.twin_state import FarmDigitalTwin
from backend.core.agronomy_models import calculate_fao56_et0, calculate_water_deficit
import time

class IrrigationAgent(BaseFarmAgent):
    def __init__(self):
        super().__init__(agent_id="agent_irrigation", role="Hydrological & Irrigation Engineer")

    async def evaluate(self, farm: FarmDigitalTwin) -> AgentOpinion:
        w = farm.current_weather
        et0 = calculate_fao56_et0(
            temp_c=w.temp_c,
            humidity_percent=w.humidity_percent,
            wind_speed_2m_ms=w.wind_speed_ms,
            solar_radiation_mj_m2_day=w.solar_radiation_mj
        )
        
        parched_zones = []
        total_irrigation_needed = 0.0
        
        for zone in farm.zones:
            # Crop coefficient Kc benchmark (flowering strawberry ~ 1.05, coffee ~ 0.95)
            kc = 1.05 if "Straw" in zone.crop_type else 0.95
            deficit = calculate_water_deficit(
                et0=et0,
                kc=kc,
                precipitation_mm=w.precipitation_mm,
                soil_moisture_pct=zone.soil_moisture_pct
            )
            if deficit["needs_watering"]:
                parched_zones.append({
                    "zone_id": zone.id,
                    "crop": zone.crop_type,
                    "moisture": zone.soil_moisture_pct,
                    "needed_mm": deficit["recommended_irrigation_mm"]
                })
                total_irrigation_needed += deficit["recommended_irrigation_mm"]

        urgency = "low"
        if len(parched_zones) > 0:
            urgency = "medium" if any(pz["moisture"] < 40.0 for pz in parched_zones) else "low"

        reasoning = (
            f"Daily ET0 is {et0} mm/day under current {w.temp_c}°C / {w.humidity_percent}% RH. "
            f"{len(parched_zones)} zones are beneath optimal moisture threshold (70%)."
        )
        
        if parched_zones:
            targets_str = ", ".join([f"{pz['zone_id']} ({pz['needed_mm']}mm)" for pz in parched_zones])
            rec = f"Execute drip irrigation cycles for: {targets_str}."
        else:
            rec = "Soil moisture reserves sufficient; hold irrigation valves closed."

        return AgentOpinion(
            agent_id=self.agent_id,
            role=self.role,
            confidence=0.95,
            recommendation=rec,
            urgency=urgency,
            data_points={
                "et0_mm": et0,
                "parched_zones_count": len(parched_zones),
                "total_water_volume_mm": round(total_irrigation_needed, 1),
                "zones": parched_zones
            },
            reasoning=reasoning,
            timestamp=time.time()
        )
