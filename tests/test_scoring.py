"""Unit tests for scoring primitives (pure functions, no DB)."""
import pandas as pd

from rei.scoring.files_engine import _price_features
from rei.scoring.indicators import percentile_score, risk_multiplier, threshold_score
from rei.scoring.institutional import apply_gates, value_trap_score
from rei.transport.impact import expected_uplift
from rei.zoning.detectors import _norm


def test_percentile_score_direction():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    asc = percentile_score(s, direction=1)
    desc = percentile_score(s, direction=-1)
    assert asc.iloc[-1] == 100.0          # largest value -> top score
    assert desc.iloc[0] == 100.0          # smallest value -> top score when inverted


def test_percentile_score_nan_is_neutral():
    s = pd.Series([1.0, None, 3.0])
    out = percentile_score(s)
    assert out.iloc[1] == 50.0


def test_risk_multiplier_bounds():
    assert risk_multiplier(0, full_at=6, min_mult=0.7) == 1.0
    assert risk_multiplier(6, full_at=6, min_mult=0.7) == 0.7
    assert 0.7 <= risk_multiplier(3, full_at=6, min_mult=0.7) <= 1.0


def test_threshold_score():
    bands = [(0.02, 20), (0.05, 60), (0.10, 100)]
    assert threshold_score(0.01, bands) == 20
    assert threshold_score(0.04, bands) == 60
    assert threshold_score(0.5, bands) == 100


def test_expected_uplift_decays_with_distance():
    near = expected_uplift("metro", dist_m=100, years_to_open=1)
    far = expected_uplift("metro", dist_m=1400, years_to_open=1)
    assert near > far >= 0
    assert expected_uplift("metro", dist_m=5000, years_to_open=1) == 0.0


def test_norm_clips():
    assert _norm(10, 5) == 1.0
    assert _norm(-1, 5) == 0.0
    assert _norm(2.5, 5) == 0.5


def test_price_features_no_inband_sales_keeps_merge_key():
    dvf = pd.DataFrame({"code_commune": [75101, 75102], "mutation_year": [2020, 2021],
                        "prix_m2": [50.0, 100.0]})
    out = _price_features(dvf)
    assert list(out.columns) == ["code_commune", "median_prix_m2_last", "price_cagr_5y", "n_sales_total"]
    communes = pd.DataFrame({"code_commune": ["75101", "75102"], "name": ["a", "b"]})
    communes.merge(out, on="code_commune", how="left")


def test_price_features_returns_str_key_for_int64_dvf():
    dvf = pd.DataFrame({"code_commune": [75101, 75101, 75102],
                        "mutation_year": [2019, 2024, 2024],
                        "prix_m2": [8000.0, 10000.0, 9000.0]})
    out = _price_features(dvf)
    assert out["code_commune"].dtype == object
    assert set(out["code_commune"]) == {"75101", "75102"}


def test_value_trap_score_extremes_and_midpoint():
    # row0 strong/clean -> 0; row1 cheap-but-weak -> 100; row2 neutral -> 50
    appr = pd.Series([100.0, 0.0, 50.0])
    rent = pd.Series([100.0, 0.0, 50.0])
    tox = pd.Series([0.0, 100.0, 50.0])
    liq = pd.Series([100.0, 0.0, 50.0])
    risk = pd.Series([100.0, 0.0, 50.0])
    trap = value_trap_score(appr, rent, tox, liq, risk)
    assert list(trap) == [0.0, 100.0, 50.0]


def test_apply_gates_caps_penalties_and_haircut():
    score = pd.Series([80.0, 90.0, 80.0, 100.0, 90.0])
    appr = pd.Series([90.0, 20.0, 90.0, 90.0, 30.0])   # rows 1,4 fail appreciation gate
    rent = pd.Series([90.0, 90.0, 90.0, 90.0, 90.0])
    tox = pd.Series([10.0, 10.0, 80.0, 10.0, 10.0])    # row 2 toxicity penalty
    risk = pd.Series([90.0, 90.0, 90.0, 90.0, 90.0])
    liq = pd.Series([90.0, 90.0, 90.0, 90.0, 90.0])
    trap = pd.Series([0.0, 0.0, 0.0, 50.0, 50.0])      # rows 3,4 trap haircut
    out = apply_gates(score, appr, rent, tox, risk, liq, trap)
    # row0 untouched; row1 capped to 55; row2 *0.85; row3 100*(1-0.2); row4 cap 55 then *0.8
    assert list(out) == [80.0, 55.0, 68.0, 80.0, 44.0]
