r"""
Biological Pest Control, Holling Type II Functional Response & Predator-Prey Population Kinetics.

Implements biophysical population dynamics for greenhouse macro-biologics:
- Holling Type II Functional Response: $N_a = \frac{a \cdot N}{1 + a \cdot T_h \cdot N} \cdot P$
- Lotka-Volterra with logistical prey carrying capacity:
  $\frac{dN}{dt} = r N (1 - \frac{N}{K}) - \frac{a N P}{1 + a T_h N}$
  $\frac{dP}{dt} = \frac{e a N P}{1 + a T_h N} - d P$
- Temperature-dependent metabolic scaling factor $f(T)$
- Target species: Phytoseiulus persimilis vs Tetranychus urticae (Two-spotted spider mite)
"""
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class PreySpecies(str, Enum):
    TWO_SPOTTED_SPIDER_MITE = "spider_mite"
    GREENHOUSE_WHITEFLY = "whitefly"
    WESTERN_FLOWER_THRIPS = "thrips"


class PredatorSpecies(str, Enum):
    PHYTOSEIULUS_PERSIMILIS = "phytoseiulus_persimilis"
    NEOSEIULUS_CALIFORNICUS = "neoseiulus_californicus"
    AMBLYSEIUS_SWIRSKII = "amblyseius_swirskii"


class PredatorBioParameters(BaseModel):
    """Physiological kinetics parameters for predatory macro-biologics."""
    species: PredatorSpecies = PredatorSpecies.PHYTOSEIULUS_PERSIMILIS
    attack_rate_a: float = Field(0.12, ge=0.01, le=1.0, description="Area of discovery / attack rate (leaves/day)")
    handling_time_th: float = Field(0.035, ge=0.005, le=0.5, description="Handling time per prey item (days)")
    conversion_efficiency_e: float = Field(0.28, ge=0.05, le=0.8, description="Prey to predator egg conversion ratio")
    natural_mortality_d: float = Field(0.12, ge=0.01, le=0.5, description="Daily natural starvation/mortality rate")
    t_opt_min_c: float = Field(22.0, ge=10.0, le=30.0)
    t_opt_max_c: float = Field(28.0, ge=20.0, le=35.0)


class PreyBioParameters(BaseModel):
    """Population growth parameters for crop pest prey."""
    species: PreySpecies = PreySpecies.TWO_SPOTTED_SPIDER_MITE
    intrinsic_growth_rate_r: float = Field(0.24, ge=0.05, le=0.6, description="Daily exponential reproductive rate")
    carrying_capacity_k: float = Field(120.0, ge=10.0, le=1000.0, description="Max prey carrying capacity per plant/leaf")
    economic_threshold_et: float = Field(5.0, ge=1.0, le=50.0, description="Scouting threshold (mites/leaf) requiring intervention")
    economic_injury_level_eil: float = Field(15.0, ge=2.0, le=100.0, description="Level causing measurable crop revenue loss")


class PopulationState(BaseModel):
    """Snapshot of pest and predator densities in a monitored zone."""
    day: float = Field(0.0, ge=0.0)
    prey_density: float = Field(..., ge=0.0, description="Pest individuals per sampling unit (leaf or plant)")
    predator_density: float = Field(..., ge=0.0, description="Predator individuals per sampling unit")
    daily_consumption: float = Field(0.0, ge=0.0, description="Prey consumed per sampling unit per day")
    prey_growth_rate: float = Field(0.0, description="Net dN/dt")
    predator_growth_rate: float = Field(0.0, description="Net dP/dt")
    suppression_status: str = "active"


class BiocontrolKineticsEngine:
    """
    Simulates predator-prey population kinetics under greenhouse microclimates.
    """

    DEFAULT_PREDATOR_PARAMS: ClassVar[dict[PredatorSpecies, PredatorBioParameters]] = {
        PredatorSpecies.PHYTOSEIULUS_PERSIMILIS: PredatorBioParameters(
            species=PredatorSpecies.PHYTOSEIULUS_PERSIMILIS,
            attack_rate_a=0.14,
            handling_time_th=0.03,
            conversion_efficiency_e=0.30,
            natural_mortality_d=0.10,
            t_opt_min_c=22.0,
            t_opt_max_c=27.0,
        ),
        PredatorSpecies.NEOSEIULUS_CALIFORNICUS: PredatorBioParameters(
            species=PredatorSpecies.NEOSEIULUS_CALIFORNICUS,
            attack_rate_a=0.09,
            handling_time_th=0.045,
            conversion_efficiency_e=0.22,
            natural_mortality_d=0.08,
            t_opt_min_c=18.0,
            t_opt_max_c=32.0,
        ),
        PredatorSpecies.AMBLYSEIUS_SWIRSKII: PredatorBioParameters(
            species=PredatorSpecies.AMBLYSEIUS_SWIRSKII,
            attack_rate_a=0.10,
            handling_time_th=0.04,
            conversion_efficiency_e=0.25,
            natural_mortality_d=0.09,
            t_opt_min_c=25.0,
            t_opt_max_c=32.0,
        ),
    }

    @staticmethod
    def temperature_scaling(temp_c: float, t_min: float = 12.0, t_opt_min: float = 22.0, t_opt_max: float = 28.0, t_max: float = 38.0) -> float:
        """
        Calculates metabolic temperature performance factor between 0.0 and 1.0.
        Uses a trapezoidal function with smooth ramp up and ramp down.
        """
        if temp_c <= t_min or temp_c >= t_max:
            return 0.05
        if t_opt_min <= temp_c <= t_opt_max:
            return 1.0
        if t_min < temp_c < t_opt_min:
            return 0.05 + 0.95 * ((temp_c - t_min) / (t_opt_min - t_min))
        # t_opt_max < temp_c < t_max
        return 0.05 + 0.95 * ((t_max - temp_c) / (t_max - t_opt_max))

    @classmethod
    def calculate_holling_type_ii_predation(
        cls,
        prey_n: float,
        predator_p: float,
        attack_rate: float,
        handling_time: float,
        temp_factor: float = 1.0,
    ) -> float:
        """
        Computes total prey consumed per unit time using Holling's Disc Equation:
        C = (a * N * P) / (1 + a * Th * N) * temp_factor
        """
        if prey_n <= 0.0 or predator_p <= 0.0:
            return 0.0
        effective_a = attack_rate * temp_factor
        denominator = 1.0 + (effective_a * handling_time * prey_n)
        return (effective_a * prey_n * predator_p) / denominator

    @classmethod
    def simulate_step(
        cls,
        current_state: PopulationState,
        predator_params: PredatorBioParameters,
        prey_params: PreyBioParameters,
        temp_c: float = 25.0,
        dt_days: float = 0.5,
    ) -> PopulationState:
        """
        Executes a single Runge-Kutta 2nd order (RK2 / Midpoint) integration step.
        """
        temp_scale = cls.temperature_scaling(
            temp_c,
            t_opt_min=predator_params.t_opt_min_c,
            t_opt_max=predator_params.t_opt_max_c,
        )

        n = current_state.prey_density
        p = current_state.predator_density

        def derivatives(density_n: float, density_p: float) -> tuple[float, float, float]:
            if density_n <= 0.0:
                dn = 0.0
                cons = 0.0
            else:
                cons = cls.calculate_holling_type_ii_predation(
                    density_n,
                    density_p,
                    predator_params.attack_rate_a,
                    predator_params.handling_time_th,
                    temp_scale,
                )
                logistic_growth = prey_params.intrinsic_growth_rate_r * density_n * (1.0 - (density_n / prey_params.carrying_capacity_k))
                dn = logistic_growth - cons

            dp = (predator_params.conversion_efficiency_e * cons) - (predator_params.natural_mortality_d * density_p)
            return dn, dp, cons

        # Midpoint step
        k1_n, k1_p, _cons1 = derivatives(n, p)
        n_mid = max(0.0, n + 0.5 * dt_days * k1_n)
        p_mid = max(0.0, p + 0.5 * dt_days * k1_p)

        k2_n, k2_p, cons2 = derivatives(n_mid, p_mid)

        new_n = max(0.0, n + dt_days * k2_n)
        new_p = max(0.0, p + dt_days * k2_p)

        # Suppression diagnosis
        if new_n <= 0.5:
            status = "eradicated"
        elif new_n <= prey_params.economic_threshold_et:
            status = "controlled"
        elif new_n <= prey_params.economic_injury_level_eil:
            status = "alert"
        else:
            status = "outbreak_damage"

        return PopulationState(
            day=round(current_state.day + dt_days, 2),
            prey_density=round(new_n, 4),
            predator_density=round(new_p, 4),
            daily_consumption=round(cons2, 4),
            prey_growth_rate=round(k2_n, 4),
            predator_growth_rate=round(k2_p, 4),
            suppression_status=status,
        )

    @classmethod
    def simulate_timeline(
        cls,
        initial_prey: float,
        initial_predator: float,
        days: int = 14,
        temp_c: float = 25.0,
        predator_species: PredatorSpecies = PredatorSpecies.PHYTOSEIULUS_PERSIMILIS,
        prey_species: PreySpecies = PreySpecies.TWO_SPOTTED_SPIDER_MITE,
        step_days: float = 0.5,
    ) -> list[PopulationState]:
        """
        Simulates population trajectories over multiple days.
        """
        pred_params = cls.DEFAULT_PREDATOR_PARAMS.get(
            predator_species,
            cls.DEFAULT_PREDATOR_PARAMS[PredatorSpecies.PHYTOSEIULUS_PERSIMILIS],
        )
        prey_params = PreyBioParameters(species=prey_species)

        state = PopulationState(
            day=0.0,
            prey_density=initial_prey,
            predator_density=initial_predator,
            daily_consumption=0.0,
            prey_growth_rate=0.0,
            predator_growth_rate=0.0,
            suppression_status="active",
        )

        timeline = [state]
        total_steps = int(days / step_days)
        for _ in range(total_steps):
            state = cls.simulate_step(
                current_state=state,
                predator_params=pred_params,
                prey_params=prey_params,
                temp_c=temp_c,
                dt_days=step_days,
            )
            timeline.append(state)
        return timeline
