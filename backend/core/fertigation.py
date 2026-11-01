"""
Precision Fertigation & Nutrient Dosing Optimization Engine.

Calculates stage-specific N-P-K nutrient balancing, target Electrical Conductivity (EC),
pH acid buffering, and leaching fractions to prevent root zone salinity stress.
"""

from typing import Dict, Tuple, List
from pydantic import BaseModel, Field

from backend.core.twin_state import PlotZone, FarmDigitalTwin


class CropFertigationTarget(BaseModel):
    """Agronomic nutritional targets for a specific crop and phenological phase."""
    crop_type: str
    growth_stage: str
    target_ec_ms_cm: float = Field(..., ge=0.5, le=4.0)
    target_ph_min: float = Field(5.5, ge=4.0, le=8.5)
    target_ph_max: float = Field(6.5, ge=4.0, le=8.5)
    n_p_k_ratio: Tuple[float, float, float] = Field((1.0, 0.5, 1.2), description="Ratio of N:P2O5:K2O")


class FertigationRecipe(BaseModel):
    """Prescribed dosing regime per cubic meter (1,000 Liters) of irrigation water."""
    zone_id: str
    crop_type: str
    growth_stage: str
    target_ec_ms_cm: float
    current_soil_ec_ms_cm: float
    ec_deficit_ms_cm: float
    target_ph: float
    tank_a_injection_ml_m3: float = Field(..., description="Stock Solution A (Calcium + Nitrate + Iron chelate) in mL/m3")
    tank_b_injection_ml_m3: float = Field(..., description="Stock Solution B (Phosphate + Sulfate + Potassium) in mL/m3")
    acid_injection_ml_m3: float = Field(..., description="Acid buffer (HNO3/H3PO4) for pH correction in mL/m3")
    leaching_fraction_pct: float = Field(..., description="Drainage flushing ratio to avoid salt accumulation")
    recommendations: List[str] = Field(default_factory=list)


class FertigationOptimizer:
    """
    Optimizes fertilizer injection ratios and pH correction for precision hydroponic/soil systems.
    """

    # Agronomic nutrient matrix: (crop_type, growth_stage) -> CropFertigationTarget
    NUTRITION_PROFILES: Dict[Tuple[str, str], CropFertigationTarget] = {
        # Strawberries (Fragaria ananassa)
        ("Strawberries", "seedling"): CropFertigationTarget(
            crop_type="Strawberries", growth_stage="seedling",
            target_ec_ms_cm=1.2, target_ph_min=5.8, target_ph_max=6.2, n_p_k_ratio=(1.2, 0.6, 1.0)
        ),
        ("Strawberries", "vegetative"): CropFertigationTarget(
            crop_type="Strawberries", growth_stage="vegetative",
            target_ec_ms_cm=1.5, target_ph_min=5.8, target_ph_max=6.2, n_p_k_ratio=(1.5, 0.5, 1.2)
        ),
        ("Strawberries", "flowering"): CropFertigationTarget(
            crop_type="Strawberries", growth_stage="flowering",
            target_ec_ms_cm=1.8, target_ph_min=5.8, target_ph_max=6.2, n_p_k_ratio=(1.0, 0.5, 1.8)
        ),
        ("Strawberries", "fruiting"): CropFertigationTarget(
            crop_type="Strawberries", growth_stage="fruiting",
            target_ec_ms_cm=2.0, target_ph_min=5.8, target_ph_max=6.2, n_p_k_ratio=(0.9, 0.4, 2.2)
        ),
        ("Strawberries", "harvest_ready"): CropFertigationTarget(
            crop_type="Strawberries", growth_stage="harvest_ready",
            target_ec_ms_cm=1.6, target_ph_min=6.0, target_ph_max=6.4, n_p_k_ratio=(0.8, 0.4, 1.5)
        ),

        # Bell Pepper (Capsicum annuum)
        ("Bell Pepper", "vegetative"): CropFertigationTarget(
            crop_type="Bell Pepper", growth_stage="vegetative",
            target_ec_ms_cm=1.8, target_ph_min=6.0, target_ph_max=6.5, n_p_k_ratio=(1.4, 0.5, 1.3)
        ),
        ("Bell Pepper", "flowering"): CropFertigationTarget(
            crop_type="Bell Pepper", growth_stage="flowering",
            target_ec_ms_cm=2.2, target_ph_min=6.0, target_ph_max=6.5, n_p_k_ratio=(1.0, 0.5, 2.0)
        ),
        ("Bell Pepper", "fruiting"): CropFertigationTarget(
            crop_type="Bell Pepper", growth_stage="fruiting",
            target_ec_ms_cm=2.4, target_ph_min=6.0, target_ph_max=6.5, n_p_k_ratio=(1.0, 0.4, 2.4)
        ),

        # Arabica Coffee (Coffea arabica)
        ("Arabica Coffee", "flowering"): CropFertigationTarget(
            crop_type="Arabica Coffee", growth_stage="flowering",
            target_ec_ms_cm=1.6, target_ph_min=5.5, target_ph_max=6.0, n_p_k_ratio=(1.2, 0.6, 1.6)
        ),
        ("Arabica Coffee", "fruiting"): CropFertigationTarget(
            crop_type="Arabica Coffee", growth_stage="fruiting",
            target_ec_ms_cm=1.9, target_ph_min=5.5, target_ph_max=6.0, n_p_k_ratio=(1.0, 0.4, 2.0)
        ),

        # Hydrangea (Hydrangea macrophylla)
        ("Hydrangea", "flowering"): CropFertigationTarget(
            crop_type="Hydrangea", growth_stage="flowering",
            target_ec_ms_cm=1.4, target_ph_min=5.2, target_ph_max=5.8, n_p_k_ratio=(1.0, 0.8, 1.2)
        ),
    }

    @classmethod
    def get_crop_target(cls, crop_type: str, growth_stage: str) -> CropFertigationTarget:
        """Retrieves target parameters or provides a safe baseline default."""
        target = cls.NUTRITION_PROFILES.get((crop_type, growth_stage))
        if target:
            return target

        # Default fallback target
        return CropFertigationTarget(
            crop_type=crop_type,
            growth_stage=growth_stage,
            target_ec_ms_cm=1.6,
            target_ph_min=5.8,
            target_ph_max=6.5,
            n_p_k_ratio=(1.2, 0.5, 1.5)
        )

    @classmethod
    def compute_recipe(
        cls,
        zone: PlotZone,
        raw_water_ec_ms_cm: float = 0.25,
        raw_water_ph: float = 7.4
    ) -> FertigationRecipe:
        """
        Computes tailored fertilizer injection rates (mL stock solution per m3 water)
        and acid buffering required to reach optimal target EC and pH.
        """
        target = cls.get_crop_target(zone.crop_type, zone.growth_stage)
        current_ec = getattr(zone, "soil_ec", 1.2)
        ec_deficit = max(0.0, target.target_ec_ms_cm - raw_water_ec_ms_cm)

        # 1. Fertilizer Dosing Injection Rate
        # Benchmark: 100 mL of 100x concentrated stock solution adds ~0.15 mS/cm EC per m3
        base_injection_rate_ml_m3 = (ec_deficit / 0.15) * 100.0

        n_ratio, _, k_ratio = target.n_p_k_ratio
        # Tank A supplies Calcium Nitrate (higher when N is needed)
        # Tank B supplies Potassium Phosphate & Sulphates (higher when K is needed)
        tank_a_ml = round(base_injection_rate_ml_m3 * (n_ratio / 1.0), 1)
        tank_b_ml = round(base_injection_rate_ml_m3 * (k_ratio / 1.5), 1)

        # 2. pH Correction & Acid Neutralization
        target_ph = (target.target_ph_min + target.target_ph_max) / 2.0
        acid_ml = 0.0
        recommendations: List[str] = []

        if raw_water_ph > target.target_ph_max:
            ph_delta = raw_water_ph - target_ph
            # 50 mL of 10% nitric acid neutralizes ~0.5 pH unit in 1 m3 water
            acid_ml = round((ph_delta / 0.5) * 50.0, 1)
            recommendations.append(
                f"Inject {acid_ml:.1f} mL/m3 acid to buffer alkaline raw water (pH {raw_water_ph:.1f} -> {target_ph:.1f})."
            )

        # 3. Leaching Fraction (LF) to prevent salt toxicity: LF = EC_in / (2 * EC_drainage_threshold)
        drainage_max_ec = target.target_ec_ms_cm * 1.5
        leaching_fraction = round(min(30.0, max(5.0, (target.target_ec_ms_cm / (2.0 * drainage_max_ec)) * 100.0)), 1)

        if current_ec > target.target_ec_ms_cm * 1.3:
            recommendations.append(
                f"Root zone salinity elevated ({current_ec:.2f} mS/cm). Increase leaching fraction to {leaching_fraction + 5.0:.1f}%."
            )

        return FertigationRecipe(
            zone_id=zone.id,
            crop_type=zone.crop_type,
            growth_stage=zone.growth_stage,
            target_ec_ms_cm=target.target_ec_ms_cm,
            current_soil_ec_ms_cm=round(current_ec, 2),
            ec_deficit_ms_cm=round(ec_deficit, 2),
            target_ph=round(target_ph, 2),
            tank_a_injection_ml_m3=tank_a_ml,
            tank_b_injection_ml_m3=tank_b_ml,
            acid_injection_ml_m3=acid_ml,
            leaching_fraction_pct=leaching_fraction,
            recommendations=recommendations
        )

    @classmethod
    def batch_optimize_farm(
        cls,
        farm: FarmDigitalTwin,
        raw_water_ec_ms_cm: float = 0.25,
        raw_water_ph: float = 7.4
    ) -> List[FertigationRecipe]:
        """Calculates fertigation prescriptions across all zones in the farm."""
        return [
            cls.compute_recipe(zone, raw_water_ec_ms_cm=raw_water_ec_ms_cm, raw_water_ph=raw_water_ph)
            for zone in farm.zones
        ]
