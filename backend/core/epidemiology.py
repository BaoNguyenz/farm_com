"""
Microclimate Fungal Pathogen Epidemiology & Disease Forecasting Engine.

Models sporulation, infection pressure, and zoospore mobility for major horticultural diseases:
1. Botrytis cinerea (Gray Mold) - Leaf wetness duration & temperature function (Broome et al.)
2. Phytophthora cactorum (Crown & Root Rot) - Soil waterlogging & soil temperature kinetics
3. Podosphaera aphanis (Powdery Mildew) - High humidity spore dispersal
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field

from backend.core.twin_state import PlotZone, WeatherTelemetry, FarmDigitalTwin


class PathogenRisk(BaseModel):
    """Specific pathogen risk assessment and biological control recommendation."""
    pathogen_name: str
    disease_common_name: str
    risk_score: float = Field(..., ge=0.0, le=100.0, description="0-100 severity index")
    risk_level: str = Field(..., description="low, moderate, high, critical")
    environmental_drivers: str
    bio_control_recommendation: str


class ZoneEpidemiologyProfile(BaseModel):
    """Pathology audit and biosecurity interventions for a specific plot zone."""
    zone_id: str
    crop_type: str
    max_risk_score: float
    primary_threat: str
    biosecurity_alert_level: str  # low, moderate, high, critical
    pathogen_risks: List[PathogenRisk]
    recommended_action: str


class EpidemiologyEngine:
    """
    Simulates disease dynamics based on microclimatic vectors and soil biophysics.
    """

    @classmethod
    def calculate_botrytis_risk(cls, temp_c: float, humidity_pct: float) -> PathogenRisk:
        """
        Calculates Gray Mold (Botrytis cinerea) infection pressure.
        Optimum infection window: 15°C to 24°C under high ambient humidity (>= 80% RH).
        """
        score = 0.0
        if humidity_pct >= 75.0 and 12.0 <= temp_c <= 28.0:
            # Quadratic temperature response peaking at 20°C
            temp_factor = max(0.0, 1.0 - ((temp_c - 20.0) / 8.0) ** 2)
            rh_factor = (humidity_pct - 75.0) / 25.0
            score = round(temp_factor * rh_factor * 100.0, 1)

        level = "low"
        if score >= 75.0:
            level = "critical"
        elif score >= 50.0:
            level = "high"
        elif score >= 25.0:
            level = "moderate"

        bio_control = (
            "Preventive bio-fungicide: Spray Bacillus subtilis QST 713 (Serenade ASO) at 2.5 L/ha. "
            "Ventilate canopy and avoid evening overhead irrigation."
        ) if score >= 40.0 else "Normal preventive sanitation; remove senescent leaves."

        return PathogenRisk(
            pathogen_name="Botrytis cinerea",
            disease_common_name="Thối trái mốc xám (Gray Mold)",
            risk_score=score,
            risk_level=level,
            environmental_drivers=f"Temp: {temp_c:.1f}°C, RH: {humidity_pct:.1f}%",
            bio_control_recommendation=bio_control
        )

    @classmethod
    def calculate_phytophthora_risk(cls, soil_temp_c: float, soil_moisture_pct: float) -> PathogenRisk:
        """
        Calculates Phytophthora cactorum (Crown/Root rot) risk.
        Requires saturated soil moisture (>75%) and warm root zone (18-28°C) for zoospore motile flagella.
        """
        score = 0.0
        if soil_moisture_pct >= 70.0 and soil_temp_c >= 16.0:
            moisture_factor = min(1.0, (soil_moisture_pct - 70.0) / 25.0)
            temp_factor = min(1.0, max(0.0, (soil_temp_c - 16.0) / 10.0))
            score = round(moisture_factor * temp_factor * 100.0, 1)

        level = "low"
        if score >= 75.0:
            level = "critical"
        elif score >= 50.0:
            level = "high"
        elif score >= 25.0:
            level = "moderate"

        bio_control = (
            "CRITICAL: Veto irrigation to allow root zone drainage. "
            "Drench root zone with Trichoderma asperellum T34 (0.5 g/L) and Potassium Phosphite (H2PO3-)."
        ) if score >= 35.0 else "Maintain aerobic root zone drainage; avoid over-watering."

        return PathogenRisk(
            pathogen_name="Phytophthora cactorum",
            disease_common_name="Thối thân & loét gốc (Crown Rot)",
            risk_score=score,
            risk_level=level,
            environmental_drivers=f"Soil moisture: {soil_moisture_pct:.1f}%, Soil temp: {soil_temp_c:.1f}°C",
            bio_control_recommendation=bio_control
        )

    @classmethod
    def calculate_powdery_mildew_risk(cls, temp_c: float, humidity_pct: float) -> PathogenRisk:
        """
        Calculates Powdery Mildew (Podosphaera aphanis) risk.
        Thrives under warm days (20-27°C) and moderate-to-high relative humidity (60-80%).
        """
        score = 0.0
        if 18.0 <= temp_c <= 28.0 and 55.0 <= humidity_pct <= 85.0:
            t_score = 1.0 - abs(temp_c - 23.0) / 7.0
            rh_score = 1.0 - abs(humidity_pct - 70.0) / 25.0
            score = round(max(0.0, t_score * rh_score) * 100.0, 1)

        level = "low"
        if score >= 70.0:
            level = "high"
        elif score >= 35.0:
            level = "moderate"

        bio_control = (
            "Apply potassium bicarbonate (Armicarb 3 g/L) or wettable sulfur (Thiovit Jet). "
            "Ensure morning sunlight penetration."
        ) if score >= 40.0 else "Canopy clear; monitor young tender leaves."

        return PathogenRisk(
            pathogen_name="Podosphaera aphanis",
            disease_common_name="Bệnh phấn trắng (Powdery Mildew)",
            risk_score=score,
            risk_level=level,
            environmental_drivers=f"Temp: {temp_c:.1f}°C, RH: {humidity_pct:.1f}%",
            bio_control_recommendation=bio_control
        )

    @classmethod
    def evaluate_zone_pathogens(
        cls,
        zone: PlotZone,
        weather: WeatherTelemetry
    ) -> ZoneEpidemiologyProfile:
        """Evaluates all disease vectors for a specific plot zone."""
        r_botrytis = cls.calculate_botrytis_risk(weather.temp_c, weather.humidity_percent)
        r_phyto = cls.calculate_phytophthora_risk(zone.soil_temp_c, zone.soil_moisture_pct)
        r_mildew = cls.calculate_powdery_mildew_risk(weather.temp_c, weather.humidity_percent)

        all_risks = [r_botrytis, r_phyto, r_mildew]
        primary = max(all_risks, key=lambda r: r.risk_score)

        return ZoneEpidemiologyProfile(
            zone_id=zone.id,
            crop_type=zone.crop_type,
            max_risk_score=primary.risk_score,
            primary_threat=f"{primary.pathogen_name} ({primary.disease_common_name})",
            biosecurity_alert_level=primary.risk_level,
            pathogen_risks=all_risks,
            recommended_action=primary.bio_control_recommendation
        )

    @classmethod
    def evaluate_farm_biosecurity(cls, farm: FarmDigitalTwin) -> Dict[str, Any]:
        """Audits farm-wide disease pressure and compiles biosecurity statistics."""
        profiles = [cls.evaluate_zone_pathogens(z, farm.current_weather) for z in farm.zones]

        high_risk_zones = [p.zone_id for p in profiles if p.biosecurity_alert_level in ("high", "critical")]
        max_threat = max(profiles, key=lambda p: p.max_risk_score) if profiles else None

        avg_score = round(sum(p.max_risk_score for p in profiles) / max(1, len(profiles)), 1)

        return {
            "farm_id": farm.farm_id,
            "total_zones_monitored": len(profiles),
            "high_risk_zones_count": len(high_risk_zones),
            "high_risk_zone_ids": high_risk_zones,
            "average_pathogen_risk_score": avg_score,
            "highest_threat": max_threat.model_dump() if max_threat else None,
            "zone_profiles": [p.model_dump() for p in profiles]
        }
