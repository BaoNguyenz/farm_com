r"""
Smart Rainwater Harvesting, Roof Catchment Runoff Hydrology & First-Flush Filtration Engine.

Implements hydrologic and environmental equations for:
- Rational Method runoff yield: $Q = (C \cdot I \cdot A) / 3.6$
- First-flush contaminant diversion kinetic ($1.0 - 1.5$ mm wash-off bypass)
- Multi-stage vortex sediment separation and disc filtration ($< 5$ NTU irrigation grade)
- Cistern reservoir level tracking and overflow spillway protection
"""
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class CatchmentSurface(BaseModel):
    """Properties of a rainwater collection surface."""
    surface_id: str = "GREENHOUSE_ROOF_A"
    area_m2: float = Field(1200.0, ge=10.0, description="Collection catchment footprint in m2")
    runoff_coefficient: float = Field(0.92, ge=0.1, le=1.0, description="Imperviousness coefficient C")
    material: str = "polycarbonate_glazing"


class RainwaterQuality(BaseModel):
    """Biophysical water quality parameters of collected rainwater."""
    turbidity_ntu: float = Field(..., ge=0.0, description="Nephelometric Turbidity Units")
    ec_ds_m: float = Field(0.06, ge=0.01, description="Electrical conductivity in dS/m (rainwater is ultra-pure)")
    ph: float = Field(6.5, ge=4.0, le=9.0)
    irrigation_ready: bool


class CisternStorage(BaseModel):
    """Storage status of rainwater retention cisterns."""
    capacity_liters: float = Field(150000.0, ge=1000.0)
    current_liters: float = Field(45000.0, ge=0.0)
    fill_percentage: float = Field(30.0, ge=0.0, le=100.0)
    is_spilling_overflow: bool = False


class HarvestEventReport(BaseModel):
    """Yield and water quality summary for a precipitation event."""
    rainfall_mm: float
    duration_hours: float
    gross_catchment_volume_liters: float
    first_flush_diverted_liters: float
    net_harvested_liters: float
    cistern_storage_after: CisternStorage
    water_quality: RainwaterQuality
    overflow_spilled_liters: float = 0.0


class RainwaterHarvestingEngine:
    """
    Simulates catchment hydrology, contaminant first-flush bypass, and cistern retention.
    """

    # First 1.2 mm of rainfall washes bird droppings, dust, and pollen off roofs
    FIRST_FLUSH_DEPTH_MM: ClassVar[float] = 1.2
    # Turbidity reduction efficiency of vortex hydrocyclone + disc filter
    FILTRATION_EFFICIENCY_PCT: ClassVar[float] = 88.0

    def __init__(
        self,
        catchment: CatchmentSurface | None = None,
        cistern_capacity_liters: float = 150000.0,
        initial_storage_liters: float = 45000.0,
    ) -> None:
        self.catchment = catchment or CatchmentSurface()
        self.cistern_capacity = cistern_capacity_liters
        self.current_storage_liters = min(cistern_capacity_liters, initial_storage_liters)

    def calculate_peak_runoff_rate(self, rainfall_intensity_mm_h: float) -> float:
        """
        Calculates peak runoff flow rate using the Rational Method:
        Q (m3/h) = (C * I * A) / 1000
        """
        if rainfall_intensity_mm_h <= 0.0:
            return 0.0
        return round((self.catchment.runoff_coefficient * rainfall_intensity_mm_h * self.catchment.area_m2) / 1000.0, 2)

    def process_precipitation_event(
        self,
        rainfall_mm: float,
        duration_hours: float = 1.0,
        raw_turbidity_ntu: float = 38.0,
    ) -> HarvestEventReport:
        """
        Simulates a rain event: first-flush separation, disc filtration, and storage update.
        """
        if rainfall_mm <= 0.0 or duration_hours <= 0.0:
            return HarvestEventReport(
                rainfall_mm=0.0,
                duration_hours=duration_hours,
                gross_catchment_volume_liters=0.0,
                first_flush_diverted_liters=0.0,
                net_harvested_liters=0.0,
                cistern_storage_after=self.get_cistern_status(),
                water_quality=RainwaterQuality(turbidity_ntu=2.0, ec_ds_m=0.05, ph=6.6, irrigation_ready=True),
                overflow_spilled_liters=0.0,
            )

        # Gross rainfall volume landing on catchment (1 mm * 1 m2 = 1 Liter)
        gross_volume_liters = rainfall_mm * self.catchment.area_m2 * self.catchment.runoff_coefficient

        # First flush diversion volume: washes roof before feeding cistern
        first_flush_depth = min(rainfall_mm, self.FIRST_FLUSH_DEPTH_MM)
        first_flush_liters = first_flush_depth * self.catchment.area_m2 * self.catchment.runoff_coefficient

        # Net collectible clean rainwater
        net_collected_liters = max(0.0, gross_volume_liters - first_flush_liters)

        # Sediment filtration reduces turbidity
        post_filter_turbidity = round(raw_turbidity_ntu * (1.0 - (self.FILTRATION_EFFICIENCY_PCT / 100.0)), 1)
        irrigation_ready = post_filter_turbidity <= 10.0

        # Update cistern retention
        overflow_liters = 0.0
        potential_storage = self.current_storage_liters + net_collected_liters
        if potential_storage > self.cistern_capacity:
            overflow_liters = round(potential_storage - self.cistern_capacity, 1)
            self.current_storage_liters = self.cistern_capacity
        else:
            self.current_storage_liters = round(potential_storage, 1)

        cistern_status = self.get_cistern_status(is_spilling=(overflow_liters > 0.0))

        quality = RainwaterQuality(
            turbidity_ntu=post_filter_turbidity,
            ec_ds_m=0.05,
            ph=6.5,
            irrigation_ready=irrigation_ready,
        )

        return HarvestEventReport(
            rainfall_mm=rainfall_mm,
            duration_hours=duration_hours,
            gross_catchment_volume_liters=round(gross_volume_liters, 1),
            first_flush_diverted_liters=round(first_flush_liters, 1),
            net_harvested_liters=round(net_collected_liters, 1),
            cistern_storage_after=cistern_status,
            water_quality=quality,
            overflow_spilled_liters=overflow_liters,
        )

    def withdraw_water(self, volume_liters: float) -> float:
        """
        Discharges rainwater for irrigation or fertigation blending.
        Returns actual volume discharged in liters.
        """
        withdrawn = min(volume_liters, self.current_storage_liters)
        self.current_storage_liters = round(self.current_storage_liters - withdrawn, 1)
        return withdrawn

    def get_cistern_status(self, is_spilling: bool = False) -> CisternStorage:
        """Returns instantaneous cistern storage metrics."""
        pct = round((self.current_storage_liters / self.cistern_capacity) * 100.0, 1)
        return CisternStorage(
            capacity_liters=self.cistern_capacity,
            current_liters=self.current_storage_liters,
            fill_percentage=pct,
            is_spilling_overflow=is_spilling,
        )

    def get_system_summary(self) -> dict[str, Any]:
        """Provides consolidated state for agent deliberation and API consumption."""
        cistern = self.get_cistern_status()
        return {
            "catchment_id": self.catchment.surface_id,
            "catchment_area_m2": self.catchment.area_m2,
            "runoff_coefficient": self.catchment.runoff_coefficient,
            "cistern_capacity_liters": cistern.capacity_liters,
            "current_storage_liters": cistern.current_liters,
            "fill_percentage": cistern.fill_percentage,
            "first_flush_depth_mm": self.FIRST_FLUSH_DEPTH_MM,
            "water_ec_ds_m": 0.05,
        }
