"""Tests for economic-concentration risk (rei.scoring.concentration)."""
import math

from rei.scoring.concentration import concentration_risk, herfindahl


def test_herfindahl_bounds():
    assert herfindahl([100, 0, 0, 0]) == 1.0              # single sector
    assert abs(herfindahl([25, 25, 25, 25]) - 0.25) < 1e-9  # 4 even -> 1/4
    assert math.isnan(herfindahl([0, 0]))                  # empty -> nan


def test_concentration_risk_diversified_vs_concentrated():
    assert concentration_risk([20, 20, 20, 20, 20]) < 10   # even -> ~0
    assert concentration_risk([90, 5, 5]) > 60             # dominated -> high
    assert concentration_risk([100]) == 100.0              # single sector -> max


def test_concentration_risk_normalised_across_sector_counts():
    # even economies read as fully diversified regardless of sector count
    assert concentration_risk([50, 50]) < 5
    assert concentration_risk([10] * 10) < 5


def test_concentration_risk_empty_is_neutral():
    assert concentration_risk([]) == 50.0
    assert concentration_risk([0, 0, 0]) == 50.0
