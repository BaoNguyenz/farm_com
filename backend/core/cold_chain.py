"""
Post-Harvest Cold-Chain Telemetry, Arrhenius Shelf-Life & Ethylene Kinetics Engine.

Implements biophysical equations for:
- Q10 temperature-dependent fruit respiration kinetics (mg CO2 / kg-h)
- Arrhenius marketable shelf-life degradation curve
- Ethylene (C2H4) senescence acceleration and transpirational fresh-weight dehydration
- Thermal abuse detection and controlled atmosphere chamber regulation
"""

from typing import ClassVar

from pydantic import BaseModel, Field


class ColdChamberState(BaseModel):
    """Real-time microclimate sensors inside a cold storage room or precooler."""
    chamber_id: str = "CHAMBER-A1"
    crop_type: str = "Strawberries"
    stored_weight_kg: float = Field(450.0, ge=0.0, description="Total fresh produce stored in chamber")
    air_temp_c: float = Field(3.5, description="Ambient air temperature inside chamber in °C")
    target_temp_c: float = Field(3.0, description="Set-point cold preservation temperature")
    relative_humidity_pct: float = Field(92.0, ge=20.0, le=100.0, description="Chamber relative humidity")
    ethylene_ppm: float = Field(0.08, ge=0.0, description="Ethylene C2H4 trace concentration in ppm")
    compressor_active: bool = True
    scrubber_active: bool = False
    hours_in_storage: float = Field(24.0, ge=0.0, description="Elapsed hours since harvest chamber entry")


class ShelfLifeProjection(BaseModel):
    """Remaining marketability and quality degradation metrics."""
    chamber_id: str
    crop_type: str
    remaining_shelf_life_days: float
    freshness_index_pct: float = Field(..., ge=0.0, le=100.0)
    respiration_rate_mg_co2_kg_h: float
    transpirational_weight_loss_pct: float
    ethylene_senescence_factor: float
    quality_grade: str  # AAA_PREMIUM_EXPORT, AA_FRESH_RETAIL, A_STANDARD, EXPEDITED_SALE_REQUIRED
    alert_action: str


class ColdChainEngine:
    """
    Simulates produce post-harvest respiration, shelf-life decay, and refrigeration dynamics.
    """

    # Crop post-harvest parameters: (optimal_temp_c, optimal_shelf_days, Q10, base_respiration_at_4C)
    CROP_POSTHARVEST_PROFILES: ClassVar[dict[str, dict[str, float]]] = {
        "Strawberries": {
            "optimal_temp_c": 2.0,
            "optimal_shelf_days": 12.0,
            "q10": 2.5,
            "base_resp_4c": 18.0,
            "ethylene_sensitivity": 1.4,
        },
        "Bell Peppers": {
            "optimal_temp_c": 7.0,
            "optimal_shelf_days": 21.0,
            "q10": 2.0,
            "base_resp_4c": 12.0,
            "ethylene_sensitivity": 1.1,
        },
        "Tomatoes": {
            "optimal_temp_c": 12.0,
            "optimal_shelf_days": 18.0,
            "q10": 1.9,
            "base_resp_4c": 10.0,
            "ethylene_sensitivity": 1.8,
        },
    }

    DEFAULT_PROFILE: ClassVar[dict[str, float]] = {
        "optimal_temp_c": 4.0,
        "optimal_shelf_days": 14.0,
        "q10": 2.2,
        "base_resp_4c": 15.0,
        "ethylene_sensitivity": 1.2,
    }

    def __init__(self) -> None:
        self.chambers: dict[str, ColdChamberState] = {
            "CHAMBER-A1": ColdChamberState(chamber_id="CHAMBER-A1", crop_type="Strawberries", stored_weight_kg=600.0, air_temp_c=3.2),
            "CHAMBER-B2": ColdChamberState(chamber_id="CHAMBER-B2", crop_type="Bell Peppers", stored_weight_kg=850.0, air_temp_c=7.5),
        }

    def evaluate_shelf_life(self, chamber: ColdChamberState) -> ShelfLifeProjection:
        """
        Calculate respiration, weight loss, and marketable shelf-life for a cold storage chamber.
        """
        profile = self.CROP_POSTHARVEST_PROFILES.get(chamber.crop_type, self.DEFAULT_PROFILE)

        temp_c = chamber.air_temp_c
        opt_t = profile["optimal_temp_c"]
        q10 = profile["q10"]
        base_resp = profile["base_resp_4c"]
        opt_days = profile["optimal_shelf_days"]

        # Respiration rate Q10 formulation: R(T) = R_base * Q10^((T - 4) / 10)
        temp_delta = temp_c - 4.0
        resp_rate = round(base_resp * (q10 ** (temp_delta / 10.0)), 2)

        # Ethylene senescence accelerator: higher ethylene reduces shelf life
        eth_factor = round(1.0 + (max(0.0, chamber.ethylene_ppm - 0.05) * profile["ethylene_sensitivity"] * 4.0), 3)

        # Temperature abuse factor: shelf life degrades exponentially above optimal temp
        thermal_abuse_ratio = max(1.0, 1.0 + (max(0.0, temp_c - opt_t) * 0.18))
        effective_shelf_days = opt_days / (thermal_abuse_ratio * eth_factor)

        # Days already spent in storage
        days_stored = chamber.hours_in_storage / 24.0
        remaining_days = round(max(0.0, effective_shelf_days - days_stored), 1)

        # Transpirational fresh weight loss %: driven by low humidity deficit
        vapor_deficit = max(0.0, (95.0 - chamber.relative_humidity_pct) / 100.0)
        weight_loss_pct = round(min(8.0, (vapor_deficit * 0.12 * days_stored) * 100.0), 2)

        # Freshness index (100% freshly harvested -> 0% unmarketable)
        freshness = round(max(0.0, min(100.0, (remaining_days / opt_days) * 100.0 - (weight_loss_pct * 3.0))), 1)

        # Quality tier grading
        if freshness >= 85.0 and remaining_days >= 7.0 and temp_c <= (opt_t + 2.0):
            grade = "AAA_PREMIUM_EXPORT"
            action = "Nominal storage conditions. Cold chain optimal."
        elif freshness >= 65.0 and remaining_days >= 4.0:
            grade = "AA_FRESH_RETAIL"
            action = "Stable for domestic supermarket distribution."
        elif freshness >= 40.0:
            grade = "A_STANDARD"
            action = "Schedule distribution within 48 hours."
        else:
            grade = "EXPEDITED_SALE_REQUIRED"
            action = "CRITICAL: Produce approaching senescence. Expedite immediate retail dispatch or flash freezing."

        return ShelfLifeProjection(
            chamber_id=chamber.chamber_id,
            crop_type=chamber.crop_type,
            remaining_shelf_life_days=remaining_days,
            freshness_index_pct=freshness,
            respiration_rate_mg_co2_kg_h=resp_rate,
            transpirational_weight_loss_pct=weight_loss_pct,
            ethylene_senescence_factor=eth_factor,
            quality_grade=grade,
            alert_action=action,
        )

    def audit_all_chambers(self) -> dict[str, list[ShelfLifeProjection]]:
        """Audit all cold room chambers."""
        projections = [self.evaluate_shelf_life(c) for c in self.chambers.values()]
        return {"chambers": projections}
