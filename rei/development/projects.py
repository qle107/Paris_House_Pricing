"""Forward-looking urban-development projects for the Grand Paris core.

Curated, source-verified seed of major aménagement operations (ZAC), new
districts, and large public facilities in Paris + 92/93/94 whose delivery falls
in the next ~5-10 years. Coordinates are approximate site centroids (sufficient
for the catchment-based impact model); status and dates are the June 2026 view.
See ``seeds/README.md`` / ``docs/URBAN_DEVELOPMENT_INTELLIGENCE.md`` for sources.

This is a starter set meant to be extended by the GPU/ZAC perimeter collector
(``rei.ingestion.gpu.ZacCollector``) and the planning-document agent.
"""
from __future__ import annotations

import datetime as dt

import geopandas as gpd
import pandas as pd

REFERENCE_YEAR = dt.date.today().year

# Project type -> peak %-uplift potential for surrounding zones (mirrors the
# transport MODE_PROFILE philosophy). Business/transport-hub districts carry the
# strongest signal; parks and standalone facilities the lightest.
DEV_PROFILE: dict[str, float] = {
    "business_district": 0.14,
    "transport_hub_district": 0.13,
    "mixed_use_district": 0.12,
    "urban_renewal": 0.11,
    "large_housing": 0.10,
    "hospital": 0.10,
    "university": 0.09,
    "cultural": 0.06,
    "park": 0.05,
}
_MAX_BASE = max(DEV_PROFILE.values())


def dev_impact_score(ptype: str, years_to_completion: float, scale: float = 1.0) -> float:
    """0-100 impact score for a development project (type x imminence x scale).

    Same shape as ``rei.transport.impact.project_impact_score``: a ramp that is
    40% at announcement and reaches full weight by delivery, normalised so the
    strongest type at full ramp scores ~100. ``scale`` (~0.8-1.3) reflects the
    programme size (homes / floor area).
    """
    base = DEV_PROFILE.get(ptype)
    if base is None:
        return 0.0
    ramp = max(0.4, min(1.0, 1.0 - years_to_completion / 9.0))
    return round(max(0.0, min(100.0, base * ramp * scale / _MAX_BASE * 100.0)), 1)


# name, type, status, completion, lon, lat, dept, commune, scale, source, note
_DEV: list[tuple] = [
    ("ZAC Cœur Pleyel", "transport_hub_district", "under_construction", "2030-12-31", 2.346560, 48.917683, "93", "Saint-Denis", 1.20,
     "Plaine Commune Développement", "Tourism, leisure and offices around the Saint-Denis Pleyel GPE super-hub."),
    ("Village des Athlètes (Olympic legacy)", "mixed_use_district", "under_construction", "2026-12-31", 2.342000, 48.922000, "93", "Saint-Ouen-sur-Seine", 1.25,
     "SOLIDEO / Plaine Commune", "~2,800 homes plus offices; Olympic village converting to a new district 2025-26."),
    ("ZAC Campus Grand Parc", "mixed_use_district", "under_construction", "2030-12-31", 2.349366, 48.793044, "94", "Villejuif", 1.30,
     "Ville de Villejuif / EPA ORSA", "~3,100 homes + 173,000 m² offices around Villejuif IGR (M14/M15) and Gustave Roussy."),
    ("CHU Saint-Ouen Grand Paris Nord", "hospital", "under_construction", "2031-12-31", 2.334000, 48.912000, "93", "Saint-Ouen-sur-Seine", 1.20,
     "AP-HP / EPAURIF", "New university hospital (merges Bichat + Beaujon) + medical faculty + INSERM; works from 2026."),
    ("Campus Condorcet", "university", "under_construction", "2029-12-31", 2.373500, 48.917600, "93", "Aubervilliers", 1.00,
     "Campus Condorcet / EPAURIF", "Humanities & social-sciences campus; student residences delivering to 2029."),
    ("ZAC Charenton-Bercy", "mixed_use_district", "approved", "2032-12-31", 2.412000, 48.825000, "94", "Charenton-le-Pont", 1.15,
     "Grand Paris Aménagement", "~400,000 m² mixed programme; first-phase demolition 2027-28."),
    ("ZAC Bercy-Charenton", "mixed_use_district", "planned", "2033-12-31", 2.397000, 48.832000, "75", "Paris 12e", 1.15,
     "SEMAPA / Ville de Paris", "Major eastern-Paris extension; environmental authorisation 2025-26, first works 2026."),
    ("ZAC Ivry-Confluences", "urban_renewal", "under_construction", "2032-12-31", 2.392000, 48.812000, "94", "Ivry-sur-Seine", 1.20,
     "Grand-Orly Seine Bièvre / SADEV94", "145 ha riverfront reconversion; Prairie des Géants park delivered 2025, phased to ~2035."),
    ("Cœur d'Orly", "business_district", "under_construction", "2030-12-31", 2.367000, 48.733000, "94", "Paray-Vieille-Poste", 1.10,
     "Groupe ADP / Grand Paris Aménagement", "Business district at Orly airport (M14/GPE since 2024); offices, hotels, retail."),
    ("ZAC Victor Hugo (eco-district)", "large_housing", "under_construction", "2028-12-31", 2.318706, 48.802772, "92", "Bagneux", 1.00,
     "Vallée Sud Aménagement", "Eco-district around the Bagneux M4/M15 stations."),
    ("Fort d'Aubervilliers eco-district", "large_housing", "under_construction", "2030-12-31", 2.405437, 48.914163, "93", "Aubervilliers", 1.00,
     "Grand Paris Aménagement", "~1,900 homes + park on the former fort, at the M7/M15 station."),
    ("Seine Gare Vitry / Les Ardoines", "urban_renewal", "under_construction", "2031-12-31", 2.408832, 48.782302, "94", "Vitry-sur-Seine", 1.10,
     "EPA ORSA", "Riverfront industrial reconversion around the Ardoines M15/RER C station."),
    ("Bruneseau (Paris Rive Gauche nord)", "mixed_use_district", "under_construction", "2030-12-31", 2.382000, 48.826000, "75", "Paris 13e", 1.05,
     "SEMAPA", "High-density mixed-use cluster bridging Paris 13e and Ivry over the périphérique."),
    ("Clichy-Montfermeil NPNRU", "urban_renewal", "under_construction", "2030-12-31", 2.556592, 48.904653, "93", "Clichy-sous-Bois", 1.00,
     "ANRU / Grand Paris Aménagement", "National urban-renewal programme around the T4 and future M16 station."),
    ("Parc Chapelle Charbon", "park", "under_construction", "2030-12-31", 2.366000, 48.897000, "75", "Paris 18e", 0.80,
     "Ville de Paris / P&MA", "New 6.5 ha park (north-east Paris), phased delivery to ~2030."),
]


def seed_frame() -> gpd.GeoDataFrame:
    """Verified Grand Paris core development projects as a scored GeoDataFrame."""
    rows = []
    for (name, ptype, status, completion, lon, lat, dept, commune, scale, source, note) in _DEV:
        comp_date = dt.date.fromisoformat(completion)
        years = max(0.0, comp_date.year - REFERENCE_YEAR)
        rows.append({
            "project": name,
            "project_type": ptype,
            "status": status,
            "completion": comp_date,
            "code_dept": dept,
            "commune": commune,
            "description": note,
            "impact_score": dev_impact_score(ptype, years, scale),
            "source": source,
            "lon": lon,
            "lat": lat,
        })
    df = pd.DataFrame(rows)
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.pop("lon"), df.pop("lat")), crs=4326)
    return gdf
