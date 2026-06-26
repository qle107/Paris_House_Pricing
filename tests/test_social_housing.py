"""Unit tests for the SRU social-housing normaliser (pure function, no network)."""
import pandas as pd

from rei.ingestion.social_housing import normalize_sru


def test_normalize_sru_from_counts():
    raw = pd.DataFrame({"code_commune": ["75101", "93066"],
                        "nb_ls": [2000, 5000], "nb_rp": [10000, 10000]})
    out = normalize_sru(raw).set_index("code_commune")
    assert out.loc["75101", "social_housing_share"] == 20.0
    assert out.loc["75101", "sru_deficit_pct"] == 5.0     # target 25 - 20
    assert out.loc["93066", "social_housing_share"] == 50.0
    assert out.loc["93066", "sru_deficit_pct"] == 0.0     # above target -> no deficit


def test_normalize_sru_uses_rate_column_and_pads_code():
    raw = pd.DataFrame({"codgeo": [1001], "taux_sru": [12.5]})
    out = normalize_sru(raw).iloc[0]
    assert out["code_commune"] == "01001"                 # zero-padded to 5 digits
    assert out["social_housing_share"] == 12.5
    assert out["sru_deficit_pct"] == 12.5


def test_normalize_sru_accented_spaced_headers():
    # real data.gouv headers carry accents, spaces and units
    raw = pd.DataFrame({"Code commune": ["93066"],
                        "Nombre de logements sociaux": [3000],
                        "Résidences principales": [12000]})
    out = normalize_sru(raw).iloc[0]
    assert out["code_commune"] == "93066"
    assert out["social_housing_share"] == 25.0
    assert out["sru_deficit_pct"] == 0.0


def test_normalize_sru_rate_header_with_percent_unit():
    raw = pd.DataFrame({"INSEE": ["75056"], "Taux de logements sociaux (%)": [21.3]})
    out = normalize_sru(raw).iloc[0]
    assert out["code_commune"] == "75056"
    assert out["social_housing_share"] == 21.3
    assert out["sru_deficit_pct"] == 3.7                  # 25 - 21.3


def test_normalize_sru_missing_columns_returns_empty():
    assert normalize_sru(pd.DataFrame({"foo": [1], "bar": [2]})).empty
