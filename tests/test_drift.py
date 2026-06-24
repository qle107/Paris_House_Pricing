"""Tests for PSI data-drift detection (rei.etl.drift)."""
import math

import numpy as np

from rei.etl.drift import psi


def test_psi_near_zero_for_same_distribution():
    rng = np.random.default_rng(0)
    x = rng.normal(size=3000)
    assert psi(x, x) < 0.01


def test_psi_flags_a_two_sigma_shift():
    rng = np.random.default_rng(1)
    base = rng.normal(0, 1, 4000)
    shifted = rng.normal(2, 1, 4000)
    assert psi(base, shifted) > 0.25       # major drift


def test_psi_empty_is_nan():
    assert math.isnan(psi([], [1, 2, 3]))
    assert math.isnan(psi([1, 2, 3], []))
