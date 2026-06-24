"""Tests for the location-aware hedonic Value re-specification (rei.scoring.institutional).

The old model had no location term, so its 'discount' collapsed to inverse price
(r = -0.85 vs price in RANKING_METHODOLOGY_REVIEW.md): cheap exurbs read as ~100%
undervalued, prime Paris as overvalued. The fix conditions expected price on the
commune location level, so the discount measures mispricing *given location*.

Synthetic only - no DB, no geopandas (the function under test is pure pandas/sklearn).
"""
import numpy as np
import pandas as pd

from rei.scoring.institutional import _hedonic_discount


def _market(seed: int = 0) -> pd.DataFrame:
    """Three communes at very different price levels, six IRIS each (~40 sales/IRIS).
    Two planted anomalies, with structure (surface) held similar so LOCATION, not
    structure, sets price:
      C5 - in the PRIME commune, trades 30% BELOW its commune level (a real bargain)
      A5 - in the CHEAP commune, trades 30% ABOVE its commune level (overpriced)
    """
    rng = np.random.default_rng(seed)
    base = {"A": 2000.0, "B": 4000.0, "C": 8000.0}        # cheap / mid / prime EUR/m2
    rows = []
    for com, lvl in base.items():
        for i in range(6):
            iris = f"{com}{i}"
            factor = 0.70 if iris == "C5" else 1.30 if iris == "A5" else 1.0
            for _ in range(40):
                rows.append({
                    "iris_code": iris, "code_commune": f"00{com}",
                    "prix_m2": round(lvl * factor * rng.uniform(0.95, 1.05), 0),
                    "surface_reelle_bati": rng.uniform(40, 90),
                    "nombre_pieces_principales": 3, "type_local": "Appartement",
                    "mutation_year": 2023,
                })
    return pd.DataFrame(rows)


def test_output_contract_and_small_sample_guard():
    out = _hedonic_discount(_market())
    assert list(out.columns) == ["iris_code", "observed_prix_m2", "expected_prix_m2", "discount_pct"]
    assert len(out) == 18
    tiny = pd.DataFrame({"prix_m2": [3000.0] * 10, "surface_reelle_bati": [50.0] * 10})
    assert _hedonic_discount(tiny).empty            # <50 in-band rows -> empty, key columns kept


def test_prefers_genuine_mispricing_over_cheapness():
    """The decisive institutional property the old model got backwards: a genuine
    bargain in a prime location must out-discount a merely-cheap, fairly-priced exurb."""
    out = _hedonic_discount(_market()).set_index("iris_code")
    bargain = out.loc["C5", "discount_pct"]          # prime commune, ~5,600 EUR/m2, real bargain
    cheap_fair = out.loc["A0", "discount_pct"]        # cheap commune, ~2,000 EUR/m2, fairly priced
    overpriced = out.loc["A5", "discount_pct"]        # cheap commune, ~2,600 EUR/m2, overpriced
    assert bargain > cheap_fair                       # prefers real mispricing over raw cheapness
    assert overpriced < cheap_fair                    # penalises overpricing within a location
    assert bargain > 15                               # the planted 30% bargain shows a clear discount
    # And observed price level alone does NOT rank the opportunity:
    assert out.loc["C5", "observed_prix_m2"] > out.loc["A0", "observed_prix_m2"] * 2


def test_discount_less_inverse_than_location_blind():
    """Old model: discount ~ -price (Spearman -0.85). Dropping the commune control
    reproduces that near-inverse behaviour; adding it must materially decouple the
    discount from raw price level on the same data."""
    m = _market()
    new = _hedonic_discount(m)
    blind = _hedonic_discount(m.drop(columns="code_commune"))   # structure-only model
    r_new = abs(new["discount_pct"].corr(new["observed_prix_m2"], method="spearman"))
    r_blind = abs(blind["discount_pct"].corr(blind["observed_prix_m2"], method="spearman"))
    assert r_blind > 0.85                  # location-blind really is ~inverse price
    assert r_new < r_blind - 0.25          # location control materially decouples it


def test_falls_back_to_location_blind_without_commune():
    """No code_commune column -> still returns a valid frame (structure-only model)."""
    m = _market().drop(columns="code_commune")
    out = _hedonic_discount(m)
    assert list(out.columns) == ["iris_code", "observed_prix_m2", "expected_prix_m2", "discount_pct"]
    assert len(out) == 18
