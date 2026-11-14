"""
Precision Weed vs. Crop Computer Vision & Micro-Mechanical Targeting Engine.

Implements edge-AI detection algorithms for:
- Differentiating dicot/monocot weed species from agricultural cash crops
- Calculating millimeter-precision weed centroid coordinates (X, Y)
- Intelligent actuator toolpath selection: Delta-Arm Punch vs. Micro-Tiller vs. Laser Diode
- Calculating organic chemical herbicide avoidance (active ingredient grams averted)
"""
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class WeedSpecies(str, Enum):
    AMARANTHUS_SP = "Amaranthus spinosus (Dền Gai)"
    PORTULACA_OLERACEA = "Portulaca oleracea (Rau Sam)"
    ECHINOCHLOA = "Echinochloa crus-galli (Cỏ Lồng Vực)"
    CYPERUS_ROTUNDUS = "Cyperus rotundus (Cỏ Gấu)"
    CROP_PLANT = "Protected Crop Canopy"


class TargetingTool(str, Enum):
    DELTA_PUNCH = "DELTA_PUNCH"          # Fast mechanical solenoid punch (<20ms)
    MICRO_TILLER = "MICRO_TILLER"        # Rotating root-severing micro-tiller
    THERMAL_LASER = "THERMAL_LASER"      # 450nm focused laser photothermal desiccation
    SKIP_PROTECTED = "SKIP_PROTECTED"    # Protected crop plant


class DetectedPlant(BaseModel):
    """Computer vision recognition of an individual plant specimen in the bed."""
    plant_id: str
    centroid_x_mm: float = Field(..., description="Camera frame relative X in mm")
    centroid_y_mm: float = Field(..., description="Camera frame relative Y in mm")
    canopy_diameter_mm: float = Field(..., ge=1.0)
    is_weed: bool
    species: WeedSpecies
    ai_confidence: float = Field(..., ge=0.0, le=1.0)
    selected_tool: TargetingTool
    termination_energy_joules: float
    glyphosate_averted_mg: float = Field(0.0, description="Chemical herbicide volume avoided via mechanical weeding")


class BedWeedSurvey(BaseModel):
    """Aggregate scan metrics over a 1-meter bed swath."""
    bed_id: str
    total_plants_detected: int
    weeds_count: int
    crops_count: int
    weed_density_per_m2: float
    total_herbicide_averted_grams: float
    action_required: bool
    recommended_actuator: TargetingTool
    detected_plants: list[DetectedPlant]


class WeedTargetingEngine:
    """
    Simulates near-infrared (NIR) and RGB edge-AI vision for precision mechanical weeding.
    """

    # Herbicide active ingredient equivalence: ~45 mg glyphosate avoided per weed mechanically terminated
    GLYPHOSATE_EQUIVALENT_MG_PER_WEED: ClassVar[float] = 45.0

    def classify_specimen(
        self,
        plant_id: str,
        centroid_x_mm: float,
        centroid_y_mm: float,
        canopy_diameter_mm: float,
        ndvi: float,
        aspect_ratio: float,
        crop_type: str = "Strawberries",
    ) -> DetectedPlant:
        """
        Differentiates crop from weed and assigns optimal zero-chemical mechanical actuator.
        """
        # Crop canopy signature check: Strawberries have trifoliate rounded leaves with aspect_ratio ~ 1.05
        # Weeds like Cyperus are linear (aspect > 2.5), Portulaca are prostrate fleshy rosettes
        is_crop = (
            (crop_type == "Strawberries" and 0.85 <= aspect_ratio <= 1.25 and canopy_diameter_mm >= 80.0)
            or (crop_type == "Bell Pepper" and 0.75 <= aspect_ratio <= 1.35 and canopy_diameter_mm >= 95.0)
        )

        if is_crop:
            return DetectedPlant(
                plant_id=plant_id,
                centroid_x_mm=centroid_x_mm,
                centroid_y_mm=centroid_y_mm,
                canopy_diameter_mm=canopy_diameter_mm,
                is_weed=False,
                species=WeedSpecies.CROP_PLANT,
                ai_confidence=0.96,
                selected_tool=TargetingTool.SKIP_PROTECTED,
                termination_energy_joules=0.0,
                glyphosate_averted_mg=0.0,
            )

        # Identify weed species
        if aspect_ratio >= 2.2:
            species = WeedSpecies.CYPERUS_ROTUNDUS
        elif canopy_diameter_mm >= 60.0:
            species = WeedSpecies.AMARANTHUS_SP
        elif aspect_ratio <= 0.9:
            species = WeedSpecies.PORTULACA_OLERACEA
        else:
            species = WeedSpecies.ECHINOCHLOA

        # Select mechanical tool based on size and species rooting depth
        if canopy_diameter_mm < 25.0:
            tool = TargetingTool.THERMAL_LASER
            energy_j = 15.0
        elif canopy_diameter_mm <= 65.0:
            tool = TargetingTool.DELTA_PUNCH
            energy_j = 35.0
        else:
            tool = TargetingTool.MICRO_TILLER
            energy_j = 75.0

        return DetectedPlant(
            plant_id=plant_id,
            centroid_x_mm=centroid_x_mm,
            centroid_y_mm=centroid_y_mm,
            canopy_diameter_mm=canopy_diameter_mm,
            is_weed=True,
            species=species,
            ai_confidence=0.93,
            selected_tool=tool,
            termination_energy_joules=energy_j,
            glyphosate_averted_mg=self.GLYPHOSATE_EQUIVALENT_MG_PER_WEED,
        )

    def scan_bed_swath(
        self,
        bed_id: str,
        specimens: list[dict[str, float]],
        crop_type: str = "Strawberries",
    ) -> BedWeedSurvey:
        """
        Scans a series of plants detected in a bed and calculates weed density and herbicide savings.
        """
        classified: list[DetectedPlant] = []
        weed_count = 0
        crop_count = 0
        total_averted_mg = 0.0

        for idx, spec in enumerate(specimens):
            p = self.classify_specimen(
                plant_id=f"{bed_id}-P{idx:03d}",
                centroid_x_mm=spec.get("x_mm", 0.0),
                centroid_y_mm=spec.get("y_mm", 0.0),
                canopy_diameter_mm=spec.get("diameter_mm", 30.0),
                ndvi=spec.get("ndvi", 0.70),
                aspect_ratio=spec.get("aspect_ratio", 1.0),
                crop_type=crop_type,
            )
            classified.append(p)
            if p.is_weed:
                weed_count += 1
                total_averted_mg += p.glyphosate_averted_mg
            else:
                crop_count += 1

        # Bed area benchmark: 1m swath length x 0.8m width = 0.8 m2
        area_m2 = 0.8
        density = round(weed_count / area_m2, 2)
        action_req = density >= 1.5

        rec_tool = TargetingTool.DELTA_PUNCH
        if weed_count > 0:
            tools = [p.selected_tool for p in classified if p.is_weed]
            rec_tool = max(set(tools), key=tools.count)

        return BedWeedSurvey(
            bed_id=bed_id,
            total_plants_detected=len(classified),
            weeds_count=weed_count,
            crops_count=crop_count,
            weed_density_per_m2=density,
            total_herbicide_averted_grams=round(total_averted_mg / 1000.0, 3),
            action_required=action_req,
            recommended_actuator=rec_tool,
            detected_plants=classified,
        )
