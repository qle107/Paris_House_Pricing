"""FastAPI map server (MVT tiles + commune detail)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from rei.api.tiles import LAYERS, build_tile_sql
from rei.common.db import get_engine

app = FastAPI(title="REI Map API", version="0.1.0")
MAP_HTML = Path(__file__).resolve().parents[2] / "dashboards" / "map" / "index.html"
MVT_MIME = "application/vnd.mapbox-vector-tile"


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/")
def index():
    if not MAP_HTML.exists():
        raise HTTPException(404, "map UI not found")
    return FileResponse(MAP_HTML)


@app.get("/api/layers")
def layers():
    return {
        name: {"minzoom": l.minzoom, "simplify": l.simplify}
        for name, l in LAYERS.items()
    }


@app.get("/tiles/{layer}/{z}/{x}/{y}.pbf")
def tile(layer: str, z: int, x: int, y: int):
    if layer not in LAYERS:
        raise HTTPException(404, f"unknown layer '{layer}'")
    if z < LAYERS[layer].minzoom:
        return Response(status_code=204)          # below minzoom: nothing to draw
    sql, params = build_tile_sql(layer, z)
    params.update({"x": x, "y": y})
    with get_engine().connect() as conn:
        row = conn.execute(text(sql), params).fetchone()
    data = bytes(row[0]) if row and row[0] is not None else b""
    if not data:
        return Response(status_code=204)
    return Response(
        content=data,
        media_type=MVT_MIME,
        headers={"Cache-Control": "public, max-age=3600"},  # tiles are cheap to cache
    )


@app.get("/api/commune/{code}")
def commune_detail(code: str):
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT * FROM scores.commune_score WHERE code_commune = :c"), {"c": code}
        ).mappings().fetchone()
    if not row:
        raise HTTPException(404, f"no score for commune {code}")
    return JSONResponse(dict(row))
