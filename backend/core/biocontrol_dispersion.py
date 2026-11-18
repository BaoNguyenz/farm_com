r"""
Macro-Biologic Spatial Release Planner, Canister Budgeting & Drone Aerial Hopper Dispersion.

Calculates precision agronomic dispersal metrics for biological control agents:
- Dose scaling based on Economic Threshold (ET) and Economic Injury Level (EIL)
- Canister / bottle packaging decomposition (vermiculite / sawdust carrier matrix)
- Drone aerial broadcast dispersal kinematics:
  $\dot{M}_{\text{dispenser}} = \text{Dose}_{\text{m}^2} \cdot v_{\text{flight}} \cdot w_{\text{swath}}$
- Multi-zone farm release manifest generation with economic cost estimation.
"""
import math
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.core.biocontrol import PredatorSpecies, PreySpecies


class DispersionMethod(str, Enum):
    MANUAL_SHAKER = "manual_shaker"
    DRONE_AERIAL_HOPPER = "drone_aerial_hopper"
    HANGING_CARD_TAG = "hanging_card_tag"


class CarrierMaterial(str, Enum):
    VERMICULITE = "vermiculite"
    SAWDUST = "sawdust"
    CARDBOARD_CARD = "cardboard_card"


class PackagingSpec(BaseModel):
    """Commercial packaging profile for macro-biologic delivery."""
    predator_species: PredatorSpecies
    unit_name: str = "bottle_2000"
    units_per_pack: int = Field(2000, ge=100)
    carrier: CarrierMaterial = CarrierMaterial.VERMICULITE
    net_weight_grams: float = Field(80.0, ge=10.0)
    cost_vnd: float = Field(350000.0, ge=10000.0)


class ZoneReleasePlan(BaseModel):
    """Release assignment for a specific greenhouse canopy or plot."""
    zone_id: str
    canopy_area_m2: float = Field(..., gt=0.0)
    target_pest: PreySpecies
    current_pest_density: float = Field(..., ge=0.0)
    beneficial_species: PredatorSpecies
    dose_per_m2: float = Field(..., gt=0.0)
    total_beneficials_needed: int = Field(..., ge=1)
    packages_required: int = Field(..., ge=1)
    dispersion_method: DispersionMethod
    drone_hopper_flow_rate_per_sec: float = Field(0.0, ge=0.0, description="Insects dispersed per second")
    application_duration_minutes: float = Field(..., gt=0.0)
    total_cost_vnd: float = Field(..., ge=0.0)


class FarmReleaseManifest(BaseModel):
    """Aggregate multi-zone biological control dispatch manifest."""
    manifest_id: str
    total_zones: int
    total_canopy_area_m2: float
    total_beneficials_dispatched: int
    total_packages_needed: int
    total_estimated_cost_vnd: float
    zone_plans: list[ZoneReleasePlan]


class MacroBiologicDispersionEngine:
    """
    Coordinates spatial distribution, dosage calculation, and equipment calibration.
    """

    DEFAULT_PACKAGING: ClassVar[dict[PredatorSpecies, PackagingSpec]] = {
        PredatorSpecies.PHYTOSEIULUS_PERSIMILIS: PackagingSpec(
            predator_species=PredatorSpecies.PHYTOSEIULUS_PERSIMILIS,
            unit_name="bottle_2000_mites",
            units_per_pack=2000,
            carrier=CarrierMaterial.VERMICULITE,
            net_weight_grams=85.0,
            cost_vnd=350000.0,
        ),
        PredatorSpecies.NEOSEIULUS_CALIFORNICUS: PackagingSpec(
            predator_species=PredatorSpecies.NEOSEIULUS_CALIFORNICUS,
            unit_name="bottle_2000_mites",
            units_per_pack=2000,
            carrier=CarrierMaterial.VERMICULITE,
            net_weight_grams=80.0,
            cost_vnd=320000.0,
        ),
        PredatorSpecies.AMBLYSEIUS_SWIRSKII: PackagingSpec(
            predator_species=PredatorSpecies.AMBLYSEIUS_SWIRSKII,
            unit_name="bottle_25000_mites",
            units_per_pack=25000,
            carrier=CarrierMaterial.SAWDUST,
            net_weight_grams=250.0,
            cost_vnd=680000.0,
        ),
    }

    @classmethod
    def calculate_dose_rate(
        cls,
        pest_density: float,
        economic_threshold: float = 5.0,
        economic_injury_level: float = 15.0,
    ) -> float:
        """
        Determines release dose per square meter:
        - Low / Preventive (<= ET): 2.5 predators/m2
        - Moderate (ET < density <= EIL): 12.0 predators/m2
        - Heavy / Outbreak (> EIL): 28.0 predators/m2
        """
        if pest_density <= economic_threshold:
            return 2.5
        if pest_density <= economic_injury_level:
            return 12.0
        return 28.0

    @classmethod
    def plan_zone_release(
        cls,
        zone_id: str,
        canopy_area_m2: float,
        pest_density: float,
        target_pest: PreySpecies = PreySpecies.TWO_SPOTTED_SPIDER_MITE,
        beneficial_species: PredatorSpecies = PredatorSpecies.PHYTOSEIULUS_PERSIMILIS,
        use_drone: bool = True,
        flight_speed_m_s: float = 1.5,
        swath_width_m: float = 2.0,
    ) -> ZoneReleasePlan:
        """
        Creates an actionable biological distribution plan for a single zone.
        """
        dose_per_m2 = cls.calculate_dose_rate(pest_density)
        total_needed = math.ceil(canopy_area_m2 * dose_per_m2)

        pkg = cls.DEFAULT_PACKAGING.get(
            beneficial_species,
            cls.DEFAULT_PACKAGING[PredatorSpecies.PHYTOSEIULUS_PERSIMILIS],
        )

        packages_required = max(1, math.ceil(total_needed / pkg.units_per_pack))
        total_cost = packages_required * pkg.cost_vnd

        if use_drone:
            method = DispersionMethod.DRONE_AERIAL_HOPPER
            # Coverage rate in m2/s = speed * swath
            coverage_rate_m2_s = flight_speed_m_s * swath_width_m
            duration_seconds = canopy_area_m2 / coverage_rate_m2_s
            duration_minutes = round(max(1.0, duration_seconds / 60.0), 1)
            hopper_flow_rate = round(dose_per_m2 * coverage_rate_m2_s, 2)
        else:
            method = DispersionMethod.MANUAL_SHAKER
            duration_minutes = round(max(5.0, canopy_area_m2 / 50.0), 1)  # ~50 m2 per min manually
            hopper_flow_rate = 0.0

        return ZoneReleasePlan(
            zone_id=zone_id,
            canopy_area_m2=canopy_area_m2,
            target_pest=target_pest,
            current_pest_density=pest_density,
            beneficial_species=beneficial_species,
            dose_per_m2=dose_per_m2,
            total_beneficials_needed=total_needed,
            packages_required=packages_required,
            dispersion_method=method,
            drone_hopper_flow_rate_per_sec=hopper_flow_rate,
            application_duration_minutes=duration_minutes,
            total_cost_vnd=total_cost,
        )

    @classmethod
    def generate_farm_manifest(
        cls,
        zone_specs: list[dict],
        manifest_id: str = "MANIFEST_BIO_001",
    ) -> FarmReleaseManifest:
        """
        Aggregates multiple zone requirements into a single master farm manifest.
        zone_specs format: [{"zone_id": "ZONE_A", "canopy_area_m2": 600.0, "pest_density": 8.0, ...}]
        """
        plans = []
        total_area = 0.0
        total_insects = 0
        total_packs = 0
        total_cost = 0.0

        for spec in zone_specs:
            plan = cls.plan_zone_release(
                zone_id=spec["zone_id"],
                canopy_area_m2=spec["canopy_area_m2"],
                pest_density=spec["pest_density"],
                target_pest=spec.get("target_pest", PreySpecies.TWO_SPOTTED_SPIDER_MITE),
                beneficial_species=spec.get("beneficial_species", PredatorSpecies.PHYTOSEIULUS_PERSIMILIS),
                use_drone=spec.get("use_drone", True),
            )
            plans.append(plan)
            total_area += plan.canopy_area_m2
            total_insects += plan.total_beneficials_needed
            total_packs += plan.packages_required
            total_cost += plan.total_cost_vnd

        return FarmReleaseManifest(
            manifest_id=manifest_id,
            total_zones=len(plans),
            total_canopy_area_m2=round(total_area, 1),
            total_beneficials_dispatched=total_insects,
            total_packages_needed=total_packs,
            total_estimated_cost_vnd=round(total_cost, 0),
            zone_plans=plans,
        )
