"""
Soil Microbiome Ecology, Nutrient Leaching Kinetics & Root Hypoxia Engine.

Implements biophysical models for:
- Beneficial soil bacterial and mycorrhizal fungal population kinetics (CFU/g)
- Nitrogen (NO3- / NH4+) percolation and gravitational leaching loss (Brooks-Corey flux)
- Root zone oxygen diffusion and waterlogging hypoxia stress index
- Soil Health Index (SHI) for regenerative agriculture and biological re-inoculation
"""

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.core.twin_state import FarmDigitalTwin, PlotZone


class MicrobialPopulationProfile(BaseModel):
    """Microbiological abundance and fungal root symbiosis metrics."""
    beneficial_bacteria_cfu_per_g: float = Field(2.5e7, ge=1e5, description="Aerobic heterotrophic bacteria CFU/g")
    mycorrhizae_colonization_pct: float = Field(65.0, ge=0.0, le=100.0, description="Arbuscular mycorrhizal root colonization %")
    soil_organic_matter_pct: float = Field(4.2, ge=0.5, le=15.0, description="Soil Organic Matter (SOM) percentage")
    trichoderma_cfu_per_g: float = Field(1.2e6, ge=0.0, description="Antagonistic fungal biocontrol density")
    soil_respiration_mg_co2_kg_day: float = Field(35.0, description="Soil microbial basal respiration rate")


class ZoneSoilEcologyAudit(BaseModel):
    """Detailed soil health, leaching vulnerability, and hypoxia state per zone."""
    zone_id: str
    crop_type: str
    soil_moisture_pct: float
    leaching_risk_tier: str  # minimal, moderate, critical_leaching
    estimated_leached_n_kg_ha: float
    root_hypoxia_index: float = Field(..., ge=0.0, le=1.0, description="0 = well-aerated, 1 = acute anaerobic hypoxia")
    soil_health_index: float = Field(..., ge=0.0, le=100.0, description="Composite microbiological vigor score")
    reinoculation_recommended: bool
    recommended_bio_treatment: str


class FarmSoilHealthReport(BaseModel):
    """Consolidated farm-wide soil ecology and leaching risk audit."""
    farm_id: str
    audit_timestamp_utc: str
    average_soil_health_index: float
    total_estimated_leached_n_kg: float
    zones_with_hypoxia_risk_count: int
    zones_with_leaching_risk_count: int
    zone_audits: list[ZoneSoilEcologyAudit]


class SoilMicrobiomeEngine:
    """
    Simulates microbial dynamics, nutrient mobility, and soil ecological equilibria.
    """

    # Saturated hydraulic conductivity for loam/sandy loam in Da Lat (mm/h)
    K_SAT_MM_H: ClassVar[float] = 22.0
    # Field capacity and saturation thresholds (%)
    FIELD_CAPACITY_PCT: ClassVar[float] = 68.0
    SATURATION_PCT: ClassVar[float] = 82.0

    def __init__(self, baseline_microbiome: MicrobialPopulationProfile | None = None) -> None:
        self.microbiome = baseline_microbiome or MicrobialPopulationProfile()

    def audit_zone(
        self,
        zone: PlotZone,
        percolation_hours: float = 1.0,
        nitrogen_pool_kg_ha: float = 45.0,
    ) -> ZoneSoilEcologyAudit:
        """
        Analyze moisture, microbial health, and leaching propensity for a plot zone.
        """
        moisture = zone.soil_moisture_pct

        # Leaching kinetics: Drainage occurs when moisture exceeds field capacity
        drainage_mm = 0.0
        leaching_tier = "minimal"
        leached_n_kg = 0.0

        if moisture > self.FIELD_CAPACITY_PCT:
            excess_ratio = (moisture - self.FIELD_CAPACITY_PCT) / (self.SATURATION_PCT - self.FIELD_CAPACITY_PCT)
            excess_ratio = min(1.5, max(0.0, excess_ratio))
            # Drainage rate increases non-linearly with excess water
            drainage_mm = round(self.K_SAT_MM_H * (excess_ratio**2) * percolation_hours, 2)

            # Nitrate ion mobility: ~0.08 kg N leached per mm of gravitational percolation
            leached_n_kg = round(min(nitrogen_pool_kg_ha * 0.4, drainage_mm * 0.08), 2)

            if drainage_mm >= 15.0 or leached_n_kg >= 1.2:
                leaching_tier = "critical_leaching"
            elif drainage_mm >= 4.0:
                leaching_tier = "moderate"

        # Root zone hypoxia: Oxygen diffusion drops exponentially in saturated soil
        hypoxia = 0.0
        if moisture >= self.SATURATION_PCT:
            hypoxia = round(min(1.0, (moisture - self.SATURATION_PCT) / (98.0 - self.SATURATION_PCT)), 2)
        elif moisture > 78.0:
            hypoxia = round((moisture - 78.0) * 0.05, 2)

        # Composite Soil Health Index (0-100)
        # Driven by biological population, balanced moisture, and lack of hypoxia
        base_score = 80.0
        if self.microbiome.mycorrhizae_colonization_pct > 60.0:
            base_score += 10.0
        if self.microbiome.soil_organic_matter_pct >= 4.0:
            base_score += 10.0

        # Penalties for extremes
        if hypoxia > 0.3:
            base_score -= hypoxia * 40.0
        if leaching_tier == "critical_leaching":
            base_score -= 25.0
        elif leaching_tier == "moderate":
            base_score -= 10.0
        if zone.health_status == "diseased":
            base_score -= 15.0

        shi = round(min(100.0, max(15.0, base_score)), 1)
        reinoculate = (
            shi < 70.0
            or hypoxia > 0.4
            or leaching_tier in ("moderate", "critical_leaching")
            or self.microbiome.trichoderma_cfu_per_g < 5e5
        )

        bio_action = "Routine bio-compost maintenance"
        if hypoxia > 0.5:
            bio_action = "Cease watering; aerate root zone and apply Trichoderma to suppress anaerobes"
        elif reinoculate:
            bio_action = "Inoculate mycorrhizal fungi spores and Bacillus subtilis consortium"
        elif leaching_tier == "critical_leaching":
            bio_action = "Pulse slow-release organic humic acid and chelated zinc"

        return ZoneSoilEcologyAudit(
            zone_id=zone.id,
            crop_type=zone.crop_type,
            soil_moisture_pct=round(moisture, 1),
            leaching_risk_tier=leaching_tier,
            estimated_leached_n_kg_ha=leached_n_kg,
            root_hypoxia_index=hypoxia,
            soil_health_index=shi,
            reinoculation_recommended=reinoculate,
            recommended_bio_treatment=bio_action,
        )

    def audit_farm(
        self,
        farm: FarmDigitalTwin,
        percolation_hours: float = 1.0,
    ) -> FarmSoilHealthReport:
        """Consolidate soil ecology across all plot zones."""
        audits: list[ZoneSoilEcologyAudit] = []
        tot_leached_n = 0.0
        shi_sum = 0.0
        hypoxia_count = 0
        leaching_count = 0

        for z in farm.zones:
            audit = self.audit_zone(z, percolation_hours=percolation_hours)
            audits.append(audit)
            tot_leached_n += audit.estimated_leached_n_kg_ha
            shi_sum += audit.soil_health_index
            if audit.root_hypoxia_index > 0.25:
                hypoxia_count += 1
            if audit.leaching_risk_tier in ("moderate", "critical_leaching"):
                leaching_count += 1

        zone_count = len(farm.zones) or 1
        avg_shi = round(shi_sum / zone_count, 1)

        return FarmSoilHealthReport(
            farm_id=farm.farm_id,
            audit_timestamp_utc=datetime.now(UTC).isoformat(),
            average_soil_health_index=avg_shi,
            total_estimated_leached_n_kg=round(tot_leached_n, 2),
            zones_with_hypoxia_risk_count=hypoxia_count,
            zones_with_leaching_risk_count=leaching_count,
            zone_audits=audits,
        )

    def simulate_microbiome_recovery(
        self,
        audit: ZoneSoilEcologyAudit,
        organic_amendment_kg: float = 50.0,
        bio_inoculant: bool = True,
    ) -> MicrobialPopulationProfile:
        """
        Simulate microbiological population resurgence following biological inoculation.
        """
        boost_factor = 1.0 + (min(200.0, organic_amendment_kg) / 100.0)
        inoculant_mult = 1.8 if bio_inoculant else 1.1

        new_bacteria = min(1e9, self.microbiome.beneficial_bacteria_cfu_per_g * boost_factor * inoculant_mult)
        new_mycorrhizae = min(95.0, self.microbiome.mycorrhizae_colonization_pct + (15.0 if bio_inoculant else 5.0))
        new_som = min(12.0, self.microbiome.soil_organic_matter_pct + (organic_amendment_kg * 0.01))
        new_trichoderma = min(1e7, self.microbiome.trichoderma_cfu_per_g * (2.5 if bio_inoculant else 1.2))
        new_resp = min(80.0, self.microbiome.soil_respiration_mg_co2_kg_day * boost_factor)

        return MicrobialPopulationProfile(
            beneficial_bacteria_cfu_per_g=round(new_bacteria, 0),
            mycorrhizae_colonization_pct=round(new_mycorrhizae, 1),
            soil_organic_matter_pct=round(new_som, 2),
            trichoderma_cfu_per_g=round(new_trichoderma, 0),
            soil_respiration_mg_co2_kg_day=round(new_resp, 1),
        )

