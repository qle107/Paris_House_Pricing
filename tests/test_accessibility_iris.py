"""Unit tests for the per-IRIS amenity-accessibility scorer (pure GeoPandas, no DB)."""
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from rei.scoring.accessibility_iris import (
    SCHOOL_CATCHMENT_M,
    _amenity_access,
    accessibility_scores,
)


def _square(cx, cy, h=0.004):
    return Polygon([(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)])


def _zones():
    # Zone A near central Paris, zone B ~11 km east (outside any 1 km catchment of A's points).
    return gpd.GeoDataFrame(
        {"iris_code": ["A", "B"], "code_commune": ["75101", "75101"]},
        geometry=[_square(2.35, 48.85), _square(2.50, 48.85)], crs=4326)


def test_accessibility_prefers_zone_with_nearby_school():
    schools = gpd.GeoDataFrame({"uai": ["s1"]}, geometry=[Point(2.35, 48.85)], crs=4326)
    out = accessibility_scores(_zones(), schools, None).set_index("iris_code")
    assert out.loc["A", "school_access_score"] > out.loc["B", "school_access_score"]
    assert out.loc["A", "n_schools_1km"] == 1
    assert out.loc["B", "n_schools_1km"] == 0
    # hospital layer absent -> NaN (so liveability drops it) rather than a fake 50
    assert pd.isna(out.loc["A", "hospital_access_score"])


def test_amenity_access_missing_layer_is_nan():
    out = _amenity_access(_zones(), None, SCHOOL_CATCHMENT_M)
    assert out["raw"].isna().all()
    assert (out["n_within"] == 0).all()


def test_amenity_access_counts_within_catchment():
    schools = gpd.GeoDataFrame(
        {"uai": ["s1", "s2"]},
        geometry=[Point(2.3505, 48.8505), Point(2.349, 48.849)], crs=4326)
    out = _amenity_access(_zones(), schools, SCHOOL_CATCHMENT_M).set_index("iris_code")
    assert out.loc["A", "n_within"] == 2
    assert out.loc["B", "n_within"] == 0
