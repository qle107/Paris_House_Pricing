"""MVT tile SQL builder (PostGIS ST_AsMVT)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Layer:
    name: str
    from_sql: str          # FROM clause (may include JOINs)
    geom: str              # geometry expression (EPSG:4326)
    id_col: str            # feature id property
    props: tuple[str, ...] # additional property expressions
    minzoom: int
    simplify: bool         # simplify polygons at low zoom


LAYERS: dict[str, Layer] = {
    "communes": Layer(
        name="communes",
        from_sql="gis.communes c LEFT JOIN scores.commune_score s ON s.code_commune = c.code_commune",
        geom="c.geometry",
        id_col="c.code_commune AS code_commune",
        props=("c.name AS name", "s.attractiveness_score AS score", "s.rank AS rank"),
        minzoom=0,
        simplify=True,
    ),
    "parcels": Layer(
        name="parcels",
        from_sql="scores.parcel_upside p",
        geom="p.geometry",
        id_col="p.id_parcelle AS id_parcelle",
        props=("p.buildable_upside_m2 AS upside_m2", "p.zone_family AS zone_family",
               "p.expected_uplift AS uplift"),
        minzoom=13,           # parcels only at street zoom (volume control)
        simplify=False,
    ),
    "zoning": Layer(
        name="zoning",
        from_sql="gis.zoning z",
        geom="z.geometry",
        id_col="z.ctid::text AS fid",
        props=("z.libelle AS libelle", "z.typezone AS typezone", "z.code_commune AS code_commune"),
        minzoom=11,
        simplify=True,
    ),
    "transit": Layer(
        name="transit",
        from_sql="gis.transit_stops t",
        geom="t.geometry",
        id_col="t.stop_id AS stop_id",
        props=("t.stop_name AS stop_name", "t.network AS network"),
        minzoom=10,
        simplify=False,
    ),
    "projects": Layer(
        name="projects",
        from_sql="gis.transport_projects tp",
        geom="tp.geometry",
        id_col="tp.ctid::text AS fid",
        props=("tp.project AS project", "tp.line AS line", "tp.mode AS mode",
               "tp.station AS station", "tp.opening::text AS opening", "tp.status AS status"),
        minzoom=6,
        simplify=False,
    ),
}


def simplify_tolerance(z: int) -> float:
    """Metres of simplification tolerance for low-zoom polygon layers (0 above z11)."""
    if z >= 12:
        return 0.0
    return max(0.0, (12 - z)) * 40.0   # ~40 m per zoom level below 12


def build_tile_sql(layer_name: str, z: int):
    """Return (sql, base_params) for a layer; caller adds x,y. Raises KeyError if unknown."""
    layer = LAYERS[layer_name]
    geom_3857 = f"ST_Transform({layer.geom}, 3857)"
    if layer.simplify:
        geom_3857 = f"ST_SimplifyPreserveTopology({geom_3857}, :tol)"
    select_props = ", ".join((layer.id_col,) + layer.props)
    sql = f"""
        WITH bounds AS (
          SELECT ST_TileEnvelope(:z, :x, :y) AS env3857,
                 ST_Transform(ST_TileEnvelope(:z, :x, :y), 4326) AS env4326
        )
        SELECT ST_AsMVT(q, '{layer.name}', 4096, 'geom') AS mvt
        FROM (
          SELECT {select_props},
                 ST_AsMVTGeom({geom_3857}, bounds.env3857, 4096, 64, true) AS geom
          FROM {layer.from_sql}, bounds
          WHERE {layer.geom} && bounds.env4326
        ) q
        WHERE q.geom IS NOT NULL
    """
    params = {"z": z, "tol": simplify_tolerance(z)} if layer.simplify else {"z": z}
    return sql, params
