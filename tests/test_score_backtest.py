"""Tests for the composite screen backtest (rei.scoring.backtest).

The harness must (a) detect real cross-sectional signal, (b) NOT manufacture skill
on noise, and (c) be leakage-safe. Synthetic panels stand in for the DVF-derived
point-in-time panel produced by rei.ml.features, so no DB or data files are needed.
"""
import numpy as np
import pandas as pd

from rei.ml.features import FEATURE_COLS
from rei.scoring.backtest import SCREEN_W, backtest_screen, screen_score, summarize


def _panel(signal: float = 0.5, noise: float = 0.05, seed: int = 0,
           years=range(2008, 2015), n: int = 60) -> pd.DataFrame:
    """Synthetic point-in-time panel. The realised target depends on momentum
    (price_cagr_3y) with strength `signal`, plus gaussian noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for y in years:
        for c in range(n):
            f = {col: float(rng.normal()) for col in FEATURE_COLS}
            target = signal * f["price_cagr_3y"] + rng.normal(scale=noise)
            rows.append({"code_commune": f"{c:05d}", "year": y, "target_cagr": target, **f})
    return pd.DataFrame(rows)


def test_screen_weights_sum_to_one():
    assert abs(sum(SCREEN_W.values()) - 1.0) < 1e-9


def test_screen_score_is_0_100_and_neutral_on_missing():
    g = _panel().groupby("year").get_group(2010)
    s = screen_score(g)
    assert s.between(0, 100).all()
    # a frame with no known feature columns -> every leg neutral 50 -> score 50
    blank = pd.DataFrame(index=range(5))
    assert (screen_score(blank) == 50.0).all()


def test_screen_score_is_leakage_safe():
    """screen_score must depend only on features, never on the realised target."""
    g = _panel().groupby("year").get_group(2011).copy()
    base = screen_score(g)
    g["target_cagr"] = g["target_cagr"] + 1000.0          # tamper the outcome
    pd.testing.assert_series_equal(screen_score(g), base)


def test_backtest_detects_injected_signal():
    folds = backtest_screen(panel=_panel(signal=0.8, noise=0.02))
    assert not folds.empty
    assert folds["rank_ic"].mean() > 0.2                  # momentum-driven target -> positive IC
    assert folds["decile_spread"].mean() > 0              # top decile beats bottom
    s = summarize(folds)
    assert s["verdict"] in ("weak but positive", "useful screening skill")
    assert s["ic_t_stat"] > 2                             # stable across folds


def test_backtest_reports_no_skill_on_noise():
    folds = backtest_screen(panel=_panel(signal=0.0, noise=1.0, seed=3))
    s = summarize(folds)
    assert abs(s["mean_rank_ic"]) < 0.15                  # no real signal -> IC near zero
    assert s["verdict"] != "useful screening skill"


def test_backtest_skips_thin_cross_sections():
    folds = backtest_screen(panel=_panel(n=10), min_areas=20)   # 10 areas/yr < 20
    assert folds.empty


def test_summarize_handles_empty():
    s = summarize(pd.DataFrame(columns=["rank_ic", "decile_spread", "hit_rate"]))
    assert s["folds"] == 0
    assert s["verdict"] == "insufficient history"
