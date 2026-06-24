"""Out-of-time backtest of the composite screening score against realised returns.

This closes the gap the institutional review flagged as #1: the composite score
that would steer acquisitions has never been validated against what areas actually
did next. The ML *forecast* is backtested (rei.ml.backtest); the *screen* is not.

Scope and honesty. The production composite mixes current-snapshot inputs (hedonic
discount, coverage, rent level, forward ML) that have no historical panel, so they
cannot be reconstructed point-in-time. What *can* be reconstructed leakage-safe is
the appreciation / liquidity / risk core, derived from DVF history by
``rei.ml.features`` (the same point-in-time panel the price model trains on). This
harness rebuilds that core as a transparent 0-100 ``screen_score`` and asks, for
every base year: do high-scoring areas earn higher realised forward CAGR?

Metrics per base-year fold:
  * rank_ic        - Spearman corr(screen_score, realised forward CAGR). The headline.
  * decile_spread  - mean realised CAGR of the top score-decile minus the bottom.
  * hit_rate       - share of the top score-quintile that beat the cross-sectional median.

A positive, statistically stable mean rank-IC is the minimum evidence an investment
committee needs before treating the ranking as a buy signal rather than a research cue.
Extending the harness: once point-in-time snapshots exist for income, zoning, risk
and rent, add them as further legs here - the panel join is the only new input.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from rei.common.logging import get_logger
from rei.scoring.indicators import percentile_score

log = get_logger(__name__)

# Weights over the point-in-time, DVF-reconstructable legs (sum to 1.0). They mirror
# the production emphasis - appreciation first, then liquidity and low volatility -
# using only inputs that have a genuine historical panel.
SCREEN_W = {"momentum": 0.45, "accel": 0.15, "liquidity": 0.20, "low_vol": 0.20}


def _leg(feats: pd.DataFrame, col: str, direction: int) -> pd.Series:
    """Percentile-normalised 0-100 leg; a missing column scores a neutral 50
    (same convention as the production scoring layer)."""
    if col not in feats.columns:
        return pd.Series(50.0, index=feats.index)
    return percentile_score(feats[col], direction)


def screen_score(feats: pd.DataFrame) -> pd.Series:
    """Transparent 0-100 screen from the point-in-time DVF legs of one base-year slice.

    momentum  = trailing 3y price CAGR (higher is better)
    accel     = trend acceleration, last YoY minus prior YoY
    liquidity = log transaction count over the window
    low_vol   = inverse volatility (calmer markets score higher)

    Uses only feature columns, never the realised target, so it is leakage-safe by
    construction (asserted in the tests).
    """
    legs = {
        "momentum":  _leg(feats, "price_cagr_3y", 1),
        "accel":     _leg(feats, "trend_accel", 1),
        "liquidity": _leg(feats, "liquidity_log", 1),
        "low_vol":   _leg(feats, "volatility", -1),
    }
    total = sum(legs[k] * w for k, w in SCREEN_W.items())
    return total.round(2)


def _decile_spread(score: pd.Series, ret: pd.Series, q: int = 10) -> tuple[float, float, float]:
    """Top-decile minus bottom-decile mean realised return. Falls back to fewer
    buckets when the cross-section is too small for ten distinct bins."""
    bins = min(q, max(2, score.nunique()))
    d = pd.qcut(score.rank(method="first"), bins, labels=False, duplicates="drop")
    top, bot = ret[d == d.max()].mean(), ret[d == d.min()].mean()
    return float(top - bot), float(top), float(bot)


def backtest_screen(panel: pd.DataFrame | None = None, horizon: int = 5,
                    window: int = 5, min_areas: int = 20) -> pd.DataFrame:
    """One metrics row per base year. Pass a panel from ``rei.ml.features.build_panel``
    (or a synthetic one); if omitted it is built from DVF history."""
    if panel is None:
        from rei.ml.features import build_panel
        panel = build_panel(horizon=horizon, window=window)
    panel = panel.dropna(subset=["target_cagr"]).copy()
    cols = ["base_year", "n", "rank_ic", "decile_spread", "top_ret", "bottom_ret", "hit_rate"]
    if panel.empty:
        return pd.DataFrame(columns=cols)

    rows: list[dict] = []
    for yr, g in panel.groupby("year"):
        s, ret = screen_score(g), g["target_cagr"].astype(float)
        ok = s.notna() & ret.notna()
        s, ret = s[ok], ret[ok]
        if len(s) < min_areas or s.nunique() < 3:
            continue
        spread, top, bot = _decile_spread(s, ret)
        med = ret.median()
        rows.append({
            "base_year": int(yr), "n": int(len(s)),
            "rank_ic": round(float(s.corr(ret, method="spearman")), 4),
            "decile_spread": round(spread, 4), "top_ret": round(top, 4),
            "bottom_ret": round(bot, 4),
            "hit_rate": round(float((ret[s >= s.quantile(0.8)] > med).mean()), 4),
        })

    out = pd.DataFrame(rows, columns=cols)
    if not out.empty:
        log.info("Screen backtest: %d folds | mean rank-IC=%.3f | mean decile spread=%.4f",
                 len(out), out["rank_ic"].mean(), out["decile_spread"].mean())
    return out


def summarize(folds: pd.DataFrame) -> dict:
    """Aggregate the folds into a one-line institutional verdict.

    The IC t-statistic is mean(IC) / standard-error(IC) across folds; a value above
    ~2 means the cross-sectional skill is unlikely to be noise. Verdict bands are
    deliberately conservative - a mean rank-IC under 0.03 earns 'no demonstrated skill'.
    """
    cols_ok = not folds.empty and "rank_ic" in folds
    ic = folds["rank_ic"].dropna() if cols_ok else pd.Series(dtype=float)
    if ic.empty:
        return {"folds": 0, "mean_rank_ic": float("nan"), "ic_t_stat": float("nan"),
                "mean_decile_spread": float("nan"), "mean_hit_rate": float("nan"),
                "verdict": "insufficient history"}
    n = len(ic)
    se = ic.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    t = float(ic.mean() / se) if se and not np.isnan(se) and se > 0 else float("nan")
    mean_ic = float(ic.mean())
    verdict = ("no demonstrated skill" if mean_ic <= 0.03 else
               "weak but positive" if mean_ic < 0.10 else
               "useful screening skill")
    return {"folds": int(len(folds)), "mean_rank_ic": round(mean_ic, 4),
            "ic_t_stat": round(t, 2) if not np.isnan(t) else float("nan"),
            "mean_decile_spread": round(float(folds["decile_spread"].mean()), 4),
            "mean_hit_rate": round(float(folds["hit_rate"].mean()), 4),
            "verdict": verdict}


if __name__ == "__main__":
    f = backtest_screen()
    print(f.to_string(index=False))
    print(summarize(f))
