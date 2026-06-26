"""Unit tests for the family-liveability composite (renormalisation, pure pandas)."""
import pandas as pd

from rei.scoring.liveability import family_liveability


def test_liveability_full_coverage_blends_all():
    f = pd.DataFrame({"iris_code": ["A", "B"],
                      "school_access_score": [80.0, 20.0],
                      "hospital_access_score": [80.0, 20.0],
                      "safety_score": [80.0, 20.0],
                      "amenity_score": [80.0, 20.0]})
    out = family_liveability(f).set_index("iris_code")
    assert out.loc["A", "family_liveability_score"] == 80.0
    assert out.loc["A", "liveability_coverage"] == 1.0
    assert out.loc["A", "family_liveability_score"] > out.loc["B", "family_liveability_score"]


def test_liveability_renormalizes_on_missing_factor():
    # only schools (0.35) + health (0.25) present -> coverage 0.6, weights renormalised
    f = pd.DataFrame({"iris_code": ["A"],
                      "school_access_score": [90.0],
                      "hospital_access_score": [70.0]})
    out = family_liveability(f).iloc[0]
    assert out["liveability_coverage"] == 0.6
    # (0.35*90 + 0.25*70) / 0.6 = 81.666... -> 81.7
    assert out["family_liveability_score"] == 81.7


def test_liveability_all_missing_is_nan():
    out = family_liveability(pd.DataFrame({"iris_code": ["A"]})).iloc[0]
    assert pd.isna(out["family_liveability_score"])
    assert out["liveability_coverage"] == 0.0
