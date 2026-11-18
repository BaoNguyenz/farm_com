r"""
Moving Bed Biofilm Reactor (MBBR) Two-Stage Nitrification Biofilter Kinetics.

Implements biophysical equations for bacterial biological oxidation:
- Stage 1 (AOB - Nitrosomonas):
  $\text{NH}_4^+ + 1.5 \text{O}_2 \to \text{NO}_2^- + \text{H}_2\text{O} + 2 \text{H}^+$
  Consumes $3.43 \text{ mg } \text{O}_2 / \text{mg TAN}$
- Stage 2 (NOB - Nitrobacter / Nitrospira):
  $\text{NO}_2^- + 0.5 \text{O}_2 \to \text{NO}_3^-$
  Consumes $1.14 \text{ mg } \text{O}_2 / \text{mg } \text{NO}_2^-\text{-N}$
- Total stoichiometric $\text{O}_2$ demand: $4.57 \text{ mg } \text{O}_2 / \text{mg TAN}$
- Alkalinity destruction: $7.14 \text{ mg CaCO}_3$ per mg TAN oxidized
- Dual Monod substrate & dissolved oxygen limitation kinetics:
  $r = r_{\max} \cdot \frac{S}{K_s + S} \cdot \frac{\text{DO}}{K_{\text{DO}} + \text{DO}} \cdot f(T) \cdot f(\text{pH})$
"""
import math
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class BiofilterMediaType(str, Enum):
    K1_CARRIER = "k1_carrier"  # 800 m2/m3 protected surface area
    K3_CARRIER = "k3_carrier"  # 500 m2/m3
    CERAMIC_RINGS = "ceramic_rings"  # 600 m2/m3


class BiofilterState(BaseModel):
    """Hydraulic and water chemistry parameters of the biological filter."""
    reactor_id: str = "MBBR_BIOFILTER_01"
    media_type: BiofilterMediaType = BiofilterMediaType.K1_CARRIER
    media_volume_m3: float = Field(0.75, ge=0.05, description="Bulk volume of fluidised biomedia")
    active_surface_area_m2: float = Field(600.0, ge=10.0, description="Total bacterial biofilm attachment area")
    flow_rate_m3_h: float = Field(3.5, ge=0.1, description="Recirculating water turnover rate")
    inlet_tan_mg_l: float = Field(..., ge=0.0)
    inlet_no2_mg_l: float = Field(..., ge=0.0)
    inlet_no3_mg_l: float = Field(..., ge=0.0)
    outlet_tan_mg_l: float = Field(..., ge=0.0)
    outlet_no2_mg_l: float = Field(..., ge=0.0)
    outlet_no3_mg_l: float = Field(..., ge=0.0)
    tan_oxidation_rate_g_h: float = Field(..., ge=0.0)
    no2_oxidation_rate_g_h: float = Field(..., ge=0.0)
    oxygen_consumed_g_h: float = Field(..., ge=0.0)
    alkalinity_destroyed_g_h_caco3: float = Field(..., ge=0.0)
    dissolved_oxygen_mg_l: float = Field(..., ge=0.0)
    tan_conversion_efficiency_pct: float = Field(..., ge=0.0, le=100.0)
    is_do_inhibited: bool = False


class MBBRBiofilterEngine:
    """
    Simulates two-stage biofilm nitrification kinetics in a moving bed reactor.
    """

    # Monod half-velocity constants
    K_TAN_MG_L: ClassVar[float] = 0.50
    K_NO2_MG_L: ClassVar[float] = 0.65
    K_DO_AOB_MG_L: ClassVar[float] = 0.75
    K_DO_NOB_MG_L: ClassVar[float] = 1.20

    # Max specific surface nitrification rate (g TAN / m2 active biofilm / day at 25C)
    MAX_SURFACE_AOB_RATE_G_M2_DAY: ClassVar[float] = 0.75
    MAX_SURFACE_NOB_RATE_G_M2_DAY: ClassVar[float] = 0.85

    # Specific surface areas per media type in m2/m3
    MEDIA_SURFACE_AREAS: ClassVar[dict[BiofilterMediaType, float]] = {
        BiofilterMediaType.K1_CARRIER: 800.0,
        BiofilterMediaType.K3_CARRIER: 500.0,
        BiofilterMediaType.CERAMIC_RINGS: 600.0,
    }

    @classmethod
    def calculate_active_surface_area(cls, media_volume_m3: float, media_type: BiofilterMediaType) -> float:
        """Calculates total biofilm colonization area."""
        specific_area = cls.MEDIA_SURFACE_AREAS.get(media_type, 800.0)
        return round(media_volume_m3 * specific_area, 1)

    @staticmethod
    def calculate_environmental_multiplier(temp_c: float, ph: float) -> float:
        """
        Calculates temperature and pH performance scaling factors.
        Optimum: temp 24 - 28C, pH 7.0 - 7.6.
        """
        # Temperature factor (Arrhenius-type response: drops below 15C)
        if temp_c <= 10.0:
            temp_factor = 0.1
        elif temp_c >= 35.0:
            temp_factor = 0.4
        else:
            temp_factor = math.exp(0.065 * (temp_c - 25.0))
            temp_factor = min(1.2, max(0.2, temp_factor))

        # pH factor: Nitrifiers are inhibited in acidic water (pH < 6.5)
        if ph <= 5.8:
            ph_factor = 0.15
        elif ph <= 6.8:
            ph_factor = 0.15 + 0.65 * ((ph - 5.8) / 1.0)
        elif ph <= 7.8:
            ph_factor = 1.0
        else:
            ph_factor = max(0.3, 1.0 - (ph - 7.8) * 0.7)

        return round(temp_factor * ph_factor, 3)

    @classmethod
    def simulate_biofilter_step(
        cls,
        inlet_tan_mg_l: float,
        inlet_no2_mg_l: float,
        inlet_no3_mg_l: float,
        dissolved_oxygen_mg_l: float,
        water_flow_m3_h: float = 3.5,
        media_volume_m3: float = 0.75,
        media_type: BiofilterMediaType = BiofilterMediaType.K1_CARRIER,
        ph: float = 7.1,
        temp_c: float = 26.0,
        dt_hours: float = 1.0,
    ) -> BiofilterState:
        """
        Simulates two-stage Monod oxidation of TAN to NO2, and NO2 to NO3.
        """
        surface_area_m2 = cls.calculate_active_surface_area(media_volume_m3, media_type)
        env_factor = cls.calculate_environmental_multiplier(temp_c, ph)

        # DO limitation factors
        do_factor_aob = dissolved_oxygen_mg_l / (cls.K_DO_AOB_MG_L + dissolved_oxygen_mg_l)
        do_factor_nob = dissolved_oxygen_mg_l / (cls.K_DO_NOB_MG_L + dissolved_oxygen_mg_l)

        # Stage 1: AOB (TAN -> NO2)
        # Monod substrate factor
        tan_factor = inlet_tan_mg_l / (cls.K_TAN_MG_L + inlet_tan_mg_l) if inlet_tan_mg_l > 0 else 0.0
        # Rate in g TAN / h = (max_rate / 24) * area * tan_factor * do_factor * env
        aob_max_capacity_g_h = (cls.MAX_SURFACE_AOB_RATE_G_M2_DAY / 24.0) * surface_area_m2 * tan_factor * do_factor_aob * env_factor

        # Hourly incoming TAN mass in grams = inlet_tan_mg_l * m3 * 1000 / 1000 = inlet_tan * m3
        incoming_tan_mass_g = inlet_tan_mg_l * water_flow_m3_h * dt_hours
        tan_oxidized_g = min(incoming_tan_mass_g, aob_max_capacity_g_h * dt_hours)
        remaining_tan_mass_g = max(0.0, incoming_tan_mass_g - tan_oxidized_g)
        outlet_tan_mg_l = remaining_tan_mass_g / (water_flow_m3_h * dt_hours)

        # Stage 2: NOB (NO2 -> NO3)
        # Generated NO2 from AOB plus incoming NO2
        incoming_no2_mass_g = (inlet_no2_mg_l * water_flow_m3_h * dt_hours) + tan_oxidized_g
        available_no2_conc = incoming_no2_mass_g / (water_flow_m3_h * dt_hours)

        no2_factor = available_no2_conc / (cls.K_NO2_MG_L + available_no2_conc) if available_no2_conc > 0 else 0.0
        nob_max_capacity_g_h = (cls.MAX_SURFACE_NOB_RATE_G_M2_DAY / 24.0) * surface_area_m2 * no2_factor * do_factor_nob * env_factor

        no2_oxidized_g = min(incoming_no2_mass_g, nob_max_capacity_g_h * dt_hours)
        remaining_no2_mass_g = max(0.0, incoming_no2_mass_g - no2_oxidized_g)
        outlet_no2_mg_l = remaining_no2_mass_g / (water_flow_m3_h * dt_hours)

        # Nitrate mass accumulation (inlet NO3 + newly oxidized NO3)
        incoming_no3_mass_g = (inlet_no3_mg_l * water_flow_m3_h * dt_hours) + no2_oxidized_g
        outlet_no3_mg_l = incoming_no3_mass_g / (water_flow_m3_h * dt_hours)

        # Stoichiometric oxygen consumption:
        # AOB: 3.43 g O2 per g TAN oxidized
        # NOB: 1.14 g O2 per g NO2 oxidized
        oxygen_consumed_g = (3.43 * tan_oxidized_g) + (1.14 * no2_oxidized_g)

        # Alkalinity destruction: 7.14 g CaCO3 per g TAN oxidized
        alkalinity_destroyed_g_caco3 = 7.14 * tan_oxidized_g

        efficiency_pct = (tan_oxidized_g / incoming_tan_mass_g * 100.0) if incoming_tan_mass_g > 0 else 100.0
        is_do_inhibited = dissolved_oxygen_mg_l < 4.0

        return BiofilterState(
            reactor_id="MBBR_BIOFILTER_01",
            media_type=media_type,
            media_volume_m3=media_volume_m3,
            active_surface_area_m2=surface_area_m2,
            flow_rate_m3_h=water_flow_m3_h,
            inlet_tan_mg_l=round(inlet_tan_mg_l, 3),
            inlet_no2_mg_l=round(inlet_no2_mg_l, 3),
            inlet_no3_mg_l=round(inlet_no3_mg_l, 3),
            outlet_tan_mg_l=round(outlet_tan_mg_l, 3),
            outlet_no2_mg_l=round(outlet_no2_mg_l, 3),
            outlet_no3_mg_l=round(outlet_no3_mg_l, 3),
            tan_oxidation_rate_g_h=round(tan_oxidized_g / dt_hours, 2),
            no2_oxidation_rate_g_h=round(no2_oxidized_g / dt_hours, 2),
            oxygen_consumed_g_h=round(oxygen_consumed_g / dt_hours, 2),
            alkalinity_destroyed_g_h_caco3=round(alkalinity_destroyed_g_caco3 / dt_hours, 2),
            dissolved_oxygen_mg_l=round(dissolved_oxygen_mg_l, 2),
            tan_conversion_efficiency_pct=round(efficiency_pct, 1),
            is_do_inhibited=is_do_inhibited,
        )
