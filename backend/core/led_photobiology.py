"""
Dynamic LED Photobiology, Daily Light Integral (DLI) & Phytochrome Spectrum Engine.

Models horticultural solid-state lighting for vertical aeroponics & CEA greenhouses:
- Daily Light Integral (DLI) accumulation from PPFD (umol/m^2/s) and photoperiod.
- Red (660nm), Blue (450nm), and Far-Red (730nm) spectrum recipe optimization.
- Phytochrome Photostationary State (PSS) estimation to prevent shade-avoidance stretching.
- Supplemental LED power & EVN tariff-aware dimming controller (efficacy 2.8 umol/J).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class PhotobiologyRecipe(str, Enum):
    """Growth-stage specific LED spectral profiles."""
    VEGETATIVE_COMPACT = "vegetative_compact"      # High Blue (25% B, 70% R, 5% FR)
    FLOWERING_ANTHOCYANIN = "flowering_anthocyanin"  # High Red + UV/Blue boost (20% B, 72% R, 8% FR)
    FRUIT_ELONGATION = "fruit_elongation"          # Elevated Far-Red (15% B, 68% R, 17% FR)


class LEDSpectrumState(BaseModel):
    """Spectral, DLI, and electrical performance output of the LED array."""
    recipe: PhotobiologyRecipe
    target_dli_mol_m2_day: float
    solar_dli_mol_m2_day: float
    supplemental_dli_needed: float
    supplemental_ppfd_umol_m2_s: float
    photoperiod_hours: float
    red_pct: float
    blue_pct: float
    far_red_pct: float
    r_fr_ratio: float
    phytochrome_pss: float = Field(..., ge=0.0, le=1.0)
    shade_avoidance_risk: bool
    fixture_power_w_per_m2: float
    energy_kwh_per_m2_day: float


@dataclass
class LEDPhotobiologyEngine:
    """
    Computes DLI deficits, phytochrome photostationary state, and LED electrical demand.
    """
    LED_EFFICACY_UMOL_PER_J: ClassVar[float] = 2.85  # Modern horticultural LED efficacy (umol/J)

    RECIPE_SPECTRA: ClassVar[dict[PhotobiologyRecipe, tuple[float, float, float]]] = {
        PhotobiologyRecipe.VEGETATIVE_COMPACT: (70.0, 25.0, 5.0),
        PhotobiologyRecipe.FLOWERING_ANTHOCYANIN: (72.0, 20.0, 8.0),
        PhotobiologyRecipe.FRUIT_ELONGATION: (68.0, 15.0, 17.0),
    }

    @staticmethod
    def compute_dli(ppfd_umol_m2_s: float, photoperiod_hours: float) -> float:
        """DLI (mol/m^2/day) = PPFD * hours * 3600 * 1e-6."""
        return round(max(0.0, ppfd_umol_m2_s) * max(0.0, photoperiod_hours) * 0.0036, 2)

    @staticmethod
    def compute_phytochrome_pss(red_pct: float, far_red_pct: float) -> tuple[float, float]:
        """
        Calculates R:FR ratio and Phytochrome Photostationary State (PSS = Pfr / Ptotal).
        Low R:FR (< 3.0) lowers PSS (< 0.72), triggering shade-avoidance stem elongation.
        """
        r_fr = red_pct / max(0.5, far_red_pct)
        pss = 0.88 * (r_fr / (r_fr + 0.85))
        return round(r_fr, 2), round(pss, 3)

    def tune_supplemental_lighting(
        self,
        recipe: PhotobiologyRecipe = PhotobiologyRecipe.FLOWERING_ANTHOCYANIN,
        target_dli_mol_m2_day: float = 18.0,
        solar_dli_mol_m2_day: float = 10.5,
        photoperiod_hours: float = 14.0,
        custom_far_red_pct: float | None = None,
    ) -> LEDSpectrumState:
        """
        Calculates supplemental PPFD, LED power density (W/m^2), and phytochrome state.
        """
        r_pct, b_pct, fr_pct = self.RECIPE_SPECTRA[recipe]
        if custom_far_red_pct is not None:
            fr_pct = max(1.0, min(40.0, custom_far_red_pct))
            r_pct = max(20.0, 100.0 - b_pct - fr_pct)

        r_fr, pss = self.compute_phytochrome_pss(r_pct, fr_pct)
        shade_risk = r_fr < 3.0 or pss < 0.72

        dli_deficit = max(0.0, round(target_dli_mol_m2_day - solar_dli_mol_m2_day, 2))
        supp_ppfd = round(dli_deficit / (max(1.0, photoperiod_hours) * 0.0036), 1) if dli_deficit > 0 else 0.0

        # Power density (W/m^2 = J/s/m^2) = PPFD (umol/s/m^2) / Efficacy (umol/J)
        power_w_m2 = round(supp_ppfd / self.LED_EFFICACY_UMOL_PER_J, 2)
        energy_kwh_m2_day = round((power_w_m2 * photoperiod_hours) / 1000.0, 3)

        return LEDSpectrumState(
            recipe=recipe,
            target_dli_mol_m2_day=target_dli_mol_m2_day,
            solar_dli_mol_m2_day=solar_dli_mol_m2_day,
            supplemental_dli_needed=dli_deficit,
            supplemental_ppfd_umol_m2_s=supp_ppfd,
            photoperiod_hours=photoperiod_hours,
            red_pct=round(r_pct, 1),
            blue_pct=round(b_pct, 1),
            far_red_pct=round(fr_pct, 1),
            r_fr_ratio=r_fr,
            phytochrome_pss=pss,
            shade_avoidance_risk=shade_risk,
            fixture_power_w_per_m2=power_w_m2,
            energy_kwh_per_m2_day=energy_kwh_m2_day,
        )
