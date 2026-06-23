"""ML tests: leakage guard, target correctness, walk-forward, quantile bands.

All pure / no DB - synthetic frames stand in for the DVF price history.
"""
import numpy as np
import pandas as pd
import pytest

from rei.ml.explain import shap_table
from rei.ml.features import (
    FEATURE_COLS,
    features_asof,
    panel_from_prices,
)
from rei.ml.train import _make_mean_model, _make_quantile_model, _pinball


def _geometric_prices(code="00001", start=2008, end=2018, p0=100.0, g=0.10, n=50):
    years = list(range(start, end + 1))
    return pd.DataFrame({
        "code_commune": code,
        "year": years,
        "median_prix_m2": [p0 * (1 + g) ** (y - start) for y in years],
        "n_sales": n,
    })


def test_features_asof_ignores_future_years():
    """The core leakage guard: features at a base year must not change when
    later years are altered. The old static-snapshot join failed this."""
    base = _geometric_prices()
    tampered = base.copy()
    mask = tampered["year"] > 2014
    tampered.loc[mask, "median_prix_m2"] = 9_999_999.0
    tampered.loc[mask, "n_sales"] = 100_000

    f_clean = features_asof(base, 2014).set_index("code_commune")
    f_tampered = features_asof(tampered, 2014).set_index("code_commune")

    pd.testing.assert_frame_equal(f_clean[FEATURE_COLS], f_tampered[FEATURE_COLS])


def test_features_asof_level_and_trailing_cagr():
    prices = _geometric_prices(p0=100.0, g=0.10)
    f = features_asof(prices, 2014).iloc[0]
    assert f["price_level_log"] == pytest.approx(np.log(100.0 * 1.10 ** 6), rel=1e-6)
    assert f["price_cagr_3y"] == pytest.approx(0.10, abs=1e-9)
    assert f["price_cagr_5y"] == pytest.approx(0.10, abs=1e-9)


def test_panel_target_is_forward_cagr():
    prices = _geometric_prices(p0=100.0, g=0.10)
    panel = panel_from_prices(prices, horizon=3, window=5)
    row = panel[panel["year"] == 2010].iloc[0]
    # 10%/yr compounding -> 3-yr forward CAGR is exactly 10%
    assert row["target_cagr"] == pytest.approx(0.10, abs=1e-9)
    # and its features only see <= 2010 data
    assert row["price_level_log"] == pytest.approx(np.log(100.0 * 1.10 ** 2), rel=1e-6)


def test_panel_has_no_rows_without_future():
    prices = _geometric_prices(start=2008, end=2018)
    panel = panel_from_prices(prices, horizon=5, window=5)
    # last base year with a 5-yr-ahead value present is 2013
    assert panel["year"].max() == 2013


def _synthetic_panel(seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for year in range(2008, 2015):
        for c in range(40):
            f = {col: float(rng.normal()) for col in FEATURE_COLS}
            target = 0.4 * f["price_cagr_3y"] + 0.1 * f["trend_accel"] + rng.normal(scale=0.05)
            rows.append({"code_commune": f"{c:05d}", "year": year, "target_cagr": target, **f})
    return pd.DataFrame(rows)


def test_walk_forward_is_expanding_and_out_of_time():
    from rei.ml.backtest import walk_forward_panel

    panel = _synthetic_panel()
    folds = walk_forward_panel(panel, min_train_years=2)

    assert not folds.empty
    # earliest two base years lack >=2 prior years -> excluded
    assert folds["test_year"].min() == 2010
    assert list(folds["test_year"]) == sorted(folds["test_year"])
    # expanding window -> training set grows each fold
    assert folds["n_train"].is_monotonic_increasing
    assert ((folds["coverage_80"] >= 0) & (folds["coverage_80"] <= 1)).all()


def test_quantile_models_are_ordered():
    rng = np.random.default_rng(1)
    X = pd.DataFrame({"x": rng.uniform(0, 1, 400)})
    y = X["x"] + rng.normal(scale=0.1, size=400)

    p10 = _make_quantile_model(0.1).fit(X, y).predict(X)
    p50 = _make_quantile_model(0.5).fit(X, y).predict(X)
    p90 = _make_quantile_model(0.9).fit(X, y).predict(X)

    assert p10.mean() <= p50.mean() + 1e-6
    assert p50.mean() <= p90.mean() + 1e-6


def test_pinball_equals_half_mae_at_median():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    pred = np.array([1.5, 1.5, 3.5, 3.5])
    assert _pinball(y, pred, 0.5) == pytest.approx(0.5 * np.mean(np.abs(y - pred)))


def test_shap_table_returns_one_row_per_input():
    rng = np.random.default_rng(2)
    X = pd.DataFrame({c: rng.normal(size=120) for c in FEATURE_COLS})
    y = X["price_cagr_3y"] + rng.normal(scale=0.1, size=120)
    model = _make_mean_model().fit(X, y)

    tbl = shap_table(model, X, top_k=3)
    assert len(tbl) == len(X)
    assert "top_drivers" in tbl.columns
    assert isinstance(tbl["top_drivers"].iloc[0], list)
    assert len(tbl["top_drivers"].iloc[0]) <= 3


def test_ml_modules_import():
    import rei.ml.backtest  # noqa: F401
    import rei.ml.predict  # noqa: F401
    import rei.ml.train  # noqa: F401


def test_price_long_from_files_aggregates():
    from rei.ml.features import _price_long_from_files

    dvf = pd.DataFrame({
        "code_commune": ["75101", "75101", "75101", "75102", "75102"],
        "mutation_year": [2018, 2018, 2019, 2019, 2019],
        # 150 (<200) and 100000 (>25000) are out of band and must be dropped
        "prix_m2": [3000.0, 5000.0, 150.0, 9000.0, 100000.0],
    })
    out = _price_long_from_files(dvf).set_index(["code_commune", "year"])
    assert out.loc[("75101", 2018), "median_prix_m2"] == 4000.0   # median(3000, 5000)
    assert out.loc[("75101", 2018), "n_sales"] == 2
    assert ("75101", 2019) not in out.index                       # only the out-of-band 50
    assert out.loc[("75102", 2019), "n_sales"] == 1               # 100000 filtered out
    assert out.loc[("75102", 2019), "median_prix_m2"] == 9000.0


def test_file_mode_train_predict_end_to_end(tmp_path, monkeypatch):
    """Full file-mode chain: synthetic DVF -> train -> predict -> ml_forecast."""
    import rei.common.store as store
    import rei.ml.predict as predict_mod
    import rei.ml.train as train_mod

    rng = np.random.default_rng(0)
    rows = []
    for c in range(6):
        base = 2000 + c * 200
        for y in range(2008, 2019):
            price = base * (1.05 ** (y - 2008))
            for _ in range(20):
                rows.append({"code_commune": f"7510{c}", "mutation_year": y,
                             "prix_m2": float(price * rng.uniform(0.9, 1.1))})
    dvf = pd.DataFrame(rows)

    captured = {}
    monkeypatch.setattr(store, "using_files", lambda: True)
    monkeypatch.setattr(store, "read_table",
                        lambda name: dvf if name == "dvf_transactions" else pd.DataFrame())
    monkeypatch.setattr(store, "write_table_files",
                        lambda df, name, conflict_cols=None: captured.setdefault(name, df.copy()) is None or len(df))

    model_path = tmp_path / "price_growth.joblib"
    monkeypatch.setattr(train_mod, "MODEL_PATH", model_path)
    monkeypatch.setattr(predict_mod, "MODEL_PATH", model_path)

    metrics = train_mod.train(horizon=3, window=5)
    assert metrics["n_train"] > 0 and model_path.exists()

    out = predict_mod.predict_all(with_shap=False)
    assert "ml_forecast" in captured
    assert {"code_commune", "expected_price_cagr", "cagr_p10", "cagr_p90"} <= set(out.columns)
    assert len(out) == 6


def test_choose_horizon_prefers_multiple_base_years():
    from main import _choose_horizon
    assert _choose_horizon([2024, 2025], 5) == 1                              # 2 yrs -> horizon 1 only
    assert _choose_horizon([2020, 2021, 2022, 2023, 2024, 2025], 5) == 3      # picks 3 (>=3 base yrs)
    assert _choose_horizon([2025], 5) is None                                 # <2 distinct years
    assert _choose_horizon([2018, 2019, 2020, 2021], 2) == 1                  # h=1 gives 3 base yrs (preferred)
