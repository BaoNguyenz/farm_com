"""
Irrigation & Hydrology Agent
Calculates Penman-Monteith Evapotranspiration, dynamic phenological Kc curves,
root-zone moisture depletion, precise volumetric water delivery commands,
and nitrate leaching / root hypoxia avoidance constraints.
"""
import time
from typing import Any

from backend.agents.base_agent import AgentOpinion, AgentRole, BaseFarmAgent, DebateVote
from backend.core.agronomy_models import calculate_fao56_et0, calculate_water_deficit
from backend.core.irrigation_hydraulics import (
    SoilTextureClass,
    UnsaturatedHydraulicsEngine,
)
from backend.core.rainwater_harvesting import RainwaterHarvestingEngine
from backend.core.soil_microbiome import SoilMicrobiomeEngine
from backend.core.solar_desalination import SolarDesalinationEngine
from backend.core.twin_state import FarmDigitalTwin
from backend.core.water_budget import WaterBudgetManager


class IrrigationAgent(BaseFarmAgent):
    """
    Hydrological & Irrigation Engineer Agent.
    Calculates dynamic FAO-56 crop water requirements ($ET_c = ET_0 \times K_c$)
    factoring in growth stage phenology, root-zone water depletion, reservoir solvency,
    soil microbiome preservation, smart rainwater harvesting, and solar RO desalination.
    """
    def __init__(
        self,
        water_budget_mgr: WaterBudgetManager | None = None,
        soil_engine: SoilMicrobiomeEngine | None = None,
        rainwater_engine: RainwaterHarvestingEngine | None = None,
        desalination_engine: SolarDesalinationEngine | None = None,
    ) -> None:
        super().__init__(
            agent_id="agent_irrigation",
            role=AgentRole.IRRIGATION.value,
            expertise_domain="hydrology"
        )
        self.water_budget_mgr = water_budget_mgr
        self.soil_engine = soil_engine or SoilMicrobiomeEngine()
        self.rainwater_engine = rainwater_engine or RainwaterHarvestingEngine()
        self.desalination_engine = desalination_engine or SolarDesalinationEngine()

    def _get_dynamic_kc(self, crop: str, stage: str) -> float:
        """Determines FAO-56 crop coefficient by species and phenological phase."""
        is_strawberry = "straw" in crop.lower()
        if stage == "flowering":
            return 1.15 if is_strawberry else 1.05
        elif stage == "fruiting":
            return 1.10 if is_strawberry else 0.95
        elif stage == "vegetative":
            return 0.75 if is_strawberry else 0.70
        elif stage == "harvest_ready":
            return 0.50
        return 0.40  # seedling

    async def evaluate(self, farm: FarmDigitalTwin) -> AgentOpinion:
        w = farm.current_weather
        et0 = calculate_fao56_et0(
            temp_c=w.temp_c,
            humidity_percent=w.humidity_percent,
            wind_speed_2m_ms=w.wind_speed_ms,
            solar_radiation_mj_m2_day=w.solar_radiation_mj,
        )

        parched_zones: list[dict[str, Any]] = []
        total_irrigation_needed_mm = 0.0
        total_volume_liters = 0.0
        emergency_wilting = False

        # Soil microbiome & leaching audit
        soil_report = self.soil_engine.audit_farm(farm)
        zone_audit_map = {za.zone_id: za for za in soil_report.zone_audits}

        for zone in farm.zones:
            kc = self._get_dynamic_kc(zone.crop_type, zone.growth_stage)
            deficit = calculate_water_deficit(
                et0=et0,
                kc=kc,
                precipitation_mm=w.precipitation_mm,
                soil_moisture_pct=zone.soil_moisture_pct
            )

            # Check soil leaching vulnerability
            za = zone_audit_map.get(zone.id)
            is_hypoxic = za.root_hypoxia_index > 0.3 if za else False
            is_leaching_critical = za.leaching_risk_tier == "critical_leaching" if za else False

            # Suppress irrigation recommendation if zone is already at or above field capacity
            if deficit["needs_watering"] and not is_hypoxic and not is_leaching_critical:
                needed_mm = deficit["recommended_irrigation_mm"]
                # 25 m2 per plot: 1mm = 25 Liters
                volume_l = round(needed_mm * 25.0, 1)

                is_critical = zone.soil_moisture_pct < 35.0
                if is_critical:
                    emergency_wilting = True

                parched_zones.append({
                    "zone_id": zone.id,
                    "crop": zone.crop_type,
                    "stage": zone.growth_stage,
                    "kc": kc,
                    "moisture": zone.soil_moisture_pct,
                    "needed_mm": needed_mm,
                    "volume_liters": volume_l,
                    "emergency": is_critical,
                    "leaching_tier": za.leaching_risk_tier if za else "minimal"
                })
                total_irrigation_needed_mm += needed_mm
                total_volume_liters += volume_l

        # Hydrological budget integration
        water_budget_data: dict[str, Any] | None = None
        if self.water_budget_mgr:
            rep = self.water_budget_mgr.get_budget_report()
            water_budget_data = rep.model_dump()
            if rep.rationing_tier in ("moderate_deficit", "severe_drought", "critical_empty") and not emergency_wilting:
                factor = 0.7 if rep.rationing_tier == "moderate_deficit" else (0.4 if rep.rationing_tier == "severe_drought" else 0.0)
                total_volume_liters = round(total_volume_liters * factor, 1)

        # Smart Rainwater Harvesting & Solar RO resilience audit
        rainwater_summary = self.rainwater_engine.get_system_summary()
        salinity_hazard = self.desalination_engine.assess_crop_salinity_hazard(
            raw_tds_ppm=200.0 if w.precipitation_mm > 5.0 else 1450.0,
            crop_type="Strawberries",
        )

        urgency = "low"
        if emergency_wilting:
            urgency = "critical"
        elif len(parched_zones) > 0 or salinity_hazard["salinity_exceeded"]:
            urgency = "medium"

        reasoning = (
            f"Daily ET0 is {et0:.2f} mm/day under current {w.temp_c}°C / {w.humidity_percent}% RH. "
            f"{len(parched_zones)} zones are beneath optimal moisture threshold (70%). "
            f"Total volume demand: {total_volume_liters:,.0f} L across the farm. "
            f"Soil Health Index: {soil_report.average_soil_health_index:.1f}/100 "
            f"({soil_report.zones_with_hypoxia_risk_count} zones hypoxic, "
            f"{soil_report.zones_with_leaching_risk_count} leaching risks). "
            f"Rainwater cistern: {rainwater_summary['current_storage_liters']:,.0f} L ({rainwater_summary['fill_percentage']}%). "
        )
        if salinity_hazard["salinity_exceeded"]:
            reasoning += f"Salinity hazard: {salinity_hazard['raw_tds_ppm']} ppm TDS (Solar RO required). "
        if water_budget_data:
            reasoning += f" Reservoir storage: {water_budget_data['storage_percentage']}% (Tier: {water_budget_data['rationing_tier']}, Autonomy: {water_budget_data['days_of_autonomy']} days)."

        if emergency_wilting:
            critical_targets = [pz["zone_id"] for pz in parched_zones if pz["emergency"]]
            rec = f"EMERGENCY: Immediate drip irrigation required for wilted zones: {', '.join(critical_targets)}."
        elif salinity_hazard["salinity_exceeded"] and rainwater_summary["current_storage_liters"] < 1000.0:
            rec = "Salinity hazard detected in well water: Activate Solar RO Desalination to supply low-EC permeate."
        elif parched_zones:
            targets_str = ", ".join([f"{pz['zone_id']} ({pz['needed_mm']}mm)" for pz in parched_zones[:4]])
            rec = f"Execute drip irrigation cycles for: {targets_str} (Total: {total_volume_liters:,.0f} L)."
        elif soil_report.zones_with_hypoxia_risk_count > 0:
            rec = "Hold all irrigation: Root zone hypoxia detected. Allow drainage and soil microbial aeration."
        else:
            rec = "Soil moisture reserves sufficient; hold irrigation valves closed."

        data_points: dict[str, Any] = {
            "et0_mm": et0,
            "parched_zones_count": len(parched_zones),
            "total_water_volume_mm": round(total_irrigation_needed_mm, 1),
            "total_water_liters": total_volume_liters,
            "zones": parched_zones,
            "emergency_wilting": emergency_wilting,
            "soil_health_report": soil_report.model_dump(),
            "rainwater_harvesting": rainwater_summary,
            "salinity_hazard": salinity_hazard,
        }
        if water_budget_data:
            data_points["water_budget"] = water_budget_data

        return AgentOpinion(
            agent_id=self.agent_id,
            role=self.role,
            confidence=0.95,
            recommendation=rec,
            urgency=urgency,
            data_points=data_points,
            reasoning=reasoning,
            timestamp=time.time()
        )

    def vote_on_proposal(self, proposal: dict[str, Any], context: dict[str, Any]) -> DebateVote:
        domain = proposal.get("action_domain", "general")
        weight = self.get_domain_weight(domain)
        urgency = proposal.get("urgency", "low")
        action_type = proposal.get("action_type", "").lower()

        # Soil saturation and nitrogen leaching veto
        is_water_action = any(k in action_type for k in ("irrigat", "pump", "water"))
        zone_moisture = context.get("target_soil_moisture_pct", 0.0)
        leaching_tier = context.get("leaching_risk_tier", "minimal")

        if is_water_action and urgency != "critical" and (zone_moisture >= 80.0 or leaching_tier == "critical_leaching"):
            return DebateVote(
                agent_id=self.agent_id,
                topic=domain,
                vote_choice="REJECT",
                weight=max(weight, 3.0),
                confidence=0.95,
                rationale=(
                    f"LEACHING & ROOT HYPOXIA VETO: Zone moisture at {zone_moisture:.1f}% "
                    f"(Tier: {leaching_tier}). Additional water percolation causes nitrate "
                    "leaching and microbial root suffocation."
                ),
            )

        # Water budget constraint check during debate
        if self.water_budget_mgr and is_water_action:
            rep = self.water_budget_mgr.get_budget_report()
            if rep.rationing_tier == "critical_empty" and urgency != "critical":
                return DebateVote(
                    agent_id=self.agent_id,
                    topic=domain,
                    vote_choice="REJECT",
                    weight=weight,
                    confidence=0.92,
                    rationale=f"VETO: Reservoir critically empty ({rep.storage_percentage}%). Non-emergency watering prohibited."
                )
            if rep.daily_quota_remaining_liters <= 0.0 and urgency != "critical":
                return DebateVote(
                    agent_id=self.agent_id,
                    topic=domain,
                    vote_choice="DEFER",
                    weight=weight,
                    confidence=0.85,
                    rationale="DEFER: Daily water extraction quota exhausted (15,000 L/day). Reschedule to next solar cycle."
                )

        # Salinity hazard veto on salt-sensitive crops
        raw_tds = context.get("water_tds_ppm", 0.0)
        crop_target = context.get("crop_type", "")
        if is_water_action and raw_tds > 750.0 and crop_target in ("Strawberries", "Bell Pepper") and not context.get("ro_desalinated", False):
            return DebateVote(
                agent_id=self.agent_id,
                topic="salinity_management",
                vote_choice="REJECT",
                weight=max(weight, 3.2),
                confidence=0.96,
                rationale=(
                    f"SALINITY VETO: Raw water TDS is {raw_tds:.0f} ppm. Direct application on {crop_target} "
                    "will cause osmotic root burning and yield penalty. Activate Solar RO Desalination first."
                ),
            )

        # Endorse rainwater harvesting & solar RO desalination
        if any(k in action_type for k in ("rainwater", "harvest_runoff", "desalination", "ro_membrane")):
            return DebateVote(
                agent_id=self.agent_id,
                topic="water_resilience",
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.95,
                rationale="Irrigation engineer strongly endorses rainwater harvesting and solar RO membrane desalination for sustainable zero-salinity irrigation.",
            )

        # Subsurface drip irrigation & precision fertigation validation
        if any(k in action_type for k in ("subsurface_drip", "sdi_fertigation", "drip_emitter")):
            measured_ec = context.get("measured_ec", 1.8)
            if measured_ec > 2.8:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="fertigation_safety",
                    vote_choice="REJECT",
                    weight=max(weight, 3.5),
                    confidence=0.96,
                    rationale=f"FERTIGATION SALINITY VETO: Injected EC ({measured_ec:.2f} mS/cm) exceeds 2.8 mS/cm threshold. High risk of osmotic root tip scorch.",
                )
            return DebateVote(
                agent_id=self.agent_id,
                topic="subsurface_hydraulics",
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.94,
                rationale="Irrigation engineer approves subsurface drip fertigation: zero canopy wetting, 35% lower evaporation, and targeted root-zone wetting.",
            )

        return DebateVote(
            agent_id=self.agent_id,
            topic=domain,
            vote_choice="APPROVE",
            weight=weight,
            confidence=0.9 if weight >= 2.0 else 0.8,
            rationale=f"{self.role} approves proposal in domain '{domain}' (urgency: {urgency})."
        )

    def audit_subsurface_matric_tension(
        self,
        zone_id: str,
        volumetric_moisture: float,
        soil_type: SoilTextureClass = SoilTextureClass.LOAM,
    ) -> dict[str, Any]:
        """Audits vadose zone matric suction pressure and wetted bulb retention."""
        engine = UnsaturatedHydraulicsEngine(soil_type)
        suction_kpa = engine.matric_suction_from_water_content(volumetric_moisture)
        se = engine.compute_effective_saturation(volumetric_moisture)
        k_unsat = engine.unsaturated_hydraulic_conductivity(volumetric_moisture)

        # Stress categorization based on matric suction:
        # < 10 kPa: near saturation / hypoxia risk
        # 10 - 35 kPa: optimal comfort zone (field capacity)
        # 35 - 70 kPa: mild moisture depletion (prompt pulse drip)
        # > 70 kPa: critical water stress
        if suction_kpa < 8.0:
            status = "hypoxic_saturated"
        elif suction_kpa <= 35.0:
            status = "optimal_moisture"
        elif suction_kpa <= 70.0:
            status = "mild_depletion"
        else:
            status = "critical_suction_stress"

        return {
            "zone_id": zone_id,
            "soil_type": soil_type.value,
            "volumetric_moisture": round(volumetric_moisture, 3),
            "effective_saturation": round(se, 3),
            "matric_suction_kpa": suction_kpa,
            "unsaturated_conductivity_cm_h": k_unsat,
            "status": status,
            "recommended_pulse_minutes": 25 if status == "mild_depletion" else (45 if status == "critical_suction_stress" else 0),
        }
