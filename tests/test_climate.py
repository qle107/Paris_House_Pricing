"""Tests for the Georisques climate/ESG hazard haircut (rei.scoring.institutional).

The overlay was coded for communes but inert at IRIS grain (the review's risk gap).
climate_multiplier brings the commune risk_multiplier to the IRIS institutional score:
>= 6 distinct natural hazards cap the score at 0.70, fewer scale linearly, and a
missing count is neutral. Pure function - no DB, no geopandas.
"""
import pandas as pd

from rei.scoring.institutional import climate_multiplier


def test_climate_multiplier_scales_with_hazard_count():
    cm = climate_multiplier(pd.Series([0.0, 3.0, 6.0, 9.0, None]))
    assert cm.iloc[0] == 1.0          # no hazards -> no haircut
    assert cm.iloc[1] == 0.85         # 3 of 6 -> 1 - 0.5*0.3
    assert cm.iloc[2] == 0.7          # 6 hazards -> full haircut floor
    assert cm.iloc[3] == 0.7          # beyond full_at stays at the floor
    assert cm.iloc[4] == 1.0          # missing count -> neutral


def test_climate_multiplier_none_when_no_feed():
    assert climate_multiplier(None) is None


def test_climate_haircut_penalises_hazard_and_preserves_clean():
    """The applied haircut: a hazard-heavy IRIS is penalised, a clean one untouched."""
    score = pd.Series([80.0, 80.0])
    out = (score * climate_multiplier(pd.Series([0.0, 6.0]))).round(1)
    assert out.iloc[0] == 80.0        # clean -> unchanged
    assert out.iloc[1] == 56.0        # 6 hazards -> 80 * 0.70
