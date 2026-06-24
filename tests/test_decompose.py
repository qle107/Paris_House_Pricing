"""Tests for the institutional score decomposition (rei.reporting.decompose)."""
from rei.reporting.decompose import decompose
from rei.scoring.institutional import ALPHA_W


def _row(**kw):
    base = {"inst_appreciation": 50, "inst_rental": 50, "inst_risk": 50, "inst_value_adj": 50,
            "inst_development": 50, "inst_liquidity": 50, "inst_toxicity": 50,
            "value_trap_score": 0.0, "climate_multiplier": 1.0,
            "institutional_score": 50.0, "data_coverage": 1.0}
    base.update(kw)
    return base


def test_contributions_vs_neutral_sum_to_base():
    d = decompose(_row(inst_appreciation=80, inst_rental=30))
    assert d["contributions"]["appreciation"] == round(0.28 * 30, 1)   # +8.4
    assert d["contributions"]["rental"] == round(0.22 * -20, 1)        # -4.4
    assert d["base_pre_gate"] == round(50 + 8.4 - 4.4, 1)              # 54.0
    assert d["positive_contributors"][0][0] == "appreciation"
    assert d["negative_contributors"][0][0] == "rental"


def test_gates_detected():
    d = decompose(_row(inst_rental=30, inst_toxicity=80))
    assert "rental < 40 -> capped at 55" in d["gates_fired"]
    assert "toxicity > 70 -> x0.85" in d["gates_fired"]
    assert "appreciation < 40 -> capped at 55" not in d["gates_fired"]


def test_trap_and_climate_haircuts_reported():
    d = decompose(_row(value_trap_score=50.0, climate_multiplier=0.7))
    assert d["trap_haircut_pct"] == 20.0      # 0.40 * 50
    assert d["climate_haircut_pct"] == 30.0   # (1 - 0.70) * 100


def test_clean_row_has_no_gates_and_neutral_base():
    d = decompose(_row())
    assert d["gates_fired"] == []
    assert d["base_pre_gate"] == 50.0
    assert d["positive_contributors"] == []
    assert d["negative_contributors"] == []


def test_alpha_weights_supported():
    d = decompose(_row(inst_appreciation=70), weights=ALPHA_W)
    assert d["contributions"]["appreciation"] == round(0.40 * 20, 1)   # 8.0
    assert "risk" not in d["contributions"]                            # alpha has no risk term
