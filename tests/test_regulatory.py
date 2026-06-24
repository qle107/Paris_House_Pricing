"""Tests for regulatory (downzoning) risk (rei.zoning.regulatory)."""
from rei.zoning.regulatory import downzoning_risk


def test_downzoning_risk():
    assert downzoning_risk(1000, 1000) == 0.0     # unchanged -> no risk
    assert downzoning_risk(1000, 600) == 40.0     # 40% of capacity lost
    assert downzoning_risk(1000, 1200) == 0.0     # upzoning -> no downside
    assert downzoning_risk(0, 500) == 50.0        # unknown baseline -> neutral
