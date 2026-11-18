r"""
Pesticide Chemical Residue Degradation Kinetics & Biocontrol Safety Clearance.

Implements IOBC (International Organization for Biological Control) residue safety standards:
- First-order chemical degradation kinetics on foliage:
  $C(t) = C_0 \cdot \exp\left(-\frac{\ln(2)}{t_{1/2}} \cdot t\right) = C_0 \cdot (0.5)^{t / t_{1/2}}$
- Safe re-entry / withholding intervals before releasing beneficial macro-biologics
- Toxicity categorization and mortality hazard assessment for Phytoseiulus persimilis,
  Encarsia formosa, and Neoseiulus californicus.
"""
import math
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class IobcToxicityRating(str, Enum):
    CLASS_1_HARMLESS = "harmless"  # < 25% beneficial mortality
    CLASS_2_SLIGHTLY_HARMFUL = "slightly_harmful"  # 25 - 50% mortality
    CLASS_3_MODERATELY_HARMFUL = "moderately_harmful"  # 51 - 75% mortality
    CLASS_4_HARMFUL = "harmful"  # > 75% mortality


class ActiveIngredientProfile(BaseModel):
    """Chemical and ecotoxicological profile of a crop protection active ingredient."""
    name: str
    chemical_group: str
    half_life_foliage_days: float = Field(..., gt=0.0)
    safe_threshold_ppm: float = Field(..., gt=0.0, description="Concentration below which beneficials survive unharmed")
    phytoseiulus_toxicity: IobcToxicityRating
    encarsia_toxicity: IobcToxicityRating
    typical_application_ppm: float = Field(..., gt=0.0)


class SprayApplication(BaseModel):
    """Log of a prior chemical or botanical spray application in a zone."""
    ingredient_name: str
    application_date_days_ago: float = Field(..., ge=0.0)
    initial_dose_ppm: float = Field(..., gt=0.0)


class SafetyClearanceReport(BaseModel):
    """Result of evaluating canopy safety for macro-biologic release."""
    target_beneficial: str
    is_safe_to_release: bool
    limiting_ingredient: str | None = None
    residual_concentration_ppm: float = 0.0
    safe_threshold_ppm: float = 0.0
    required_waiting_days_remaining: float = 0.0
    iobc_rating: IobcToxicityRating = IobcToxicityRating.CLASS_1_HARMLESS
    recommendation: str


class BiocontrolSafetyEngine:
    """
    Evaluates pesticide persistence and validates release safety for beneficial insects and mites.
    """

    INGREDIENT_DATABASE: ClassVar[dict[str, ActiveIngredientProfile]] = {
        "deltamethrin": ActiveIngredientProfile(
            name="deltamethrin",
            chemical_group="pyrethroid",
            half_life_foliage_days=5.5,
            safe_threshold_ppm=0.05,
            phytoseiulus_toxicity=IobcToxicityRating.CLASS_4_HARMFUL,
            encarsia_toxicity=IobcToxicityRating.CLASS_4_HARMFUL,
            typical_application_ppm=12.5,
        ),
        "abamectin": ActiveIngredientProfile(
            name="abamectin",
            chemical_group="avermectin",
            half_life_foliage_days=1.8,
            safe_threshold_ppm=0.10,
            phytoseiulus_toxicity=IobcToxicityRating.CLASS_3_MODERATELY_HARMFUL,
            encarsia_toxicity=IobcToxicityRating.CLASS_2_SLIGHTLY_HARMFUL,
            typical_application_ppm=3.6,
        ),
        "imidacloprid": ActiveIngredientProfile(
            name="imidacloprid",
            chemical_group="neonicotinoid",
            half_life_foliage_days=14.0,
            safe_threshold_ppm=0.02,
            phytoseiulus_toxicity=IobcToxicityRating.CLASS_4_HARMFUL,
            encarsia_toxicity=IobcToxicityRating.CLASS_4_HARMFUL,
            typical_application_ppm=25.0,
        ),
        "azadirachtin": ActiveIngredientProfile(
            name="azadirachtin",
            chemical_group="botanical_neem",
            half_life_foliage_days=0.9,
            safe_threshold_ppm=1.0,
            phytoseiulus_toxicity=IobcToxicityRating.CLASS_1_HARMLESS,
            encarsia_toxicity=IobcToxicityRating.CLASS_1_HARMLESS,
            typical_application_ppm=5.0,
        ),
        "bacillus_thuringiensis": ActiveIngredientProfile(
            name="bacillus_thuringiensis",
            chemical_group="microbial",
            half_life_foliage_days=0.5,
            safe_threshold_ppm=100.0,
            phytoseiulus_toxicity=IobcToxicityRating.CLASS_1_HARMLESS,
            encarsia_toxicity=IobcToxicityRating.CLASS_1_HARMLESS,
            typical_application_ppm=50.0,
        ),
    }

    @staticmethod
    def calculate_residual_concentration(
        initial_ppm: float,
        half_life_days: float,
        elapsed_days: float,
    ) -> float:
        """
        Calculates remaining concentration via first-order decay:
        C(t) = C0 * 0.5^(t / t_half)
        """
        if elapsed_days < 0.0 or half_life_days <= 0.0:
            return initial_ppm
        return round(initial_ppm * math.pow(0.5, elapsed_days / half_life_days), 4)

    @staticmethod
    def calculate_required_waiting_days(
        initial_ppm: float,
        target_safe_ppm: float,
        half_life_days: float,
    ) -> float:
        """
        Solves for time t where C(t) = safe_threshold:
        t = t_half * log2(C0 / safe_threshold) = t_half * ln(C0 / safe_threshold) / ln(2)
        """
        if initial_ppm <= target_safe_ppm or target_safe_ppm <= 0.0:
            return 0.0
        days = half_life_days * (math.log(initial_ppm / target_safe_ppm) / math.log(2.0))
        return round(max(0.0, days), 1)

    @classmethod
    def evaluate_release_safety(
        cls,
        spray_history: list[SprayApplication],
        target_beneficial: str = "phytoseiulus_persimilis",
    ) -> SafetyClearanceReport:
        """
        Validates whether all recent sprays have decayed below the beneficial safety threshold.
        """
        if not spray_history:
            return SafetyClearanceReport(
                target_beneficial=target_beneficial,
                is_safe_to_release=True,
                recommendation="Canopy is pristine with zero pesticide residues. Release authorized.",
            )

        worst_clearance = True
        worst_ingredient: str | None = None
        max_waiting_days_remaining = 0.0
        highest_iobc = IobcToxicityRating.CLASS_1_HARMLESS
        worst_residue = 0.0
        worst_threshold = 0.0

        for spray in spray_history:
            profile = cls.INGREDIENT_DATABASE.get(spray.ingredient_name.lower())
            if not profile:
                continue

            # Determine toxicity rating for target
            if "encarsia" in target_beneficial.lower():
                toxicity = profile.encarsia_toxicity
            else:
                toxicity = profile.phytoseiulus_toxicity

            if toxicity == IobcToxicityRating.CLASS_1_HARMLESS:
                continue

            current_residue = cls.calculate_residual_concentration(
                spray.initial_dose_ppm,
                profile.half_life_foliage_days,
                spray.application_date_days_ago,
            )

            total_days_needed = cls.calculate_required_waiting_days(
                spray.initial_dose_ppm,
                profile.safe_threshold_ppm,
                profile.half_life_foliage_days,
            )
            days_remaining = max(0.0, total_days_needed - spray.application_date_days_ago)

            if current_residue > profile.safe_threshold_ppm:
                worst_clearance = False
                if days_remaining > max_waiting_days_remaining:
                    max_waiting_days_remaining = round(days_remaining, 1)
                    worst_ingredient = profile.name
                    highest_iobc = toxicity
                    worst_residue = current_residue
                    worst_threshold = profile.safe_threshold_ppm

        if not worst_clearance:
            rec = (
                f"HOLD RELEASE: Toxic residues of {worst_ingredient} remain ({worst_residue:.3f} ppm vs safe "
                f"{worst_threshold:.3f} ppm). Must wait {max_waiting_days_remaining} more days."
            )
            return SafetyClearanceReport(
                target_beneficial=target_beneficial,
                is_safe_to_release=False,
                limiting_ingredient=worst_ingredient,
                residual_concentration_ppm=worst_residue,
                safe_threshold_ppm=worst_threshold,
                required_waiting_days_remaining=max_waiting_days_remaining,
                iobc_rating=highest_iobc,
                recommendation=rec,
            )

        return SafetyClearanceReport(
            target_beneficial=target_beneficial,
            is_safe_to_release=True,
            recommendation="All pesticide residues have decayed below lethal thresholds. Release authorized.",
        )
