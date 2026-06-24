"""Tests for per-area liquidity normalization (rei.scoring.indicators.liquidity_density).

Raw transaction count let a large whole-commune ("commune non irisee") unit out-rank a
small dense IRIS purely on volume - the MAUP inflation both reviews flagged. Density
(sales/km2) corrects it. Pure function - no DB, no geopandas.
"""
import pandas as pd

from rei.scoring.indicators import liquidity_density


def test_density_inverts_the_whole_commune_count_bias():
    n = pd.Series([500.0, 80.0])      # whole-commune unit vs small dense IRIS
    a = pd.Series([50.0, 0.5])        # 50 km2 vs 0.5 km2
    d = liquidity_density(n, a)
    assert d.iloc[0] == 10.0          # 500 / 50
    assert d.iloc[1] == 160.0         # 80 / 0.5
    assert d.iloc[1] > d.iloc[0]      # density ranks the dense IRIS above the big unit
    assert n.iloc[0] > n.iloc[1]      # ...whereas raw count would invert that ranking


def test_density_handles_missing_or_zero_area():
    d = liquidity_density(pd.Series([100.0, 50.0, 30.0]), pd.Series([2.0, None, 0.0]))
    assert d.iloc[0] == 50.0          # 100 / 2
    assert pd.isna(d.iloc[1])         # missing area -> NaN (neutral downstream)
    assert pd.isna(d.iloc[2])         # zero area -> NaN, no divide-by-zero
