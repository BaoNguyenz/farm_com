r"""
Closed-Loop Recirculating Aquaponic Ecosystem Coordinator & Mass Balance Engine.

Couples recirculating aquaculture (fish tanks), solids removal, biological filtration (MBBR),
and deep water culture (DWC) hydroponics into a unified closed mass-balance loop:
- Fish tank -> Swirl separator -> MBBR biofilter -> DWC plant troughs -> Sump pump -> Fish tank
- Continuous multi-solute mass balance: TAN, NO2-, NO3-, DO, Alkalinity, and pH
- Dynamic water turnover ($Q = 3.5\text{ m}^3/\text{h}$) across system volume ($18.5\text{ m}^3$)
- Dual-harvest readiness accounting (fish biomass kg + heads of leafy greens).
"""
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.core.aquaponics_biofilter import (
    BiofilterMediaType,
    BiofilterState,
    MBBRBiofilterEngine,
)
from backend.core.aquaponics_fish import (
    FishBioenergeticsEngine,
    FishSpecies,
    FishTankState,
)
from backend.core.aquaponics_hydroponics import (
    AquaponicCropType,
    AquaponicHydroponicsEngine,
    BaseChemical,
    BufferDosingRecommendation,
    HydroponicBedState,
    HydroponicSubsystemType,
)


class AquaponicLoopStatus(str, Enum):
    OPTIMAL_EQUILIBRIUM = "optimal_equilibrium"
    AMMONIA_SPIKE = "ammonia_spike"
    NITRITE_ACCUMULATION = "nitrite_accumulation"
    ALKALINITY_DEPLETED = "alkalinity_depleted"
    HYPOXIA_CRITICAL = "hypoxia_critical"


class AquaponicEcosystemTelemetry(BaseModel):
    """Integrated operational snapshot of the complete coupled aquaponic facility."""
    system_id: str = "AQUAPONICS_FACILITY_01"
    fish_tank: FishTankState
    biofilter: BiofilterState
    hydroponics: HydroponicBedState
    water_flow_rate_m3_h: float = Field(3.5, ge=0.5)
    total_water_volume_m3: float = Field(18.5, ge=5.0)
    water_turnover_hours: float = Field(..., ge=0.5)
    ecosystem_status: AquaponicLoopStatus
    system_health_score: float = Field(..., ge=0.0, le=100.0)
    total_fish_biomass_kg: float
    total_crop_heads: int
    recommendations: list[str] = Field(default_factory=list)


class AquaponicEcosystemCoordinator:
    """
    Coordinates recirculating water loop, synchronizing fish excretion, microbial nitrification,
    and plant nutrient uptake.
    """

    DEFAULT_FISH_VOLUME_M3: ClassVar[float] = 5.0
    DEFAULT_BIOFILTER_VOLUME_M3: ClassVar[float] = 1.5
    DEFAULT_DWC_VOLUME_M3: ClassVar[float] = 12.0

    def __init__(
        self,
        system_id: str = "AQUAPONICS_FACILITY_01",
        flow_rate_m3_h: float = 3.5,
    ) -> None:
        self.system_id = system_id
        self.flow_rate_m3_h = flow_rate_m3_h

        self.fish_state = FishTankState(
            tank_id="TANK_TILAPIA_01",
            species=FishSpecies.NILE_TILAPIA,
            fish_count=500,
            avg_weight_grams=450.0,
            total_biomass_kg=225.0,
            water_volume_m3=self.DEFAULT_FISH_VOLUME_M3,
            water_temp_c=26.5,
            ph=7.0,
            dissolved_oxygen_mg_l=6.2,
            tan_mg_l=0.35,
            toxic_nh3_mg_l=0.012,
        )

        self.biofilter_state = BiofilterState(
            reactor_id="MBBR_BIOFILTER_01",
            media_type=BiofilterMediaType.K1_CARRIER,
            media_volume_m3=0.75,
            active_surface_area_m2=600.0,
            flow_rate_m3_h=flow_rate_m3_h,
            inlet_tan_mg_l=0.35,
            inlet_no2_mg_l=0.05,
            inlet_no3_mg_l=75.0,
            outlet_tan_mg_l=0.08,
            outlet_no2_mg_l=0.02,
            outlet_no3_mg_l=76.2,
            tan_oxidation_rate_g_h=0.95,
            no2_oxidation_rate_g_h=0.88,
            oxygen_consumed_g_h=4.25,
            alkalinity_destroyed_g_h_caco3=6.78,
            dissolved_oxygen_mg_l=6.0,
            tan_conversion_efficiency_pct=88.5,
        )

        self.hydroponic_state = HydroponicBedState(
            bed_id="DWC_BED_01",
            subsystem_type=HydroponicSubsystemType.DEEP_WATER_CULTURE_DWC,
            crop_type=AquaponicCropType.BUTTERHEAD_LETTUCE,
            bed_area_m2=40.0,
            plant_count=1000,
            water_volume_m3=self.DEFAULT_DWC_VOLUME_M3,
            inlet_no3_mg_l=76.2,
            outlet_no3_mg_l=75.0,
            daily_no3_uptake_grams=28.5,
            alkalinity_mg_l_caco3=85.0,
            ph=6.9,
        )

    def get_total_water_volume_m3(self) -> float:
        return (
            self.fish_state.water_volume_m3
            + self.DEFAULT_BIOFILTER_VOLUME_M3
            + self.hydroponic_state.water_volume_m3
        )

    def step_simulation_cycle(
        self,
        feed_input_kg: float = 0.0,
        par_umol_m2_s: float = 400.0,
        supplementary_aeration: bool = True,
        dt_hours: float = 1.0,
    ) -> AquaponicEcosystemTelemetry:
        """
        Executes one time step across the recirculating loop:
        1. Fish tank feeding & TAN production
        2. MBBR biofilter oxidation of TAN to NO2 and NO3
        3. Plant bed absorption of NO3
        4. Water loop return and dissolved oxygen / alkalinity balance.
        """
        # Step 1: Fish feeding
        if feed_input_kg > 0.0:
            self.fish_state, _ = FishBioenergeticsEngine.apply_feeding_event(
                self.fish_state,
                feed_kg=feed_input_kg,
            )

        if supplementary_aeration:
            self.fish_state.dissolved_oxygen_mg_l = min(7.5, self.fish_state.dissolved_oxygen_mg_l + (0.8 * dt_hours))

        # Step 2: Biofilter oxidation
        self.biofilter_state = MBBRBiofilterEngine.simulate_biofilter_step(
            inlet_tan_mg_l=self.fish_state.tan_mg_l,
            inlet_no2_mg_l=self.biofilter_state.outlet_no2_mg_l,
            inlet_no3_mg_l=self.hydroponic_state.outlet_no3_mg_l,
            dissolved_oxygen_mg_l=self.fish_state.dissolved_oxygen_mg_l,
            water_flow_m3_h=self.flow_rate_m3_h,
            ph=self.fish_state.ph,
            temp_c=self.fish_state.water_temp_c,
            dt_hours=dt_hours,
        )

        # Update fish tank TAN to match biofilter outlet after water turnover
        turnover_factor = min(1.0, (self.flow_rate_m3_h * dt_hours) / self.fish_state.water_volume_m3)
        blended_tan = (self.fish_state.tan_mg_l * (1.0 - turnover_factor)) + (self.biofilter_state.outlet_tan_mg_l * turnover_factor)
        self.fish_state.tan_mg_l = round(blended_tan, 3)
        self.fish_state.toxic_nh3_mg_l = FishBioenergeticsEngine.calculate_toxic_nh3_concentration(
            self.fish_state.tan_mg_l, self.fish_state.ph, self.fish_state.water_temp_c
        )

        # Step 3: Hydroponic assimilation
        self.hydroponic_state = AquaponicHydroponicsEngine.simulate_hydroponic_step(
            state=self.hydroponic_state,
            inlet_no3_mg_l=self.biofilter_state.outlet_no3_mg_l,
            water_flow_m3_h=self.flow_rate_m3_h,
            par_umol_m2_s=par_umol_m2_s,
            dt_hours=dt_hours,
        )

        # Step 4: Alkalinity consumption in loop
        tot_vol = self.get_total_water_volume_m3()
        alk_destroyed_mg_l = (self.biofilter_state.alkalinity_destroyed_g_h_caco3 * dt_hours) / tot_vol
        new_alk = max(10.0, self.hydroponic_state.alkalinity_mg_l_caco3 - alk_destroyed_mg_l)
        self.hydroponic_state.alkalinity_mg_l_caco3 = round(new_alk, 1)

        # Diagnose ecosystem loop status & health score
        recs: list[str] = []
        score = 100.0

        if self.fish_state.toxic_nh3_mg_l >= 0.05:
            status = AquaponicLoopStatus.AMMONIA_SPIKE
            score -= 30.0
            recs.append("CRITICAL: Toxic un-ionized NH3 > 0.05 mg/L. Reduce feed and increase biofilter aeration.")
        elif self.biofilter_state.outlet_no2_mg_l >= 1.0:
            status = AquaponicLoopStatus.NITRITE_ACCUMULATION
            score -= 25.0
            recs.append("WARNING: Nitrite NO2- elevated. Check NOB biofilm and maintain salinity at 1-2 ppt to prevent brown blood disease.")
        elif self.hydroponic_state.alkalinity_mg_l_caco3 < 50.0:
            status = AquaponicLoopStatus.ALKALINITY_DEPLETED
            score -= 20.0
            recs.append("WARNING: Alkalinity < 50 mg/L CaCO3. Dose potassium bicarbonate (KHCO3) to prevent pH crash.")
        elif self.fish_state.dissolved_oxygen_mg_l < 4.0:
            status = AquaponicLoopStatus.HYPOXIA_CRITICAL
            score -= 35.0
            recs.append("CRITICAL: Low dissolved oxygen in fish tank (<4.0 mg/L). Engage emergency venturi aerator.")
        else:
            status = AquaponicLoopStatus.OPTIMAL_EQUILIBRIUM
            recs.append("Ecosystem in healthy symbiotic equilibrium: Fish TAN efficiently nitrified to crop fertilizer.")

        turnover_hours = round(tot_vol / self.flow_rate_m3_h, 1)

        return AquaponicEcosystemTelemetry(
            system_id=self.system_id,
            fish_tank=self.fish_state,
            biofilter=self.biofilter_state,
            hydroponics=self.hydroponic_state,
            water_flow_rate_m3_h=self.flow_rate_m3_h,
            total_water_volume_m3=tot_vol,
            water_turnover_hours=turnover_hours,
            ecosystem_status=status,
            system_health_score=round(max(0.0, score), 1),
            total_fish_biomass_kg=self.fish_state.total_biomass_kg,
            total_crop_heads=self.hydroponic_state.plant_count,
            recommendations=recs,
        )

    def dose_alkalinity_buffer(
        self,
        chemical: BaseChemical = BaseChemical.POTASSIUM_BICARBONATE,
        target_alkalinity_mg_l: float = 100.0,
    ) -> BufferDosingRecommendation:
        """Applies buffer chemical to restore system water alkalinity."""
        rec = AquaponicHydroponicsEngine.calculate_buffer_dosing(
            current_alkalinity_mg_l=self.hydroponic_state.alkalinity_mg_l_caco3,
            water_volume_m3=self.get_total_water_volume_m3(),
            target_alkalinity_mg_l=target_alkalinity_mg_l,
            chemical=chemical,
        )
        self.hydroponic_state.alkalinity_mg_l_caco3 = rec.expected_alkalinity_after_mg_l
        return rec
