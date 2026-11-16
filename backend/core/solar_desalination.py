r"""
Solar-Powered Brackish Water Reverse Osmosis (BWRO) & Membrane Flux Kinetics Engine.

Implements Solution-Diffusion membrane mass transport and solar thermodynamic equations:
- van 't Hoff osmotic pressure: $\pi = 0.00078 \cdot \text{TDS} \cdot (T_K / 298.15)$
- Permeate solvent flux: $J_w = A_w \cdot (P_{\text{feed}} - \Delta \pi)$
- Solute rejection: $R_s = (1 - C_p / C_f) \cdot 100\%$
- Specific Energy Consumption (SEC in $\text{kWh/m}^3$) with Energy Recovery Device (ERD)
- Direct solar PV variable-frequency drive matching to avoid grid tariffs
"""
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class WaterStream(BaseModel):
    """Physicochemical properties of an aqueous stream."""
    stream_name: str
    flow_rate_m3_h: float = Field(..., ge=0.0)
    tds_ppm: float = Field(..., ge=0.0, description="Total Dissolved Solids in mg/L")
    ec_ds_m: float = Field(..., ge=0.0, description="Electrical Conductivity in dS/m")
    temperature_c: float = Field(25.0, ge=5.0, le=50.0)


class DesalinationMetrics(BaseModel):
    """Operational membrane and thermodynamic performance indicators."""
    operating_pressure_bar: float
    osmotic_pressure_bar: float
    net_driving_pressure_bar: float
    permeate_flux_lmh: float
    recovery_ratio_pct: float
    salt_rejection_pct: float
    sec_kwh_m3: float
    erd_enabled: bool


class DesalinationBatchResult(BaseModel):
    """Comprehensive outcome of a solar RO desalination run."""
    feed_water: WaterStream
    permeate_water: WaterStream
    brine_reject_water: WaterStream
    metrics: DesalinationMetrics
    duration_hours: float
    total_permeate_m3: float
    total_brine_m3: float
    energy_consumed_kwh: float
    solar_coverage_pct: float
    is_safe_for_crops: bool
    status: str


class SolarDesalinationEngine:
    """
    Simulates reverse osmosis membrane separation powered by solar photovoltaic arrays.
    """

    # Spiral-wound thin film composite (TFC) membrane constants
    A_PERMEABILITY_LMH_BAR: ClassVar[float] = 1.85  # Pure water permeability coeff
    MEMBRANE_AREA_M2: ClassVar[float] = 40.0         # 4040 BWRO membrane active area
    MEMBRANE_SALT_REJECTION: ClassVar[float] = 99.2   # Nominal NaCl rejection %
    PUMP_MAX_POWER_KW: ClassVar[float] = 2.4        # High-pressure multi-stage booster pump
    MIN_SOLAR_KW_THRESHOLD: ClassVar[float] = 0.75   # Minimum PV power to initiate pumping

    # Crop salinity tolerance limits (TDS mg/L and EC dS/m)
    CROP_TDS_THRESHOLDS: ClassVar[dict[str, float]] = {
        "Strawberries": 450.0,    # Very salt sensitive (EC ~0.7 dS/m)
        "Bell Pepper": 750.0,     # Moderately sensitive (EC ~1.2 dS/m)
        "Arabica Coffee": 900.0,  # Moderately tolerant (EC ~1.4 dS/m)
        "Hydrangea": 650.0,       # Sensitive to root scorch (EC ~1.0 dS/m)
    }

    @staticmethod
    def calculate_osmotic_pressure(tds_ppm: float, temp_c: float = 25.0) -> float:
        """
        Calculates osmotic pressure (bar) from TDS using van 't Hoff relation:
        pi = 0.00078 * TDS * ((temp_c + 273.15) / 298.15)
        """
        temp_k = max(278.15, temp_c + 273.15)
        return round(0.00078 * max(0.0, tds_ppm) * (temp_k / 298.15), 2)

    @staticmethod
    def tds_to_ec(tds_ppm: float) -> float:
        """Approximates electrical conductivity (dS/m) from TDS ppm (1 dS/m ~ 640 ppm)."""
        return round(tds_ppm / 640.0, 2)

    def run_desalination_cycle(
        self,
        feed_tds_ppm: float = 2200.0,
        feed_volume_m3: float = 4.0,
        solar_available_kw: float = 2.5,
        target_pressure_bar: float = 14.0,
        use_erd: bool = True,
        water_temp_c: float = 24.0,
    ) -> DesalinationBatchResult:
        """
        Executes a solar RO membrane separation cycle based on real-time solar irradiance.
        """
        # 1. Solar power availability check
        solar_coverage = min(100.0, round((solar_available_kw / self.PUMP_MAX_POWER_KW) * 100.0, 1))
        if solar_available_kw < self.MIN_SOLAR_KW_THRESHOLD:
            # Insufficient solar power: low pressure standby
            feed_stream = WaterStream(
                stream_name="Feed Brackish Well",
                flow_rate_m3_h=0.0,
                tds_ppm=feed_tds_ppm,
                ec_ds_m=self.tds_to_ec(feed_tds_ppm),
                temperature_c=water_temp_c,
            )
            dummy_metrics = DesalinationMetrics(
                operating_pressure_bar=0.0,
                osmotic_pressure_bar=self.calculate_osmotic_pressure(feed_tds_ppm, water_temp_c),
                net_driving_pressure_bar=0.0,
                permeate_flux_lmh=0.0,
                recovery_ratio_pct=0.0,
                salt_rejection_pct=0.0,
                sec_kwh_m3=0.0,
                erd_enabled=use_erd,
            )
            return DesalinationBatchResult(
                feed_water=feed_stream,
                permeate_water=WaterStream(stream_name="Permeate", flow_rate_m3_h=0.0, tds_ppm=0.0, ec_ds_m=0.0),
                brine_reject_water=WaterStream(stream_name="Brine", flow_rate_m3_h=0.0, tds_ppm=0.0, ec_ds_m=0.0),
                metrics=dummy_metrics,
                duration_hours=0.0,
                total_permeate_m3=0.0,
                total_brine_m3=0.0,
                energy_consumed_kwh=0.0,
                solar_coverage_pct=solar_coverage,
                is_safe_for_crops=False,
                status="standby_insufficient_solar",
            )

        # 2. Operating pressure modulated by solar power
        # Full 2.4 kW achieves target pressure (14-16 bar); lower power throttles pump speed
        actual_pressure = round(min(target_pressure_bar, target_pressure_bar * (solar_available_kw / self.PUMP_MAX_POWER_KW)), 1)
        osmotic_pressure = self.calculate_osmotic_pressure(feed_tds_ppm, water_temp_c)

        # Net Driving Pressure: NDP = P_operating - pi_feed
        ndp = max(0.5, round(actual_pressure - osmotic_pressure, 2))

        # 3. Permeate Water Flux (LMH) & Volumetric Flow Rate
        flux_lmh = round(self.A_PERMEABILITY_LMH_BAR * ndp, 1)
        permeate_flow_m3_h = round((flux_lmh * self.MEMBRANE_AREA_M2) / 1000.0, 2)

        # 4. Recovery ratio: typically 70% for brackish water
        recovery_pct = 70.0
        feed_flow_m3_h = round(permeate_flow_m3_h / (recovery_pct / 100.0), 2)
        brine_flow_m3_h = round(feed_flow_m3_h - permeate_flow_m3_h, 2)

        # 5. Salt rejection and permeate quality
        permeate_tds = round(feed_tds_ppm * (1.0 - (self.MEMBRANE_SALT_REJECTION / 100.0)), 1)
        brine_tds = round((feed_tds_ppm * feed_flow_m3_h - permeate_tds * permeate_flow_m3_h) / max(0.1, brine_flow_m3_h), 1)

        # 6. Specific Energy Consumption (SEC in kWh/m3)
        # Baseline pump SEC ~ 2.4 kWh/m3; ERD (isobaric exchanger) recovers 40%
        base_sec = 2.45 * (actual_pressure / 15.0)
        sec = round(base_sec * (0.60 if use_erd else 1.0), 2)

        duration_hours = round(feed_volume_m3 / max(0.1, feed_flow_m3_h), 2)
        total_permeate = round(permeate_flow_m3_h * duration_hours, 2)
        total_brine = round(brine_flow_m3_h * duration_hours, 2)
        total_kwh = round(sec * total_permeate, 2)

        feed_stream = WaterStream(
            stream_name="Feed Brackish Groundwater",
            flow_rate_m3_h=feed_flow_m3_h,
            tds_ppm=feed_tds_ppm,
            ec_ds_m=self.tds_to_ec(feed_tds_ppm),
            temperature_c=water_temp_c,
        )
        permeate_stream = WaterStream(
            stream_name="Desalinated Permeate Water",
            flow_rate_m3_h=permeate_flow_m3_h,
            tds_ppm=permeate_tds,
            ec_ds_m=self.tds_to_ec(permeate_tds),
            temperature_c=water_temp_c,
        )
        brine_stream = WaterStream(
            stream_name="Concentrated Brine Reject",
            flow_rate_m3_h=brine_flow_m3_h,
            tds_ppm=brine_tds,
            ec_ds_m=self.tds_to_ec(brine_tds),
            temperature_c=water_temp_c,
        )

        metrics = DesalinationMetrics(
            operating_pressure_bar=actual_pressure,
            osmotic_pressure_bar=osmotic_pressure,
            net_driving_pressure_bar=ndp,
            permeate_flux_lmh=flux_lmh,
            recovery_ratio_pct=recovery_pct,
            salt_rejection_pct=self.MEMBRANE_SALT_REJECTION,
            sec_kwh_m3=sec,
            erd_enabled=use_erd,
        )

        is_safe = permeate_tds <= self.CROP_TDS_THRESHOLDS["Strawberries"]

        return DesalinationBatchResult(
            feed_water=feed_stream,
            permeate_water=permeate_stream,
            brine_reject_water=brine_stream,
            metrics=metrics,
            duration_hours=duration_hours,
            total_permeate_m3=total_permeate,
            total_brine_m3=total_brine,
            energy_consumed_kwh=total_kwh,
            solar_coverage_pct=solar_coverage,
            is_safe_for_crops=is_safe,
            status="active_desalination",
        )

    def assess_crop_salinity_hazard(self, raw_tds_ppm: float, crop_type: str = "Strawberries") -> dict[str, Any]:
        """
        Assesses osmotic root stress and yield penalty if irrigated with untreated water.
        """
        threshold = self.CROP_TDS_THRESHOLDS.get(crop_type, 600.0)
        exceeds = raw_tds_ppm > threshold
        excess_pct = round(max(0.0, ((raw_tds_ppm - threshold) / threshold) * 100.0), 1)

        # Maas-Hoffman yield reduction model: ~10% yield loss per 1.0 dS/m beyond threshold
        raw_ec = self.tds_to_ec(raw_tds_ppm)
        threshold_ec = self.tds_to_ec(threshold)
        yield_loss_pct = round(min(80.0, max(0.0, (raw_ec - threshold_ec) * 12.0)), 1)

        recommendation = (
            f"SALINITY HAZARD: Raw groundwater TDS ({raw_tds_ppm} ppm) exceeds {crop_type} tolerance ({threshold} ppm). "
            f"Projected yield loss {yield_loss_pct}%. Activate solar RO desalination immediately."
            if exceeds
            else f"Groundwater salinity ({raw_tds_ppm} ppm) acceptable for {crop_type}."
        )

        return {
            "crop_type": crop_type,
            "raw_tds_ppm": raw_tds_ppm,
            "crop_tds_threshold": threshold,
            "salinity_exceeded": exceeds,
            "excess_pct": excess_pct,
            "projected_yield_loss_pct": yield_loss_pct,
            "ro_treatment_required": exceeds,
            "recommendation": recommendation,
        }
