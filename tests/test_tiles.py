"""Tile-SQL builder unit tests (no DB)."""
import pytest

from rei.api.tiles import LAYERS, build_tile_sql, simplify_tolerance


def test_all_layers_build():
    for name in LAYERS:
        sql, params = build_tile_sql(name, z=12)
        assert "ST_AsMVT" in sql and "ST_AsMVTGeom" in sql
        assert f"'{name}'" in sql            # layer name embedded in ST_AsMVT
        assert params["z"] == 12


def test_simplify_tolerance_zoom_scaling():
    assert simplify_tolerance(12) == 0.0          # no simplify at street zoom
    assert simplify_tolerance(6) > simplify_tolerance(10) > 0  # more simplify when zoomed out


def test_simplify_only_for_polygon_layers():
    _, comm = build_tile_sql("communes", z=6)
    _, tran = build_tile_sql("transit", z=6)
    assert "tol" in comm
    assert "tol" not in tran


def test_unknown_layer_raises():
    with pytest.raises(KeyError):
        build_tile_sql("nope", z=10)
