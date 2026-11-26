"""
Agronomist (Plant Doctor) Agent
Analyzes NDVI/NDWI satellite indices, canopy microclimate status, UAV multispectral scouting,
and autonomous rover mechanical weed eradication dispatching.
"""
import time
from typing import Any

from backend.agents.base_agent import AgentOpinion, AgentRole, BaseFarmAgent, DebateVote
from backend.core.agrivoltaic_shading import (
    AgrivoltaicOperationalMode,
    AgrivoltaicShadingEngine,
)
from backend.core.aquaponics_system import AquaponicEcosystemCoordinator
from backend.core.biocontrol import PredatorSpecies, PreySpecies
from backend.core.biocontrol_dispersion import MacroBiologicDispersionEngine
from backend.core.biocontrol_safety import BiocontrolSafetyEngine, SprayApplication
from backend.core.drone_scouting import DroneScoutingEngine
from backend.core.fertigation import FertigationOptimizer
from backend.core.greenhouse_cea import GreenhouseCEAEngine
from backend.core.heat_stress import CanopyHeatStressController
from backend.core.pollination import BioAcousticPollinationEngine
from backend.core.rover_fleet import RoverFleetCoordinator
from backend.core.twin_state import FarmDigitalTwin


class AgronomistAgent(BaseFarmAgent):
    """
    Chief Agronomist & Plant Doctor Agent.
    Evaluates canopy spectral indices, chlorophyll adequacy, microclimate
    humidity-temperature vectors for fungal sporulation, heat stress dynamics,
    autonomous mechanical weed eradication, greenhouse CEA climate regulation,
    and bio-acoustic pollinator buzz density.
    """
    def __init__(
        self,
        rover_coordinator: RoverFleetCoordinator | None = None,
        pollination_engine: BioAcousticPollinationEngine | None = None,
        greenhouse_engine: GreenhouseCEAEngine | None = None,
        aquaponics_coordinator: AquaponicEcosystemCoordinator | None = None,
    ) -> None:
        super().__init__(
            agent_id="agent_agronomist",
            role=AgentRole.AGRONOMIST.value,
            expertise_domain="agronomy"
        )
        self.drone_engine = DroneScoutingEngine()
        self.rover_coordinator = rover_coordinator or RoverFleetCoordinator()
        self.pollination_engine = pollination_engine or BioAcousticPollinationEngine()
        self.greenhouse_engine = greenhouse_engine or GreenhouseCEAEngine()
        self.aquaponics_coordinator = aquaponics_coordinator or AquaponicEcosystemCoordinator()

    def audit_aquaponic_water_chemistry(self, farm: FarmDigitalTwin | None = None) -> dict[str, Any]:
        """
        Monitors fish tank ammonia/DO toxicity, MBBR nitrification efficiency,
        and DWC plant bed alkalinity buffering.
        """
        telemetry = self.aquaponics_coordinator.step_simulation_cycle(feed_input_kg=0.0, dt_hours=1.0)
        alkalinity_dosing = None

        if telemetry.hydroponics.alkalinity_mg_l_caco3 < 60.0:
            rec = self.aquaponics_coordinator.dose_alkalinity_buffer(target_alkalinity_mg_l=100.0)
            alkalinity_dosing = rec.model_dump()

        return {
            "telemetry": telemetry.model_dump(),
            "ecosystem_status": telemetry.ecosystem_status.value,
            "system_health_score": telemetry.system_health_score,
            "alkalinity_dosing_action": alkalinity_dosing,
            "requires_emergency_aeration": telemetry.fish_tank.dissolved_oxygen_mg_l < 4.5,
        }

    def audit_agrivoltaic_canopy_welfare(
        self,
        canopy_temp_c: float = 32.0,
        ambient_ghi_w_m2: float = 850.0,
        crop_type: str = "Strawberries",
    ) -> dict[str, Any]:
        """
        Evaluates under-canopy photoinhibition risk and determines whether dynamic
        tracker shading is required to protect crops from sunburn.
        """
        ambient_par = ambient_ghi_w_m2 * AgrivoltaicShadingEngine.PAR_PER_W_M2
        needs_shading, reason = AgrivoltaicShadingEngine.evaluate_crop_protection_need(
            crop_type=crop_type,
            canopy_temp_c=canopy_temp_c,
            ambient_par=ambient_par,
        )

        recommended_mode = (
            AgrivoltaicOperationalMode.CROP_PROTECTIVE_SHADING
            if needs_shading
            else AgrivoltaicOperationalMode.MAX_ELECTRICITY_YIELD
        )

        return {
            "crop_type": crop_type,
            "canopy_temp_c": canopy_temp_c,
            "ambient_par_umol_m2_s": round(ambient_par, 1),
            "needs_defensive_shading": needs_shading,
            "recommended_mode": recommended_mode.value,
            "rationale": reason,
        }

    def audit_weed_infestation_and_dispatch(self, farm: FarmDigitalTwin) -> dict[str, Any]:
        """
        Scans plots for weed resurgence and schedules autonomous ground rover interventions.
        """
        infestation_plots: list[str] = []
        dispatched_missions: list[dict[str, Any]] = []

        for zone in farm.zones:
            # Weeds thrive when soil moisture is moderate (45-70%) and canopy health is stressed or has gaps
            if zone.health_status in ("weed_infested", "stressed") or (zone.ndvi < 0.55 and zone.soil_moisture_pct > 50.0):
                infestation_plots.append(zone.id)
                try:
                    mission = self.rover_coordinator.dispatch_mission(
                        plot_id=zone.id,
                        row_index=1,
                        priority="urgent_infestation"
                    )
                    dispatched_missions.append(mission.model_dump())
                except RuntimeError:
                    continue

        return {
            "infestation_plots_detected": len(infestation_plots),
            "infestation_plot_ids": infestation_plots,
            "dispatched_missions_count": len(dispatched_missions),
            "missions": dispatched_missions,
            "fleet_status": self.rover_coordinator.get_fleet_status().model_dump(),
        }

    def audit_biocontrol_safety_and_release(
        self,
        zone_id: str,
        canopy_area_m2: float,
        pest_density: float,
        target_pest: str = "spider_mite",
        beneficial_species: str = "phytoseiulus_persimilis",
        spray_history: list[dict[str, Any]] | None = None,
        use_drone: bool = True,
    ) -> dict[str, Any]:
        """
        Evaluates pesticide residue withholding safety and calculates precision
        macro-biologic release dosage for greenhouse biological pest control.
        """
        spray_records = []
        if spray_history:
            for s in spray_history:
                spray_records.append(
                    SprayApplication(
                        ingredient_name=s.get("ingredient_name", ""),
                        application_date_days_ago=float(s.get("application_date_days_ago", 0.0)),
                        initial_dose_ppm=float(s.get("initial_dose_ppm", 10.0)),
                    )
                )

        safety_report = BiocontrolSafetyEngine.evaluate_release_safety(
            spray_history=spray_records,
            target_beneficial=beneficial_species,
        )

        p_species = PredatorSpecies.PHYTOSEIULUS_PERSIMILIS
        for sp in PredatorSpecies:
            if sp.value == beneficial_species or sp.name.lower() == beneficial_species.lower():
                p_species = sp
                break

        prey_sp = PreySpecies.TWO_SPOTTED_SPIDER_MITE
        for py in PreySpecies:
            if py.value == target_pest or py.name.lower() == target_pest.lower():
                prey_sp = py
                break

        release_plan = None
        if safety_report.is_safe_to_release and pest_density > 2.0:
            plan_obj = MacroBiologicDispersionEngine.plan_zone_release(
                zone_id=zone_id,
                canopy_area_m2=canopy_area_m2,
                pest_density=pest_density,
                target_pest=prey_sp,
                beneficial_species=p_species,
                use_drone=use_drone,
            )
            release_plan = plan_obj.model_dump()

        return {
            "zone_id": zone_id,
            "safety_clearance": safety_report.model_dump(),
            "release_authorized": safety_report.is_safe_to_release and (release_plan is not None),
            "release_plan": release_plan,
        }

    def ingest_drone_survey(self, report_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Parses high-resolution UAV multispectral imagery findings and formulates
        targeted micro-application spray prescriptions.
        """
        anomalies = report_dict.get("critical_anomalies", [])
        surveys = report_dict.get("zone_surveys", [])

        prescriptions: list[dict[str, Any]] = []
        for s in surveys:
            chlorosis = s.get("chlorosis_hotspots", 0)
            weed_score = s.get("weed_pressure_score", 0.0)
            z_id = s.get("zone_id", "")

            if chlorosis >= 2:
                prescriptions.append({
                    "zone_id": z_id,
                    "action": "variable_rate_foliar_nitrogen",
                    "dosage_liters_ha": 3.5,
                    "target": "chlorotic_canopy_patches"
                })
            elif weed_score > 0.45:
                prescriptions.append({
                    "zone_id": z_id,
                    "action": "spot_organic_herbicide_micro_spray",
                    "dosage_liters_ha": 1.8,
                    "target": "inter_row_weed_clusters"
                })

        return {
            "total_anomalies_detected": len(anomalies),
            "prescriptions_generated": len(prescriptions),
            "prescriptions": prescriptions,
            "drone_mission_status": report_dict.get("status", "unknown")
        }

    async def evaluate(self, farm: FarmDigitalTwin) -> AgentOpinion:
        w = farm.current_weather
        stressed_zones: list[str] = []
        low_biomass_zones: list[str] = []
        fungal_hazard_zones: list[str] = []

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

        # UAV Drone multispectral mission analysis
        drone_report = self.drone_engine.simulate_mission(zones=farm.zones, mission_id="SCOUT-AGRO-LATEST")
        drone_findings = self.ingest_drone_survey(drone_report.model_dump())

        # Autonomous rover weed management audit
        rover_audit = self.audit_weed_infestation_and_dispatch(farm)

        # Greenhouse CEA microclimate and photosynthetic kinetics
        gh_microclimate = self.greenhouse_engine.regulate_microclimate(
            ambient_temp_c=w.temp_c,
            ambient_humidity_pct=w.humidity_percent,
            solar_radiation_mj=w.solar_radiation_mj,
        )

        # Bio-acoustic pollination assessment
        pollination_report = self.pollination_engine.audit_farm(farm)
        pollination_deficient = pollination_report.zones_requiring_supplementary_pollination > 0
        thermal_foraging_stress = any(z.foraging_thermal_stress for z in pollination_report.zone_audits)

        urgency = "low"
        if (
            len(fungal_hazard_zones) >= 2
            or len(low_biomass_zones) >= 2
            or heat_assessment.alert_level == "extreme_thermal_shock"
            or len(drone_report.critical_anomalies) >= 2
            or pollination_report.zones_requiring_supplementary_pollination >= 2
        ):
            urgency = "critical"
        elif (
            len(low_biomass_zones) > 0
            or len(stressed_zones) > 0
            or len(fungal_hazard_zones) > 0
            or heat_assessment.fogging_required
            or len(drone_report.critical_anomalies) > 0
            or rover_audit["infestation_plots_detected"] > 0
            or pollination_deficient
            or gh_microclimate.climate_status in ("heat_stress", "excessive_humidity")
        ):
            urgency = "medium"

        reasoning = (
            f"Agronomic survey completed across {len(farm.zones)} plot zones. "
            f"Weather vector: {w.temp_c}°C, {w.humidity_percent}% RH. "
            f"Drone scout detected {len(drone_report.critical_anomalies)} canopy anomalies. "
            f"Rover fleet dispatched {rover_audit['dispatched_missions_count']} autonomous mechanical weeding missions. "
            f"CEA Microclimate: {gh_microclimate.climate_status} (VPD: {gh_microclimate.vpd_kpa} kPa, CO2: {gh_microclimate.co2_concentration_ppm} ppm, Pn: {gh_microclimate.canopy_net_photosynthesis_umol_m2_s}). "
            f"Pollination: {pollination_report.average_visitations_per_flower} visits/flower ({pollination_report.zones_requiring_supplementary_pollination} zones deficient). "
        )
        if fungal_hazard_zones:
            reasoning += f"High fungal outbreak risk in saturated zones: {', '.join(fungal_hazard_zones)}. "
        if low_biomass_zones:
            reasoning += f"Nitrogen chlorosis / low biomass observed in: {', '.join(low_biomass_zones)}. "
        if heat_assessment.fogging_required:
            reasoning += f"Canopy heat stress: {heat_assessment.action_summary} "

        if heat_assessment.alert_level == "extreme_thermal_shock":
            rec = f"EMERGENCY: Extreme thermal shock detected ({w.temp_c}°C, VPD {heat_assessment.vpd_kpa} kPa). Immediate evaporative fogging required."
        elif thermal_foraging_stress:
            rec = f"POLLINATION THERMAL CESSATION ({w.temp_c}°C): Adjust ridge vents and wet pads to restore bumblebee foraging range."
        elif pollination_report.zones_requiring_supplementary_pollination >= 2:
            rec = f"POLLINATION DEFICIT: {pollination_report.zones_requiring_supplementary_pollination} blooming zones lack pollinator visitation. Deploy supplementary Bombus hive."
        elif urgency == "critical":
            rec = f"EMERGENCY: Apply preventive bio-fungicide to {', '.join(fungal_hazard_zones)} and schedule foliar nutrition."
        elif heat_assessment.fogging_required:
            rec = f"Canopy heat stress ({heat_assessment.alert_level}): Activate {heat_assessment.pulse_duration_seconds}s micro-fogging pulse."
        elif rover_audit["dispatched_missions_count"] > 0:
            rec = f"ROBOTIC FLEET: Dispatched {rover_audit['dispatched_missions_count']} mechanical weeding rovers to eradicate weeds without chemical herbicides."
        elif drone_findings["prescriptions_generated"] > 0:
            rec = f"UAV Scouting: Deploy drone targeted spray missions for {drone_findings['prescriptions_generated']} hotspot zones."
        elif pollination_deficient:
            rec = "Pollination density below target: schedule supplementary bumblebee hive release."
        elif urgency == "medium":
            rec = "Schedule soil pathogen inspection & foliar nitrogen spray for targeted zones."
        else:
            rec = "Canopy biophysical health optimal across all plot zones."

        data_points: dict[str, Any] = {
            "stressed_count": len(stressed_zones),
            "low_biomass_count": len(low_biomass_zones),
            "fungal_risk_count": len(fungal_hazard_zones),
            "target_zones": stressed_zones + low_biomass_zones,
            "fungal_hazard_zones": fungal_hazard_zones,
            "ambient_rh_pct": w.humidity_percent,
            "heat_stress": heat_assessment.model_dump(),
            "fertigation_recipes_count": len(fert_recipes),
            "drone_scouting": drone_findings,
            "rover_weed_management": rover_audit,
            "greenhouse_cea": gh_microclimate.model_dump(),
            "pollination_report": pollination_report.model_dump(),
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

    def vote_on_proposal(self, proposal: dict[str, Any], context: dict[str, Any]) -> DebateVote:
        domain = proposal.get("action_domain", "general")
        weight = self.get_domain_weight(domain)
        urgency = proposal.get("urgency", "low")

        action_type = proposal.get("action_type", "").lower()

        # Herbicide veto on VietGAP/organic certified plots
        if any(k in action_type for k in ("glyphosate", "chemical_herbicide", "paraquat")):
            return DebateVote(
                agent_id=self.agent_id,
                topic=domain,
                vote_choice="REJECT",
                weight=max(weight, 3.5),
                confidence=0.98,
                rationale=(
                    "ORGANIC INTEGRITY VETO: Chemical herbicide application strictly prohibited "
                    "under VietGAP / GlobalG.A.P. Zero-Residue MRL protocols. "
                    "Dispatch autonomous mechanical weeding rovers instead."
                ),
            )

        # Autonomous mechanical rover weeding endorsement
        if any(k in action_type for k in ("rover", "weed_punch", "mechanical_weeding", "delta_arm")):
            return DebateVote(
                agent_id=self.agent_id,
                topic=domain,
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.96,
                rationale="Agronomist strongly endorses zero-chemical autonomous mechanical weeding rover deployment."
            )

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

        # Drone precision spraying and swarm aerial survey
        if "drone" in action_type or "scout" in action_type or "spot_spray" in action_type:
            wind_speed = context.get("wind_speed_m_s", 0.0)
            rain_rate = context.get("rain_rate_mm_h", 0.0)
            if wind_speed > 12.0:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="uav_safety",
                    vote_choice="REJECT",
                    weight=max(weight, 4.0),
                    confidence=0.98,
                    rationale=f"HIGH WIND GUST VETO: Wind speed ({wind_speed:.1f} m/s > 12.0 m/s). Extreme aerodynamic instability and collision/crash hazard. Abort swarm mission.",
                )
            if rain_rate > 5.0:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="uav_safety",
                    vote_choice="REJECT",
                    weight=max(weight, 3.8),
                    confidence=0.96,
                    rationale=f"RAIN INGRESS VETO: Precipitation ({rain_rate:.1f} mm/h > 5.0 mm/h) risks sensor lens fouling and avionics short-circuit. Abort drone launch.",
                )
            return DebateVote(
                agent_id=self.agent_id,
                topic=domain,
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.96,
                rationale="Agronomist strongly endorses autonomous UAV scouting & targeted spot spray for identified canopy anomalies.",
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

        # CO2 enrichment anti-exhaust loss veto
        if "co2_injection" in action_type or "co2_dosing" in action_type:
            vents_open = context.get("roof_vent_pct", 0.0) > 50.0
            if vents_open:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic=domain,
                    vote_choice="REJECT",
                    weight=max(weight, 3.0),
                    confidence=0.96,
                    rationale="CO2 LOSS VETO: Roof vents are open >50%. Liquid CO2 dosing will vent to the atmosphere with zero photosynthetic gain.",
                )

        # Vent opening during scheduled CO2 dosing veto
        if ("open_vent" in action_type or "vent_aperture" in action_type) and context.get("co2_dosing_active", False):
            return DebateVote(
                agent_id=self.agent_id,
                topic=domain,
                vote_choice="REJECT",
                weight=weight,
                confidence=0.94,
                rationale="VENT VETO: Active CO2 enrichment scheduled. Restrict roof vents <50% to prevent gas loss.",
            )

        # Supplementary pollination endorsement
        if any(k in action_type for k in ("pollinat", "bombus", "hive", "buzz")):
            return DebateVote(
                agent_id=self.agent_id,
                topic=domain,
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.95,
                rationale="Agronomist strongly endorses supplementary bumblebee hive placement to ensure symmetrical AAA fruit set.",
            )

        # Pesticide toxicity veto when beneficials are active
        if any(k in action_type for k in ("chemical_spray", "insecticide", "pesticide_spray")) and context.get("beneficials_active", False):
            return DebateVote(
                agent_id=self.agent_id,
                topic=domain,
                vote_choice="REJECT",
                weight=max(weight, 3.5),
                confidence=0.98,
                rationale="PESTICIDE TOXICITY VETO: Active beneficial macro-biologics (Phytoseiulus/Encarsia) established in canopy. Broad-spectrum chemical sprays will destroy predator cohorts.",
            )

        # Macro-biologic biological control endorsement
        if any(k in action_type for k in ("biocontrol", "macro_biologic", "predator_release")):
            return DebateVote(
                agent_id=self.agent_id,
                topic=domain,
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.95,
                rationale="Agronomist endorses macro-biologic release to suppress pest infestation below economic injury level without synthetic chemical residues.",
            )

        # Aquaponics fish tank aeration curtailment veto
        if any(k in action_type for k in ("stop_aeration", "curtail_aerator", "disable_air_pump")):
            fish_do = context.get("fish_tank_do_mg_l", 4.8)
            if fish_do < 5.0:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="aquaponics_fish_welfare",
                    vote_choice="REJECT",
                    weight=max(weight, 4.0),
                    confidence=0.99,
                    rationale=f"AQUAPONICS HYPOXIA VETO: Fish tank DO is low ({fish_do:.1f} mg/L < 5.0 mg/L). Aeration shutdown will cause mass fish asphyxiation.",
                )

        # Systemic copper spray veto in aquaponics greenhouses
        if any(k in action_type for k in ("copper_spray", "systemic_fungicide")) and context.get("is_aquaponics", False):
            return DebateVote(
                agent_id=self.agent_id,
                topic="aquaponics_toxicity",
                vote_choice="REJECT",
                weight=max(weight, 4.0),
                confidence=0.99,
                rationale="AQUAPONICS TOXICITY VETO: Copper sprays recirculate into aquaculture rearing tanks and are acutely lethal to fish and nitrifying bacteria.",
            )

        # Agrivoltaic canopy photoinhibition & sunburn defense veto
        if any(k in action_type for k in ("disable_shading", "force_max_power")) and context.get("canopy_temp_c", 25.0) > 30.5:
            temp = context.get("canopy_temp_c", 31.0)
            return DebateVote(
                agent_id=self.agent_id,
                topic="agrivoltaic_canopy_welfare",
                vote_choice="REJECT",
                weight=max(weight, 3.8),
                confidence=0.98,
                rationale=f"AGRIVOLTAIC PHOTOINHIBITION VETO: Under-canopy temperature is {temp:.1f}°C (>30.5°C). Forcing max power tracking will scorch strawberry beds and cause severe PSII photodamage.",
            )

        # Agrivoltaic defensive shading endorsement
        if any(k in action_type for k in ("crop_shading", "defensive_shade", "agrivoltaic_shade")):
            return DebateVote(
                agent_id=self.agent_id,
                topic="agrivoltaic_canopy_welfare",
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.96,
                rationale="Agronomist strongly endorses dynamic panel shading to lower leaf temperature and suppress transpirational water stress.",
            )

        # Anaerobic digestate bio-fertilizer safety check
        if any(k in action_type for k in ("apply_digestate", "liquid_digestate_feed")):
            is_pasteurized = context.get("pasteurization_compliant", True)
            vfa_tic = context.get("vfa_tic_ratio", 0.25)
            if not is_pasteurized:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="digestate_safety",
                    vote_choice="REJECT",
                    weight=max(weight, 3.8),
                    confidence=0.97,
                    rationale="PATHOGEN BIOSECURITY VETO: Digestate is not pasteurized compliant. Risk of enteric Salmonella/E. coli contamination on export produce.",
                )
            if vfa_tic > 0.40:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="digestate_safety",
                    vote_choice="REJECT",
                    weight=max(weight, 3.2),
                    confidence=0.94,
                    rationale=f"SOUR DIGESTATE VETO: High VFA/TIC ratio ({vfa_tic:.2f} > 0.40) indicates phytotoxic volatile acid accumulation. Defer soil application.",
                )
            return DebateVote(
                agent_id=self.agent_id,
                topic="organic_nutrition",
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.95,
                rationale="Agronomist endorses pasteurized anaerobic digestate: supplies organic bio-available ammonium N and humic organic matter.",
            )

        # Post-harvest cold chain & export quality check
        if any(k in action_type for k in ("ship_export", "release_cold_chain")):
            grade = context.get("quality_grade", "GRADE_AAA_PREMIUM")
            dh = context.get("cumulative_degree_hours", 10.0)
            if "DOWNGRADE" in grade or dh > 45.0:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="export_quality",
                    vote_choice="REJECT",
                    weight=max(weight, 4.0),
                    confidence=0.98,
                    rationale=f"COLD-CHAIN BREACH VETO: Lot suffered {dh:.1f} degree-hours thermal abuse (Grade: {grade}). High risk of Botrytis gray mold fungal rot. Reject export clearance.",
                )
            return DebateVote(
                agent_id=self.agent_id,
                topic="export_quality",
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.96,
                rationale=f"Agronomist approves export shipment: cold-chain intact (Grade: {grade}) with effective MAP atmospheric mold suppression.",
            )

        # Soil Carbon Sequestration & RothC conservation tillage check
        if any(k in action_type for k in ("deep_tillage", "stubble_burn", "burn_residue")):
            return DebateVote(
                agent_id=self.agent_id,
                topic="soil_carbon_conservation",
                vote_choice="REJECT",
                weight=max(weight, 4.0),
                confidence=0.98,
                rationale="SOIL CARBON LOSS VETO: Deep inversion tillage or burning crop residues rapidly oxidizes humified organic matter (HUM) and microbial biomass (BIO). Violates regenerative RothC carbon accrual standards. Transition to no-till conservation agriculture.",
            )

        if any(k in action_type for k in ("apply_biochar", "soil_carbon_sequestration", "carbon_mrv_issuance")):
            return DebateVote(
                agent_id=self.agent_id,
                topic="soil_carbon_sequestration",
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.97,
                rationale="Agronomist strongly endorses soil carbon sequestration & biochar application: stabilizes recalcitrant inert organic matter (IOM >= 95%), expands cation exchange capacity, and enhances soil water retention.",
            )

        # Solar Thermal Crop Drying & Bioactive Nutrient Quality Check
        if any(k in action_type for k in ("solar_drying_batch", "crop_dehydration", "dryer_operation")):
            chamber_t = context.get("chamber_air_temp_c", 48.0)
            aw = context.get("water_activity_aw", 0.55)
            if chamber_t > 55.0:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="drying_quality",
                    vote_choice="REJECT",
                    weight=max(weight, 4.0),
                    confidence=0.98,
                    rationale=f"DRYING THERMAL ABUSE VETO: Chamber temperature ({chamber_t:.1f}°C > 55°C). Destroys ascorbic acid (Vitamin C), triggers enzymatic browning and nutrient loss. Increase PCM thermal absorption or ambient bypass.",
                )
            if aw > 0.65 and context.get("is_packaged", False):
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="drying_quality",
                    vote_choice="REJECT",
                    weight=max(weight, 3.8),
                    confidence=0.96,
                    rationale=f"WATER ACTIVITY VETO: Water activity ({aw:.3f} > 0.60) exceeds safe storage limit. High risk of Aspergillus/Penicillium mold sporulation in sealed storage.",
                )
            return DebateVote(
                agent_id=self.agent_id,
                topic="drying_quality",
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.96,
                rationale="Agronomist endorses solar-thermal PCM crop drying: controlled temperature preserves >70% bioactive ascorbic acid and guarantees microbiological stability (a_w <= 0.60).",
            )

        # Smart Pheromone Trap & Mating Disruption IPM check
        if any(k in action_type for k in ("pheromone_disruption", "pest_trap_intervention")):
            mean_catch = context.get("mean_moths_per_trap_night", 0.0)
            et = context.get("economic_threshold", 5.0)
            if mean_catch < et and context.get("action_subtype") == "chemical_spray":
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="ipm_pest_control",
                    vote_choice="REJECT",
                    weight=max(weight, 4.0),
                    confidence=0.97,
                    rationale=f"IPM THRESHOLD VETO: Optical trap catch ({mean_catch:.1f}/trap) is below Economic Threshold ({et:.1f}). Chemical spraying is unnecessary and harms beneficial pollinators.",
                )
            return DebateVote(
                agent_id=self.agent_id,
                topic="ipm_pest_control",
                vote_choice="APPROVE",
                weight=weight,
                confidence=0.96,
                rationale="Agronomist endorses pheromone mating disruption & optical pest trap monitoring: zero chemical residue and targeted lepidopteran suppression.",
            )

        return DebateVote(
            agent_id=self.agent_id,
            topic=domain,
            vote_choice="APPROVE",
            weight=weight,
            confidence=0.9 if weight >= 2.0 else 0.8,
            rationale=f"{self.role} approves proposal in domain '{domain}' (urgency: {urgency})."
        )

    def audit_pest_trap_threshold(
        self,
        species: str,
        mean_moths_per_trap_night: float,
        economic_threshold: float,
        disruption_radius_m: float,
    ) -> dict[str, Any]:
        """Audits optical pheromone trap population density against IPM Economic Threshold."""
        threshold_exceeded = mean_moths_per_trap_night >= economic_threshold
        return {
            "species": species,
            "mean_moths_per_trap_night": mean_moths_per_trap_night,
            "economic_threshold": economic_threshold,
            "threshold_exceeded": threshold_exceeded,
            "disruption_radius_m": disruption_radius_m,
            "ipm_action": "DEPLOY_PHEROMONE_DISRUPTION" if threshold_exceeded else "MONITOR_ONLY",
        }

    def audit_drying_batch_quality(
        self,
        commodity: str,
        water_activity_aw: float,
        moisture_wb_pct: float,
        vitamin_c_retention_pct: float,
        chamber_temp_c: float,
    ) -> dict[str, Any]:
        """Audits dried produce biophysical safety and bioactive retention."""
        is_safe = water_activity_aw <= 0.60 and chamber_temp_c <= 55.0
        is_grade_aaa = is_safe and vitamin_c_retention_pct >= 70.0 and moisture_wb_pct <= 14.0

        recommendations: list[str] = []
        if water_activity_aw > 0.60:
            recommendations.append(f"Water activity {water_activity_aw:.3f} > 0.60. Extend drying by 2-4 hours to prevent mould.")
        if chamber_temp_c > 52.0:
            recommendations.append("Thermal threshold caution: throttle solar collector airflow to preserve antioxidant anthocyanins.")

        return {
            "commodity": commodity,
            "water_activity_aw": water_activity_aw,
            "moisture_wb_pct": moisture_wb_pct,
            "vitamin_c_retention_pct": vitamin_c_retention_pct,
            "chamber_temp_c": chamber_temp_c,
            "is_microbiologically_safe": is_safe,
            "quality_tier": "GRADE_AAA_EXPORT" if is_grade_aaa else ("GRADE_AA_COMMERCIAL" if is_safe else "REJECT_UNSAFE"),
            "recommendations": recommendations,
        }

    def audit_soil_carbon_health(
        self,
        total_soc_t_c_ha: float,
        hum_ratio_pct: float,
        soil_organic_matter_pct: float,
    ) -> dict[str, Any]:
        """Audits soil organic carbon health and regenerative soil sink status."""
        is_healthy = soil_organic_matter_pct >= 2.0 and total_soc_t_c_ha >= 25.0
        status = (
            "EXCELLENT_CARBON_SINK"
            if soil_organic_matter_pct >= 3.0
            else ("MODERATE_CARBON_SINK" if is_healthy else "DEPLETED_CARBON_DEBT")
        )

        recommendations: list[str] = []
        if soil_organic_matter_pct < 2.0:
            recommendations.append("Apply 2.5 t/ha biochar to rebuild stable inert carbon pool.")
        if hum_ratio_pct < 50.0:
            recommendations.append("Incorporate composted anaerobic digestate to enhance humified organic matter.")

        return {
            "total_soc_t_c_ha": round(total_soc_t_c_ha, 2),
            "hum_ratio_pct": round(hum_ratio_pct, 1),
            "soil_organic_matter_pct": round(soil_organic_matter_pct, 2),
            "carbon_sink_status": status,
            "is_soil_carbon_healthy": is_healthy,
            "recommendations": recommendations,
        }

    def audit_drone_swarm_mission(
        self,
        swarm_size: int,
        total_area_ha: float,
        wind_speed_m_s: float,
        rain_rate_mm_h: float = 0.0,
    ) -> dict[str, Any]:
        """Audits autonomous UAV swarm weather envelope and flight safety."""
        is_safe = wind_speed_m_s <= 12.0 and rain_rate_mm_h <= 5.0
        reasons: list[str] = []
        if wind_speed_m_s > 12.0:
            reasons.append(f"Wind speed {wind_speed_m_s:.1f} m/s exceeds max airframe limit (12 m/s).")
        if rain_rate_mm_h > 5.0:
            reasons.append(f"Precipitation {rain_rate_mm_h:.1f} mm/h exceeds optical rating.")

        return {
            "swarm_size": swarm_size,
            "total_area_ha": total_area_ha,
            "wind_speed_m_s": wind_speed_m_s,
            "rain_rate_mm_h": rain_rate_mm_h,
            "is_flight_permitted": is_safe,
            "flight_readiness": "CLEAR_FOR_TAKEOFF" if is_safe else "FLIGHT_ABORT_WEATHER",
            "safety_reasons": reasons,
        }

    def audit_postharvest_cold_chain(
        self,
        lot_id: str,
        quality_grade: str,
        cumulative_degree_hours: float,
        botrytis_inhibition_pct: float,
    ) -> dict[str, Any]:
        """Audits post-harvest cold-chain log and MAP preservation efficacy."""
        is_export_approved = "GRADE_B" not in quality_grade and cumulative_degree_hours <= 45.0
        return {
            "lot_id": lot_id,
            "quality_grade": quality_grade,
            "cumulative_degree_hours": cumulative_degree_hours,
            "botrytis_inhibition_pct": botrytis_inhibition_pct,
            "is_export_cleared": is_export_approved,
            "disposition": "CLEAR_FOR_AIR_FREIGHT" if is_export_approved else "DIVERT_TO_DOMESTIC_JAM_PROCESSING",
        }

    def audit_digestate_organic_safety(
        self,
        vfa_tic_ratio: float,
        pasteurization_compliant: bool,
        liquid_ec_ms_cm: float,
    ) -> dict[str, Any]:
        """Audits anaerobic digestate bio-fertilizer safety for organic food crops."""
        is_safe = pasteurization_compliant and vfa_tic_ratio <= 0.35 and liquid_ec_ms_cm <= 8.0
        recommendations: list[str] = []

        if not pasteurization_compliant:
            recommendations.append("Require batch thermal hold at 55°C for 4 hours to eliminate coliforms.")
        if vfa_tic_ratio > 0.35:
            recommendations.append("Volatile organic acid toxicity: aerate liquid digestate before root application.")
        if liquid_ec_ms_cm > 6.0:
            recommendations.append(f"High concentrate EC ({liquid_ec_ms_cm} mS/cm): dilute 1:10 with rainwater before fertigation.")

        return {
            "vfa_tic_ratio": vfa_tic_ratio,
            "pasteurization_compliant": pasteurization_compliant,
            "liquid_ec_ms_cm": liquid_ec_ms_cm,
            "is_safe_for_application": is_safe,
            "prescribed_dilution_ratio": "1:10" if liquid_ec_ms_cm > 5.0 else "1:5",
            "recommendations": recommendations,
        }
