"""
Unit test suite for pesticide residue degradation kinetics and biocontrol release safety checks.
"""
import pytest

from backend.core.biocontrol_safety import (
    BiocontrolSafetyEngine,
    IobcToxicityRating,
    SprayApplication,
)


def test_residual_concentration_decay():
    """Verify first-order exponential decay formula across half-lives."""
    c0 = 10.0
    t_half = 4.0

    # At t = 0 -> 10.0
    assert BiocontrolSafetyEngine.calculate_residual_concentration(c0, t_half, 0.0) == 10.0

    # At t = 1 half-life (4 days) -> 5.0
    assert pytest.approx(BiocontrolSafetyEngine.calculate_residual_concentration(c0, t_half, 4.0), abs=0.01) == 5.0

    # At t = 2 half-lives (8 days) -> 2.5
    assert pytest.approx(BiocontrolSafetyEngine.calculate_residual_concentration(c0, t_half, 8.0), abs=0.01) == 2.5

    # At t = 3 half-lives (12 days) -> 1.25
    assert pytest.approx(BiocontrolSafetyEngine.calculate_residual_concentration(c0, t_half, 12.0), abs=0.01) == 1.25


def test_required_waiting_days_calculation():
    """Verify calculation of withholding period to reach non-toxic threshold."""
    c0 = 16.0
    target_ppm = 1.0  # Needs 4 half-lives (16 -> 8 -> 4 -> 2 -> 1)
    t_half = 3.0

    days_needed = BiocontrolSafetyEngine.calculate_required_waiting_days(c0, target_ppm, t_half)
    assert days_needed == 12.0  # 4 * 3.0 = 12.0 days


def test_evaluate_release_safety_clean_canopy():
    """Verify that an untreated canopy is cleared for immediate beneficial release."""
    report = BiocontrolSafetyEngine.evaluate_release_safety([], target_beneficial="phytoseiulus_persimilis")
    assert report.is_safe_to_release is True
    assert "pristine" in report.recommendation.lower()
    assert report.required_waiting_days_remaining == 0.0


def test_evaluate_release_safety_blocks_recent_deltamethrin():
    """Verify that a recent pyrethroid spray halts macro-biologic release."""
    spray = SprayApplication(
        ingredient_name="deltamethrin",
        application_date_days_ago=2.0,  # Sprayed 2 days ago
        initial_dose_ppm=12.5,
    )

    report = BiocontrolSafetyEngine.evaluate_release_safety([spray], target_beneficial="phytoseiulus_persimilis")

    assert report.is_safe_to_release is False
    assert report.limiting_ingredient == "deltamethrin"
    assert report.residual_concentration_ppm > 0.05
    assert report.required_waiting_days_remaining > 0.0
    assert report.iobc_rating == IobcToxicityRating.CLASS_4_HARMFUL
    assert "HOLD RELEASE" in report.recommendation


def test_evaluate_release_safety_clears_after_waiting_period():
    """Verify that after sufficient degradation time, release is authorized."""
    spray = SprayApplication(
        ingredient_name="abamectin",
        application_date_days_ago=12.0,  # t_half = 1.8 days; 12 days is ~6.6 half lives -> residue < 0.1 ppm
        initial_dose_ppm=3.6,
    )

    report = BiocontrolSafetyEngine.evaluate_release_safety([spray], target_beneficial="phytoseiulus_persimilis")
    assert report.is_safe_to_release is True
    assert "authorized" in report.recommendation.lower()


def test_botanical_and_microbial_safety():
    """Verify that harmless microbial (Bt) and botanical (Azadirachtin) sprays do not block release."""
    sprays = [
        SprayApplication(ingredient_name="bacillus_thuringiensis", application_date_days_ago=1.0, initial_dose_ppm=50.0),
        SprayApplication(ingredient_name="azadirachtin", application_date_days_ago=2.0, initial_dose_ppm=5.0),
    ]

    report = BiocontrolSafetyEngine.evaluate_release_safety(sprays, target_beneficial="phytoseiulus_persimilis")
    assert report.is_safe_to_release is True
