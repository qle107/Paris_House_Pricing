"""Tests for validation helpers (pure parts; no DB)."""
import pandas as pd
import pytest

from rei.etl.validate import missingness_report, robust_z


def test_robust_z_flags_outlier():
    s = pd.Series([1, 1, 1, 1, 100.0])
    z = robust_z(s)
    assert z.iloc[-1] > 5         # the 100 is a clear outlier
    assert abs(z.iloc[0]) < 1


def test_missingness_report():
    df = pd.DataFrame({"a": [1, None, 3], "b": [1, 2, 3]})
    rep = missingness_report(df).set_index("column")["pct_missing"]
    assert rep["a"] == pytest.approx(33.33, abs=0.01)
    assert rep["b"] == 0.0


def test_dvf_schema_accepts_valid_frame():
    pa = pytest.importorskip("pandera")  # skip if pandera not installed
    from rei.etl.validate import validate_dvf
    df = pd.DataFrame({
        "valeur_fonciere": [300000.0],
        "surface_reelle_bati": [60.0],
        "prix_m2": [5000.0],
        "type_local": ["Appartement"],
        "mutation_year": pd.array([2024], dtype="Int64"),
        "code_commune": ["93066"],
    })
    validated = validate_dvf(df)
    assert len(validated) == 1
