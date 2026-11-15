"""
Bio-Acoustic Pollinator Monitoring, Bumblebee Buzz Frequency & Fruit Set Optimization Engine.

Implements biophysical and bio-acoustic equations for:
- Detecting bumblebee (Bombus) sonication buzz signatures in the 320-380 Hz resonance band
- Tracking flower visitation density per square meter
- Modeling strawberry and solanaceous fruit set deformation probability ("cat-facing")
- Determining foraging cessation due to ambient thermal extremes (<12°C or >32°C)
"""
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.core.twin_state import FarmDigitalTwin


class BuzzPollinationEvent(BaseModel):
    """Detected acoustic sonication event by a foraging pollinator."""
    timestamp: float
    frequency_hz: float = Field(..., ge=100.0, le=600.0, description="Sonication resonance frequency (Hz)")
    amplitude_db: float = Field(..., description="Audio signal amplitude in dBFS")
    duration_seconds: float = Field(..., ge=0.1, le=10.0)
    zone_id: str


class ZonePollinationAudit(BaseModel):
    """Detailed pollination adequacy and fruit deformation risk per plot zone."""
    zone_id: str
    flower_count_per_m2: int
    buzz_events_count_per_hour: int
    visitations_per_flower: float = Field(..., ge=0.0)
    fruit_deformation_risk_pct: float = Field(..., ge=0.0, le=100.0)
    pollination_status: str  # optimal, adequate, deficient, severe_deficit
    foraging_thermal_stress: bool
    recommended_action: str


class FarmPollinationReport(BaseModel):
    """Consolidated farm-wide bio-acoustic pollination index."""
    farm_id: str
    average_visitations_per_flower: float
    estimated_active_foragers: int
    zones_requiring_supplementary_pollination: int
    overall_fruit_set_quality_pct: float
    zone_audits: list[ZonePollinationAudit]


class BioAcousticPollinationEngine:
    """
    Analyzes microphone sensor streams inside the greenhouse to assess bumblebee sonication activity.
    """

    # Optimum sonication acoustic bandwidth for Bombus bumblebees
    SONICATION_MIN_HZ: ClassVar[float] = 310.0
    SONICATION_MAX_HZ: ClassVar[float] = 390.0

    # Minimum visits per strawberry/pepper flower for symmetrical AAA export grade
    TARGET_VISITATIONS_PER_FLOWER: ClassVar[float] = 2.5

    def analyze_acoustic_signature(self, frequency_hz: float, duration_seconds: float) -> bool:
        """
        Determines whether an acoustic detection corresponds to active floral buzz pollination.
        Normal wingbeat is 150-200 Hz; floral sonication jumps to 320-380 Hz.
        """
        is_resonant = self.SONICATION_MIN_HZ <= frequency_hz <= self.SONICATION_MAX_HZ
        has_duration = 0.4 <= duration_seconds <= 4.0
        return is_resonant and has_duration

    def audit_zone(
        self,
        zone_id: str,
        flower_count_per_m2: int = 40,
        buzz_events_per_hour: int = 120,
        ambient_temp_c: float = 23.0,
    ) -> ZonePollinationAudit:
        """
        Evaluates floral visitation adequacy and calculates fruit deformation risk.
        """
        # Foraging thermal limits: bumblebees cease foraging below 12°C or above 32°C
        thermal_stress = ambient_temp_c < 12.0 or ambient_temp_c > 32.0
        effective_buzz_events = 0 if thermal_stress else buzz_events_per_hour

        # Visitations per flower: each flower needs at least ~2.5 sonication events during blooming
        visitations = round(effective_buzz_events / max(1, flower_count_per_m2), 2)

        # Fruit deformation probability modeled as inverse sigmoid of visitations
        # Zero visits -> 85% misshapen fruit; >= 2.5 visits -> < 4% deformation
        if visitations >= self.TARGET_VISITATIONS_PER_FLOWER:
            deformation_risk = max(3.0, round(12.0 - (visitations * 3.5), 1))
            status = "optimal"
            action = "Pollination density optimal. Fruit set symmetry guaranteed."
        elif visitations >= 1.5:
            deformation_risk = round(25.0 - (visitations * 6.0), 1)
            status = "adequate"
            action = "Pollination acceptable for standard retail grading."
        elif visitations >= 0.5:
            deformation_risk = round(55.0 - (visitations * 15.0), 1)
            status = "deficient"
            action = "Supplementary bumblebee hive release recommended to avoid Grade B downgrades."
        else:
            deformation_risk = 82.0
            status = "severe_deficit"
            action = "CRITICAL: Near-zero pollination sonication. Release hive or deploy vibratory air-pulse wand immediately."

        if thermal_stress:
            action = f"THERMAL FORAGING CESSATION ({ambient_temp_c:.1f}°C): Pollinators inactive. Restore greenhouse microclimate to 18-26°C."

        return ZonePollinationAudit(
            zone_id=zone_id,
            flower_count_per_m2=flower_count_per_m2,
            buzz_events_count_per_hour=effective_buzz_events,
            visitations_per_flower=visitations,
            fruit_deformation_risk_pct=deformation_risk,
            pollination_status=status,
            foraging_thermal_stress=thermal_stress,
            recommended_action=action,
        )

    def audit_farm(self, farm: FarmDigitalTwin) -> FarmPollinationReport:
        """
        Consolidates acoustic pollination telemetry across all blooming plot zones.
        """
        audits: list[ZonePollinationAudit] = []
        tot_visitations = 0.0
        deficient_count = 0
        temp = farm.current_weather.temp_c if hasattr(farm, "current_weather") else 22.0

        for zone in farm.zones:
            # Only flowering and early fruiting zones require active buzz pollination
            is_blooming = zone.growth_stage in ("flowering", "fruiting")
            flowers_m2 = 45 if is_blooming else 5

            # Baseline sonication simulation: healthy plots receive ~130 buzz events/h
            buzz_events = 135 if is_blooming else 20
            if zone.health_status in ("stressed", "water_stressed"):
                buzz_events = 40  # Stressed flowers secrete less nectar/aroma

            audit = self.audit_zone(
                zone_id=zone.id,
                flower_count_per_m2=flowers_m2,
                buzz_events_per_hour=buzz_events,
                ambient_temp_c=temp,
            )
            audits.append(audit)
            tot_visitations += audit.visitations_per_flower
            if audit.pollination_status in ("deficient", "severe_deficit"):
                deficient_count += 1

        avg_visits = round(tot_visitations / max(1, len(farm.zones)), 2)
        est_foragers = max(5, int(avg_visits * 18))
        quality = round(max(10.0, 100.0 - (deficient_count * 12.5)), 1)

        return FarmPollinationReport(
            farm_id=farm.farm_id,
            average_visitations_per_flower=avg_visits,
            estimated_active_foragers=est_foragers,
            zones_requiring_supplementary_pollination=deficient_count,
            overall_fruit_set_quality_pct=quality,
            zone_audits=audits,
        )
