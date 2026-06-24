"""Tests for geospatial primitives (rei.gis.spatial)."""
import math

import numpy as np

from rei.gis.spatial import gravity_accessibility, morans_i


def test_gravity_decays_with_distance():
    near = gravity_accessibility([100], d0=800)
    far = gravity_accessibility([2000], d0=800)
    assert near > far > 0


def test_gravity_sums_and_weights_capacity():
    one = gravity_accessibility([100], [1], d0=800)
    two = gravity_accessibility([100, 100], [1, 1], d0=800)
    five = gravity_accessibility([100], [5], d0=800)
    assert abs(two - 2 * one) < 1e-9
    assert abs(five - 5 * one) < 1e-9


def test_gravity_empty_is_zero():
    assert gravity_accessibility([]) == 0.0


def test_morans_i_sign():
    W = np.array([[0, 1, 0, 0], [1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0]], float)  # 4-node line
    assert morans_i([1, 1, -1, -1], W) > 0      # similar neighbours -> clustering
    assert morans_i([1, -1, 1, -1], W) < 0      # alternating -> dispersion


def test_morans_i_zero_variance_is_nan():
    W = np.array([[0, 1], [1, 0]], float)
    assert math.isnan(morans_i([5, 5], W))
