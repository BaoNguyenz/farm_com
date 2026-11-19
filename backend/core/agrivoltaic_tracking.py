r"""
Agrivoltaic Dual-Axis Sun-Tracking Kinematics & Astronomical Solar Position Algorithm (SPA).

Implements solar astronomy and tracker kinematics for elevated agrivoltaic canopies:
- Solar Declination: $\delta = 23.45^\circ \cdot \sin\left(\frac{360}{365} \cdot (d_n + 284)\right)$
- Equation of Time (EoT) and Local Solar Time (LST) calculation
- Solar Elevation ($\alpha$), Zenith ($\theta_z$), and Azimuth ($\gamma_s$) angles
- Inter-row self-shading prevention via Backtracking kinematics:
  $\beta_{\text{backtrack}} = \arcsin\left(\frac{L_{\text{pitch}}}{W_{\text{panel}}} \cdot \cos(\alpha)\right)$
- Angle of Incidence (AOI) and instantaneous photovoltaic generation:
  $P_{\text{PV}} = \eta \cdot A_{\text{PV}} \cdot G_{\text{eff}} \cdot \cos(\theta)$
"""
import math
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class TrackerMode(str, Enum):
    ASTRONOMICAL_MAX_POWER = "max_power"
    BACKTRACKING = "backtracking"
    DEFENSIVE_STOW_WIND = "stow_wind"
    FLAT_OVERCAST = "flat_overcast"


class SolarPosition(BaseModel):
    """Calculated astronomical solar vectors for a specific geographic coordinate."""
    day_of_year: int = Field(..., ge=1, le=366)
    local_hour: float = Field(..., ge=0.0, le=24.0)
    declination_deg: float
    equation_of_time_min: float
    local_solar_time_h: float
    hour_angle_deg: float
    elevation_deg: float
    zenith_deg: float
    azimuth_deg: float
    is_sun_up: bool


class AgrivoltaicTrackerConfig(BaseModel):
    """Structural engineering parameters of the elevated agrivoltaic tracker pergola."""
    latitude_deg: float = Field(11.94, description="Dalat / Central Highlands latitude")
    longitude_deg: float = Field(108.45, description="Dalat longitude")
    standard_meridian_deg: float = Field(105.0, description="Vietnam UTC+7 standard meridian")
    clearance_height_meters: float = Field(3.5, ge=2.0, le=6.0, description="Clearance height above crops for machinery/air circulation")
    panel_width_meters: float = Field(2.2, ge=1.0, le=4.0)
    row_pitch_meters: float = Field(6.5, ge=3.0, le=12.0, description="Center-to-center row spacing")
    max_tilt_deg: float = Field(55.0, ge=15.0, le=80.0, description="Mechanical actuator limit")
    panel_area_m2: float = Field(150.0, ge=10.0)
    installed_capacity_kwp: float = Field(30.0, ge=1.0)
    stc_efficiency: float = Field(0.21, ge=0.1, le=0.3)
    temp_coefficient_pct: float = Field(-0.35, ge=-0.6, le=-0.1)


class TrackerState(BaseModel):
    """Instantaneous operational orientation and energy generation of the tracker."""
    mode: TrackerMode
    panel_tilt_deg: float = Field(..., ge=-60.0, le=60.0)
    panel_azimuth_deg: float = Field(..., ge=0.0, le=360.0)
    angle_of_incidence_deg: float = Field(..., ge=0.0, le=180.0)
    incident_irradiance_w_m2: float = Field(..., ge=0.0)
    effective_irradiance_w_m2: float = Field(..., ge=0.0)
    generated_power_kw: float = Field(..., ge=0.0)
    is_backtracking_engaged: bool = False


class AgrivoltaicTrackingEngine:
    """
    Computes solar angles, mechanical tracker trajectories, and electrical PV output.
    """

    STC_NOCT_CELL_TEMP_DELTA_C: ClassVar[float] = 25.0

    @classmethod
    def calculate_solar_position(
        cls,
        day_of_year: int,
        local_hour: float,
        latitude_deg: float = 11.94,
        longitude_deg: float = 108.45,
        standard_meridian_deg: float = 105.0,
    ) -> SolarPosition:
        """
        Calculates exact astronomical position of the sun using Cooper and Spencer models.
        """
        # Solar Declination (Spencer/Cooper)
        declination_rad = math.radians(23.45 * math.sin(math.radians((360.0 / 365.0) * (day_of_year + 284))))
        declination_deg = math.degrees(declination_rad)

        # Equation of Time (EoT) in minutes
        b = math.radians((360.0 / 365.0) * (day_of_year - 81))
        eot_min = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)

        # Local Solar Time (LST)
        time_offset_hours = (eot_min / 60.0) + ((longitude_deg - standard_meridian_deg) / 15.0)
        lst_hours = (local_hour + time_offset_hours) % 24.0

        # Hour Angle (H): 0 at solar noon, negative morning, positive afternoon
        hour_angle_deg = (lst_hours - 12.0) * 15.0
        h_rad = math.radians(hour_angle_deg)
        lat_rad = math.radians(latitude_deg)

        # Solar Elevation Angle (alpha)
        sin_elev = (math.sin(lat_rad) * math.sin(declination_rad)) + (math.cos(lat_rad) * math.cos(declination_rad) * math.cos(h_rad))
        sin_elev = max(-1.0, min(1.0, sin_elev))
        elev_rad = math.asin(sin_elev)
        elev_deg = math.degrees(elev_rad)

        # Zenith Angle
        zenith_deg = max(0.0, 90.0 - elev_deg)

        # Solar Azimuth Angle (gamma_s, measured from North 0°, East 90°, South 180°, West 270°)
        if elev_deg <= 0.0 or zenith_deg >= 90.0:
            is_sun_up = False
            azimuth_deg = 180.0  # default
        else:
            is_sun_up = True
            cos_az = (math.sin(elev_rad) * math.sin(lat_rad) - math.sin(declination_rad)) / (math.cos(elev_rad) * math.cos(lat_rad))
            cos_az = max(-1.0, min(1.0, cos_az))
            az_raw_deg = math.degrees(math.acos(cos_az))
            if hour_angle_deg > 0.0:
                azimuth_deg = 360.0 - az_raw_deg
            else:
                azimuth_deg = az_raw_deg

        return SolarPosition(
            day_of_year=day_of_year,
            local_hour=local_hour,
            declination_deg=round(declination_deg, 3),
            equation_of_time_min=round(eot_min, 2),
            local_solar_time_h=round(lst_hours, 2),
            hour_angle_deg=round(hour_angle_deg, 2),
            elevation_deg=round(elev_deg, 2),
            zenith_deg=round(zenith_deg, 2),
            azimuth_deg=round(azimuth_deg, 2),
            is_sun_up=is_sun_up,
        )

    @classmethod
    def calculate_tracking_orientation(
        cls,
        solar_pos: SolarPosition,
        config: AgrivoltaicTrackerConfig,
        mode: TrackerMode = TrackerMode.ASTRONOMICAL_MAX_POWER,
        ghi_w_m2: float = 850.0,
        ambient_temp_c: float = 26.0,
    ) -> TrackerState:
        """
        Determines mechanical actuator tilt and azimuth angles, with backtracking collision protection.
        """
        if not solar_pos.is_sun_up:
            return TrackerState(
                mode=TrackerMode.FLAT_OVERCAST,
                panel_tilt_deg=0.0,
                panel_azimuth_deg=180.0,
                angle_of_incidence_deg=90.0,
                incident_irradiance_w_m2=0.0,
                effective_irradiance_w_m2=0.0,
                generated_power_kw=0.0,
                is_backtracking_engaged=False,
            )

        if mode in (TrackerMode.DEFENSIVE_STOW_WIND, TrackerMode.FLAT_OVERCAST):
            tilt_deg = 0.0
            azimuth_deg = 180.0
            is_backtrack = False
        else:
            # Single-axis North-South horizontal tracker with East-West tilt
            # Ideal unconstrained tilt towards sun azimuth
            ideal_tilt = solar_pos.zenith_deg if solar_pos.hour_angle_deg >= 0 else -solar_pos.zenith_deg

            # Ground Cover Ratio (GCR) = panel_width / row_pitch
            gcr = config.panel_width_meters / config.row_pitch_meters

            # Backtracking check: when sun elevation is low, shadow can cast onto next row
            is_backtrack = False
            tilt_deg = ideal_tilt

            if mode in (TrackerMode.BACKTRACKING, TrackerMode.ASTRONOMICAL_MAX_POWER) and solar_pos.elevation_deg < 35.0:
                cos_elev = math.cos(math.radians(solar_pos.elevation_deg))
                if cos_elev > 0.0:
                    backtrack_ratio = math.sin(math.radians(solar_pos.elevation_deg)) / gcr
                    backtrack_ratio = max(-1.0, min(1.0, backtrack_ratio))
                    backtrack_tilt = math.degrees(math.acos(backtrack_ratio))
                    if abs(ideal_tilt) > backtrack_tilt:
                        tilt_deg = backtrack_tilt if ideal_tilt > 0 else -backtrack_tilt
                        is_backtrack = True

            # Clamp to physical mechanical limit
            tilt_deg = max(-config.max_tilt_deg, min(config.max_tilt_deg, tilt_deg))
            azimuth_deg = 90.0 if tilt_deg < 0 else 270.0  # East or West tilt

        # Angle of Incidence (AOI)
        # cos(theta) = cos(zenith)*cos(tilt) + sin(zenith)*sin(tilt)*cos(gamma_s - gamma_t)
        z_rad = math.radians(solar_pos.zenith_deg)
        tilt_rad = math.radians(abs(tilt_deg))
        az_delta_rad = math.radians(solar_pos.azimuth_deg - azimuth_deg)

        cos_aoi = (math.cos(z_rad) * math.cos(tilt_rad)) + (math.sin(z_rad) * math.sin(tilt_rad) * math.cos(az_delta_rad))
        cos_aoi = max(0.0, min(1.0, cos_aoi))
        aoi_deg = math.degrees(math.acos(cos_aoi))

        # Effective irradiance on panel plane (POA - Plane of Array)
        poa_irradiance = ghi_w_m2 * cos_aoi

        # Temperature derating: T_cell = T_amb + 25 * (POA / 1000)
        cell_temp_c = ambient_temp_c + (cls.STC_NOCT_CELL_TEMP_DELTA_C * (poa_irradiance / 1000.0))
        temp_delta = cell_temp_c - 25.0
        temp_factor = 1.0 + (config.temp_coefficient_pct / 100.0) * temp_delta
        temp_factor = max(0.65, min(1.05, temp_factor))

        # Power calculation
        raw_power_kw = (config.panel_area_m2 * poa_irradiance * config.stc_efficiency * temp_factor) / 1000.0
        capped_power_kw = min(config.installed_capacity_kwp, max(0.0, raw_power_kw))

        return TrackerState(
            mode=mode,
            panel_tilt_deg=round(tilt_deg, 2),
            panel_azimuth_deg=round(azimuth_deg, 2),
            angle_of_incidence_deg=round(aoi_deg, 2),
            incident_irradiance_w_m2=round(ghi_w_m2, 1),
            effective_irradiance_w_m2=round(poa_irradiance, 1),
            generated_power_kw=round(capped_power_kw, 2),
            is_backtracking_engaged=is_backtrack,
        )

    @classmethod
    def simulate_day_tracking(
        cls,
        day_of_year: int,
        config: AgrivoltaicTrackerConfig | None = None,
        peak_ghi_w_m2: float = 900.0,
        ambient_temp_c: float = 27.0,
    ) -> list[TrackerState]:
        """
        Simulates an entire diurnal tracking profile from 06:00 to 18:00 at 1-hour resolution.
        """
        if config is None:
            config = AgrivoltaicTrackerConfig()

        states = []
        for h in range(6, 19):
            hour_float = float(h)
            pos = cls.calculate_solar_position(
                day_of_year=day_of_year,
                local_hour=hour_float,
                latitude_deg=config.latitude_deg,
                longitude_deg=config.longitude_deg,
                standard_meridian_deg=config.standard_meridian_deg,
            )

            # Bell-shaped GHI irradiance curve
            if pos.is_sun_up:
                ghi = peak_ghi_w_m2 * math.sin(math.radians(pos.elevation_deg))
                ghi = max(0.0, ghi)
            else:
                ghi = 0.0

            state = cls.calculate_tracking_orientation(
                solar_pos=pos,
                config=config,
                mode=TrackerMode.ASTRONOMICAL_MAX_POWER,
                ghi_w_m2=ghi,
                ambient_temp_c=ambient_temp_c,
            )
            states.append(state)

        return states
