"""Tests for DVF cleaning logic (no network)."""
import pandas as pd

from rei.ingestion.dvf import DvfCollector


def test_commune_url_metropole_vs_dom():
    c = DvfCollector()
    assert c.commune_url(2024, "93066").endswith("/communes/93/93066.csv")
    assert c.commune_url(2024, "97101").endswith("/communes/971/97101.csv")


def test_clean_filters_and_computes_prix_m2():
    raw = pd.DataFrame({
        "id_mutation": ["1", "2", "3", "4"],
        "date_mutation": ["2024-03-01", "2024-05-01", "2024-06-01", "2024-07-01"],
        "nature_mutation": ["Vente"] * 4,
        "valeur_fonciere": [300000, 1000, 250000, 400000],   # row 2 below floor
        "code_commune": ["93066"] * 4,
        "code_departement": ["93"] * 4,
        "id_parcelle": ["p1", "p2", "p3", "p4"],
        "type_local": ["Appartement", "Maison", "Dépendance", "Maison"],  # row 3 not residential
        "surface_reelle_bati": [60, 80, 100, 0],             # row 4 zero area
        "nombre_pieces_principales": [3, 4, 5, 2],
        "surface_terrain": [0, 200, 0, 300],
        "longitude": [2.4] * 4,
        "latitude": [48.9] * 4,
    })
    out = DvfCollector().clean(raw)
    assert list(out["id_mutation"]) == ["1"]
    assert out["prix_m2"].iloc[0] == 5000  # 300000 / 60
    assert out["mutation_year"].iloc[0] == 2024
