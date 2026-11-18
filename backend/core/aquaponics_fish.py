r"""
Fish Bio-Energetics, Metabolic Waste & Total Ammonia Nitrogen (TAN) Excretion Kinetics.

Implements biophysical equations for Recirculating Aquaculture Systems (RAS) / Aquaponics:
- Tilapia (Oreochromis niloticus) metabolic feed conversion & biomass scaling
- Total Ammonia Nitrogen (TAN) production from protein catabolism:
  $\text{TAN}_{\text{day}} = \text{Feed} \cdot \text{Protein} \cdot 0.092$
- Emerson formula for toxic un-ionized ammonia fraction:
  $pK_a = \frac{2729.92}{T_K} + 0.09018$
  $f_{NH_3} = \frac{1}{10^{(pK_a - pH)} + 1}$
  $[NH_3] = f_{NH_3} \cdot [\text{TAN}]$
- Respiratory dissolved oxygen consumption ($250 - 400 \text{ mg } O_2/\text{kg}\cdot\text{h}$)
"""
import math
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class FishSpecies(str, Enum):
    NILE_TILAPIA = "nile_tilapia"
    RED_TILAPIA = "red_tilapia"
    BARRAMUNDI = "barramundi"


class FishTankState(BaseModel):
    """Real-time biophysical state of the aquaculture rearing tank."""
    tank_id: str = "TANK_TILAPIA_01"
    species: FishSpecies = FishSpecies.NILE_TILAPIA
    fish_count: int = Field(500, ge=1)
    avg_weight_grams: float = Field(450.0, ge=10.0, le=3000.0)
    total_biomass_kg: float = Field(225.0, ge=1.0)
    water_volume_m3: float = Field(5.0, ge=0.5, le=50.0)
    water_temp_c: float = Field(26.5, ge=15.0, le=35.0)
    ph: float = Field(7.0, ge=5.5, le=9.0)
    dissolved_oxygen_mg_l: float = Field(6.2, ge=0.0, le=15.0)
    tan_mg_l: float = Field(0.40, ge=0.0, description="Total Ammonia Nitrogen NH3 + NH4+")
    toxic_nh3_mg_l: float = Field(0.015, ge=0.0, description="Un-ionized toxic ammonia NH3")
    is_ammonia_alarm: bool = False
    is_hypoxia_alarm: bool = False


class FeedingEvent(BaseModel):
    """Record of feed administration and resulting nitrogenous load."""
    feed_amount_kg: float = Field(..., gt=0.0)
    crude_protein_pct: float = Field(32.0, ge=20.0, le=55.0)
    tan_generated_grams: float
    immediate_oxygen_demand_grams: float
    resulting_tan_mg_l: float
    resulting_toxic_nh3_mg_l: float


class FishBioenergeticsEngine:
    """
    Simulates fish metabolism, feed conversion, TAN excretion, and oxygen demand.
    """

    # Lethal toxic NH3 threshold for Tilapia is ~0.5 mg/L; warning threshold is 0.05 mg/L
    TOXIC_NH3_WARNING_MG_L: ClassVar[float] = 0.05
    # Critical hypoxia threshold for Tilapia is <3.0 mg/L; optimal is >5.0 mg/L
    HYPOXIA_CRITICAL_MG_L: ClassVar[float] = 3.5

    @staticmethod
    def calculate_unionized_ammonia_fraction(ph: float, temp_c: float) -> float:
        """
        Emerson et al. (1975) equation for un-ionized ammonia (NH3) equilibrium fraction:
        pKa = 2729.92 / (temp_c + 273.15) + 0.09018
        fraction = 1.0 / (10^(pKa - pH) + 1.0)
        """
        temp_k = temp_c + 273.15
        p_ka = (2729.92 / temp_k) + 0.09018
        exponent = p_ka - ph
        return 1.0 / (math.pow(10.0, exponent) + 1.0)

    @classmethod
    def calculate_toxic_nh3_concentration(cls, tan_mg_l: float, ph: float, temp_c: float) -> float:
        """Computes toxic un-ionized NH3 from total ammonia nitrogen."""
        fraction = cls.calculate_unionized_ammonia_fraction(ph, temp_c)
        return round(tan_mg_l * fraction, 4)

    @staticmethod
    def calculate_daily_feeding_requirement(
        biomass_kg: float,
        water_temp_c: float,
        base_rate_pct: float = 2.0,
    ) -> float:
        """
        Calculates recommended daily feed intake based on biomass and temperature.
        Tilapia appetite peaks around 26-29°C; drops below 20°C or above 34°C.
        """
        if water_temp_c < 18.0:
            temp_mult = 0.3
        elif 18.0 <= water_temp_c < 24.0:
            temp_mult = 0.7 + 0.3 * ((water_temp_c - 18.0) / 6.0)
        elif 24.0 <= water_temp_c <= 30.0:
            temp_mult = 1.0
        else:
            temp_mult = max(0.4, 1.0 - (water_temp_c - 30.0) * 0.15)

        feed_kg = biomass_kg * (base_rate_pct / 100.0) * temp_mult
        return round(feed_kg, 2)

    @staticmethod
    def calculate_tan_excretion(feed_kg: float, crude_protein_pct: float = 32.0) -> float:
        """
        Timmons & Ebeling aquaculture bio-energetics formula:
        TAN (grams) = Feed (kg) * Protein (%) * 0.092 * 10
        For 1 kg of 32% protein feed: 1.0 * 32.0 * 0.092 * 10 = ~29.44 g TAN.
        """
        if feed_kg <= 0.0:
            return 0.0
        return round(feed_kg * crude_protein_pct * 0.092 * 10.0, 2)

    @staticmethod
    def calculate_respiratory_oxygen_demand(
        biomass_kg: float,
        duration_hours: float = 1.0,
        post_feeding_spike: bool = True,
    ) -> float:
        """
        Computes metabolic oxygen consumption (grams of O2):
        Resting rate: ~250 mg O2 / kg biomass / hour
        Post-prandial (feeding) rate: ~380 mg O2 / kg biomass / hour
        """
        rate_mg_kg_h = 380.0 if post_feeding_spike else 250.0
        total_mg = biomass_kg * rate_mg_kg_h * duration_hours
        return round(total_mg / 1000.0, 2)  # Convert to grams

    @classmethod
    def apply_feeding_event(
        cls,
        state: FishTankState,
        feed_kg: float,
        crude_protein_pct: float = 32.0,
    ) -> tuple[FishTankState, FeedingEvent]:
        """
        Simulates feed consumption, resulting TAN spike in tank water, and oxygen draw.
        """
        tan_grams = cls.calculate_tan_excretion(feed_kg, crude_protein_pct)
        o2_demand_grams = cls.calculate_respiratory_oxygen_demand(state.total_biomass_kg, duration_hours=2.0)

        # Additional TAN in mg/L (grams * 1000 / liters = grams / m3)
        delta_tan_mg_l = tan_grams / state.water_volume_m3

        # Update TAN and toxic NH3
        new_tan = state.tan_mg_l + delta_tan_mg_l
        toxic_nh3 = cls.calculate_toxic_nh3_concentration(new_tan, state.ph, state.water_temp_c)

        # Dissolved oxygen transient depression buffered by continuous tank aeration
        delta_do_mg_l = o2_demand_grams / state.water_volume_m3
        transient_drop = min(1.5, 0.05 * delta_do_mg_l)
        new_do = max(0.5, state.dissolved_oxygen_mg_l - transient_drop)

        is_nh3_alarm = toxic_nh3 >= cls.TOXIC_NH3_WARNING_MG_L
        is_hypo_alarm = new_do < cls.HYPOXIA_CRITICAL_MG_L

        # Slight growth update (FCR = 1.4: 1.4 kg feed produces 1.0 kg biomass)
        biomass_gain_kg = feed_kg / 1.4
        new_biomass = round(state.total_biomass_kg + (biomass_gain_kg * 0.5), 2)
        new_avg_wt = round((new_biomass * 1000.0) / state.fish_count, 1)

        new_state = FishTankState(
            tank_id=state.tank_id,
            species=state.species,
            fish_count=state.fish_count,
            avg_weight_grams=new_avg_wt,
            total_biomass_kg=new_biomass,
            water_volume_m3=state.water_volume_m3,
            water_temp_c=state.water_temp_c,
            ph=state.ph,
            dissolved_oxygen_mg_l=round(new_do, 2),
            tan_mg_l=round(new_tan, 3),
            toxic_nh3_mg_l=round(toxic_nh3, 4),
            is_ammonia_alarm=is_nh3_alarm,
            is_hypoxia_alarm=is_hypo_alarm,
        )

        event = FeedingEvent(
            feed_amount_kg=feed_kg,
            crude_protein_pct=crude_protein_pct,
            tan_generated_grams=tan_grams,
            immediate_oxygen_demand_grams=o2_demand_grams,
            resulting_tan_mg_l=round(new_tan, 3),
            resulting_toxic_nh3_mg_l=round(toxic_nh3, 4),
        )

        return new_state, event
