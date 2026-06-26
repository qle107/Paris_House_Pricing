"""Unit tests for the geolocated-collector parsers (pure functions, no network)."""
import pandas as pd

from rei.ingestion.education import normalize_school_points
from rei.ingestion.health import normalize_hospital_points


def test_school_points_from_annuaire_fields():
    raw = pd.DataFrame({
        "identifiant_de_l_etablissement": ["0750001A", "0750002B"],
        "nom_etablissement": ["Ecole A", "Ecole B"],
        "code_commune": ["75101", "75102"],
        "latitude": [48.85, 48.86],
        "longitude": [2.35, 2.36],
    })
    out = normalize_school_points(raw)
    assert len(out) == 2
    assert {"uai", "nom_etablissement", "code_commune", "latitude", "longitude"} <= set(out.columns)
    assert out["uai"].tolist() == ["0750001A", "0750002B"]


def test_school_points_drops_missing_coords_and_requires_coord_cols():
    raw = pd.DataFrame({"uai": ["a", "b"], "latitude": [48.85, None], "longitude": [2.35, 2.36]})
    assert normalize_school_points(raw)["uai"].tolist() == ["a"]
    # no coordinate columns at all -> empty frame with the right schema
    assert normalize_school_points(pd.DataFrame({"uai": ["a"], "nom_etablissement": ["x"]})).empty


def test_hospital_points_explicit_latlon():
    raw = pd.DataFrame({"osm_id": ["1", "2"], "name": ["H1", "H2"],
                        "latitude": [48.85, 48.9], "longitude": [2.35, 2.4]})
    out = normalize_hospital_points(raw)
    assert out["facility_id"].tolist() == ["1", "2"]
    assert len(out) == 2


def test_hospital_points_geo_point_2d_dict():
    raw = pd.DataFrame({"osm_id": ["1"], "name": ["H1"], "geo_point_2d": [{"lat": 48.85, "lon": 2.35}]})
    row = normalize_hospital_points(raw).iloc[0]
    assert (round(row["latitude"], 2), round(row["longitude"], 2)) == (48.85, 2.35)


def test_hospital_points_geo_point_2d_dotted_columns():
    raw = pd.DataFrame({"osm_id": ["1"], "name": ["H1"],
                        "geo_point_2d.lat": [48.85], "geo_point_2d.lon": [2.35]})
    assert normalize_hospital_points(raw).iloc[0]["latitude"] == 48.85


def test_hospital_points_geo_point_2d_string():
    raw = pd.DataFrame({"id": ["1"], "name": ["H1"], "geo_point_2d": ["48.85, 2.35"]})
    row = normalize_hospital_points(raw).iloc[0]
    assert (row["latitude"], row["longitude"]) == (48.85, 2.35)


def test_hospital_points_no_coords_is_empty():
    assert normalize_hospital_points(pd.DataFrame({"osm_id": ["1"], "name": ["H1"]})).empty
