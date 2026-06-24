"""Tests for the auto-generated investment memo (rei.reporting.memo)."""
from rei.reporting.memo import investment_memo


def _row(**kw):
    base = {"iris_name": "Pleyel 01", "iris_code": "93066",
            "inst_appreciation": 85, "inst_rental": 70, "inst_risk": 60, "inst_value_adj": 65,
            "inst_development": 60, "inst_liquidity": 55, "inst_toxicity": 20,
            "value_trap_score": 12, "climate_multiplier": 1.0, "institutional_score": 74.0,
            "data_coverage": 0.82, "observed_prix_m2": 5474.0, "expected_prix_m2": 5900.0,
            "discount_pct": 7.2}
    base.update(kw)
    return base


def test_memo_has_title_score_and_recommendation():
    m = investment_memo(_row())
    assert "Pleyel 01" in m and "93066" in m
    assert "74/100" in m
    assert "Shortlist for acquisition" in m          # score 74 >= 70


def test_memo_lists_drivers_and_fired_gates():
    m = investment_memo(_row(inst_rental=30, inst_toxicity=80, institutional_score=45.0))
    assert "**Drivers.**" in m and "**Risks & penalties.**" in m
    assert "rental < 40" in m                         # a fired gate is surfaced
    assert "Watch" in m                               # 40 <= 45 < 55


def test_memo_includes_forecast_only_when_provided():
    fc = {"expected_price_cagr": -0.046, "cagr_p10": -0.09, "cagr_p90": 0.01, "horizon": 3}
    m = investment_memo(_row(), forecast=fc)
    assert "Forward outlook" in m and "-4.6%" in m
    assert "Forward outlook" not in investment_memo(_row())


def test_memo_flags_value_trap_and_pass():
    m = investment_memo(_row(institutional_score=32.0, value_trap_score=70))
    assert "Pass" in m and "value-trap risk" in m


def test_memo_value_line_formats_prices():
    m = investment_memo(_row())
    assert "5,474" in m and "5,900" in m
