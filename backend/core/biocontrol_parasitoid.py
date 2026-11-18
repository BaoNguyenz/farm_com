r"""
Parasitoid Wasp Bio-Dynamics, Emergence Kinetics & Whitefly Parasitism Model.

Implements biophysical kinetics for Encarsia formosa & Eretmocerus eremicus:
- Modified Nicholson-Bailey parasitism:
  $P_{\text{parasitized}} = N \cdot \left[1 - \exp\left(-\frac{a \cdot W}{1 + a \cdot T_h \cdot N}\right)\right]$
- Adult host-feeding mortality (puncturing young nymphs for protein)
- Temperature-dependent degree-day pupal emergence delay:
  $D = \frac{K_{\text{deg}}}{T - T_{\text{base}}}$
- Pupal scale blackening / mummification tracking and card introduction dosing
"""
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class ParasitoidSpecies(str, Enum):
    ENCARSIA_FORMOSA = "encarsia_formosa"
    ERETMOCERUS_EREMICUS = "eretmocerus_eremicus"


class ParasitoidBioParams(BaseModel):
    """Physiological parameters for parasitic micro-hymenoptera."""
    species: ParasitoidSpecies = ParasitoidSpecies.ENCARSIA_FORMOSA
    attack_rate_a: float = Field(0.08, ge=0.01, le=0.5, description="Searching efficiency per wasp (leaves/day)")
    handling_time_th: float = Field(0.05, ge=0.01, le=0.5, description="Oviposition handling time (days/nymph)")
    host_feeding_ratio: float = Field(0.20, ge=0.05, le=0.6, description="Ratio of nymphs killed by host-feeding vs oviposition")
    emergence_rate_pct: float = Field(92.0, ge=50.0, le=100.0, description="Pupal emergence success %")
    base_temp_c: float = Field(12.5, ge=5.0, le=18.0, description="Base developmental temperature")
    degree_days_to_emerge: float = Field(145.0, ge=80.0, le=300.0, description="Thermal degree-days for adult emergence")
    adult_lifespan_days: float = Field(12.0, ge=3.0, le=30.0, description="Adult female lifespan at 24C")


class WhiteflyColonyState(BaseModel):
    """Snapshot of whitefly infestation and parasitoid cohort in a canopy."""
    day: float = Field(0.0, ge=0.0)
    healthy_nymphs: float = Field(..., ge=0.0, description="Unparasitized whitefly nymphs per leaf")
    parasitized_pupae: float = Field(0.0, ge=0.0, description="Black/mummified pupae containing developing wasps")
    adult_wasps: float = Field(0.0, ge=0.0, description="Active adult female wasps per leaf")
    daily_parasitized: float = Field(0.0, ge=0.0)
    daily_host_feeding_kills: float = Field(0.0, ge=0.0)
    daily_emerged_wasps: float = Field(0.0, ge=0.0)
    parasitism_rate_pct: float = Field(0.0, ge=0.0, le=100.0)
    parasitoid_status: str = "established"


class ParasitoidKineticsEngine:
    """
    Simulates parasitoid wasp parasitism, host feeding, and pupal emergence kinetics.
    """

    SPECIES_PARAMS: ClassVar[dict[ParasitoidSpecies, ParasitoidBioParams]] = {
        ParasitoidSpecies.ENCARSIA_FORMOSA: ParasitoidBioParams(
            species=ParasitoidSpecies.ENCARSIA_FORMOSA,
            attack_rate_a=0.09,
            handling_time_th=0.045,
            host_feeding_ratio=0.22,
            emergence_rate_pct=93.0,
            base_temp_c=12.5,
            degree_days_to_emerge=140.0,
            adult_lifespan_days=14.0,
        ),
        ParasitoidSpecies.ERETMOCERUS_EREMICUS: ParasitoidBioParams(
            species=ParasitoidSpecies.ERETMOCERUS_EREMICUS,
            attack_rate_a=0.075,
            handling_time_th=0.05,
            host_feeding_ratio=0.30,
            emergence_rate_pct=88.0,
            base_temp_c=11.0,
            degree_days_to_emerge=160.0,
            adult_lifespan_days=10.0,
        ),
    }

    @classmethod
    def calculate_pupal_duration_days(cls, temp_c: float, params: ParasitoidBioParams) -> float:
        """
        Calculates days from oviposition to adult emergence using thermal time:
        Duration = DD / max(0.5, temp - T_base)
        """
        effective_temp = max(0.5, temp_c - params.base_temp_c)
        return round(params.degree_days_to_emerge / effective_temp, 1)

    @classmethod
    def calculate_parasitism_and_feeding(
        cls,
        nymphs: float,
        wasps: float,
        params: ParasitoidBioParams,
    ) -> tuple[float, float]:
        """
        Calculates number of nymphs parasitized and killed by host feeding per day.
        Uses modified Nicholson-Bailey functional response:
        parasitized = N * (1 - exp(- (a * W) / (1 + a * Th * N)))
        """
        if nymphs <= 0.0 or wasps <= 0.0:
            return 0.0, 0.0

        import math

        exponent = (params.attack_rate_a * wasps) / (1.0 + (params.attack_rate_a * params.handling_time_th * nymphs))
        fraction_attacked = 1.0 - math.exp(-exponent)
        total_attacked = min(nymphs, nymphs * fraction_attacked)

        # Host-feeding kills young nymphs directly without ovipositing
        host_feeding_kills = total_attacked * params.host_feeding_ratio
        parasitized_nymphs = total_attacked * (1.0 - params.host_feeding_ratio)

        return round(parasitized_nymphs, 4), round(host_feeding_kills, 4)

    @classmethod
    def simulate_step(
        cls,
        state: WhiteflyColonyState,
        temp_c: float = 24.0,
        params: ParasitoidBioParams | None = None,
        dt_days: float = 1.0,
    ) -> WhiteflyColonyState:
        """
        Integrates a single daily step for whitefly - parasitoid dynamics.
        """
        if params is None:
            params = cls.SPECIES_PARAMS[ParasitoidSpecies.ENCARSIA_FORMOSA]

        # Whitefly natural nymph reproduction if healthy
        r_whitefly = 0.18
        k_whitefly = 80.0
        nymph_reproduction = r_whitefly * state.healthy_nymphs * (1.0 - (state.healthy_nymphs / k_whitefly)) * dt_days

        # Parasitism and host-feeding
        daily_parasitized, daily_feeding = cls.calculate_parasitism_and_feeding(
            state.healthy_nymphs, state.adult_wasps, params
        )

        net_nymphs = max(0.0, state.healthy_nymphs + nymph_reproduction - daily_parasitized - daily_feeding)

        # Pupal emergence
        pupal_duration = cls.calculate_pupal_duration_days(temp_c, params)
        emergence_fraction = (1.0 / max(1.0, pupal_duration)) * (params.emergence_rate_pct / 100.0) * dt_days
        emerged_wasps = state.parasitized_pupae * emergence_fraction

        net_pupae = max(0.0, state.parasitized_pupae + daily_parasitized - emerged_wasps)

        # Adult wasp natural mortality
        mortality_rate = 1.0 / max(1.0, params.adult_lifespan_days)
        net_wasps = max(0.0, state.adult_wasps + emerged_wasps - (state.adult_wasps * mortality_rate * dt_days))

        total_nymphs_and_pupae = net_nymphs + net_pupae
        p_rate = (net_pupae / total_nymphs_and_pupae * 100.0) if total_nymphs_and_pupae > 0 else 0.0

        if p_rate >= 80.0:
            status = "optimal_control"
        elif p_rate >= 50.0:
            status = "satisfactory"
        else:
            status = "insufficient_parasitism"

        return WhiteflyColonyState(
            day=round(state.day + dt_days, 2),
            healthy_nymphs=round(net_nymphs, 3),
            parasitized_pupae=round(net_pupae, 3),
            adult_wasps=round(net_wasps, 3),
            daily_parasitized=round(daily_parasitized, 3),
            daily_host_feeding_kills=round(daily_feeding, 3),
            daily_emerged_wasps=round(emerged_wasps, 3),
            parasitism_rate_pct=round(p_rate, 2),
            parasitoid_status=status,
        )

    @classmethod
    def calculate_card_release_dose(
        cls,
        canopy_area_m2: float,
        nymph_density_per_leaf: float,
        economic_threshold: float = 3.0,
        pupae_per_card: int = 60,
    ) -> dict[str, float | int]:
        """
        Calculates recommended Encarsia formosa cardboard release tags.
        Standard agronomic dosage:
        - Low infestation (density <= ET): 1.5 wasps/m2
        - Moderate infestation (ET < density <= 2*ET): 3.0 wasps/m2
        - Heavy infestation (density > 2*ET): 6.0 wasps/m2
        """
        if nymph_density_per_leaf <= economic_threshold:
            wasps_per_m2 = 1.5
            strategy = "preventive"
        elif nymph_density_per_leaf <= (2.0 * economic_threshold):
            wasps_per_m2 = 3.5
            strategy = "curative_moderate"
        else:
            wasps_per_m2 = 6.5
            strategy = "curative_heavy"

        total_wasps_needed = canopy_area_m2 * wasps_per_m2
        total_cards = int(-(-total_wasps_needed // pupae_per_card))  # Ceiling division

        return {
            "wasps_per_m2": wasps_per_m2,
            "total_wasps_needed": round(total_wasps_needed, 0),
            "pupae_per_card": pupae_per_card,
            "total_cards_recommended": total_cards,
            "canopy_area_m2": canopy_area_m2,
            "strategy": strategy,
        }
