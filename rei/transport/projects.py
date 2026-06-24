"""Forward-looking transport projects for the Grand Paris core (75/92/93/94).

Verified seed of Grand Paris Express (GPE) stations plus the Tram T1 east
extension. Station coordinates are the official Societe des Grands Projets (SGP)
positions republished by Ile-de-France Mobilites open data ("Point de
localisation des gares du Grand Paris Express"); line status and opening dates
are the June 2026 view (see ``seeds/README.md`` and
``docs/URBAN_DEVELOPMENT_INTELLIGENCE.md`` for the source list).

``seed_frame()`` returns a GeoDataFrame ready for ``write_geo(..., "transport_projects")``
with a per-station ``impact_score`` from ``rei.transport.impact.project_impact_score``.
"""
from __future__ import annotations

import datetime as dt

import geopandas as gpd
import pandas as pd

from rei.transport.impact import project_impact_score

REFERENCE_YEAR = dt.date.today().year

# Official coordinate source baked into every record.
_SRC = "Societe des Grands Projets / Ile-de-France Mobilites open data (gares GPE, RGF93)"

# project, line, station, opening, status, lon, lat, dept, commune, hub_bonus, note
# hub_bonus: 0 standard, 8 interchange, 12 major hub, 15 multi-line super-hub.
_GPE: list[tuple] = [
    # --- Line 15 South (Pont de Sevres - Noisy-Champs): testing, opening Apr 2027 ---
    ("GPE L15 Sud", "15", "Pont de Sevres", "2027-04-01", "commissioning", 2.230480, 48.827291, "92", "Boulogne-Billancourt", 8, "Western terminus, interchange with M9."),
    ("GPE L15 Sud", "15", "Issy RER", "2027-04-01", "commissioning", 2.259940, 48.821096, "92", "Issy-les-Moulineaux", 8, "Interchange with RER C."),
    ("GPE L15 Sud", "15", "Fort d'Issy-Vanves-Clamart", "2027-04-01", "commissioning", 2.273536, 48.814068, "92", "Clamart", 8, "Interchange with Transilien N."),
    ("GPE L15 Sud", "15", "Chatillon-Montrouge", "2027-04-01", "commissioning", 2.302360, 48.811218, "92", "Chatillon", 8, "Interchange with M13."),
    ("GPE L15 Sud", "15", "Bagneux", "2027-04-01", "commissioning", 2.318706, 48.802772, "92", "Bagneux", 8, "Interchange with M4; Victor Hugo eco-district."),
    ("GPE L15 Sud", "15", "Arcueil-Cachan", "2027-04-01", "commissioning", 2.328342, 48.797458, "94", "Arcueil", 8, "Interchange with RER B."),
    ("GPE L15 Sud", "15", "Villejuif Institut Gustave Roussy", "2027-04-01", "commissioning", 2.349366, 48.793044, "94", "Villejuif", 12, "M14 + M15 hub; Campus Grand Parc / Gustave Roussy."),
    ("GPE L15 Sud", "15", "Villejuif Louis Aragon", "2027-04-01", "commissioning", 2.367221, 48.788468, "94", "Villejuif", 8, "Interchange with M7."),
    ("GPE L15 Sud", "15", "Vitry Centre", "2027-04-01", "commissioning", 2.387039, 48.789990, "94", "Vitry-sur-Seine", 0, "New station, town centre."),
    ("GPE L15 Sud", "15", "Les Ardoines", "2027-04-01", "commissioning", 2.408832, 48.782302, "94", "Vitry-sur-Seine", 8, "RER C; Ardoines ZAC riverfront renewal."),
    ("GPE L15 Sud", "15", "Le Vert de Maisons", "2027-04-01", "commissioning", 2.433005, 48.789269, "94", "Maisons-Alfort", 8, "Interchange with RER D."),
    ("GPE L15 Sud", "15", "Creteil L'Echat", "2027-04-01", "commissioning", 2.449883, 48.795436, "94", "Creteil", 8, "M8 + Henri Mondor hospital."),
    ("GPE L15 Sud", "15", "Saint-Maur-Creteil", "2027-04-01", "commissioning", 2.472649, 48.806702, "94", "Saint-Maur-des-Fosses", 8, "RER A; station phased slightly later."),
    ("GPE L15 Sud", "15", "Champigny Centre", "2027-04-01", "commissioning", 2.502041, 48.816200, "94", "Champigny-sur-Marne", 8, "Junction with L15 East."),
    ("GPE L15 Sud", "15", "Bry-Villiers-Champigny", "2027-04-01", "commissioning", 2.526383, 48.823987, "94", "Villiers-sur-Marne", 8, "Future RER E interchange."),
    ("GPE L15 Sud", "15", "Noisy-Champs", "2027-04-01", "commissioning", 2.580787, 48.843455, "93", "Noisy-le-Grand", 12, "RER A; eastern terminus, shared with L16."),
    # --- Line 15 West (Pont de Sevres - Saint-Denis Pleyel): under construction, ~2030 ---
    ("GPE L15 Ouest", "15", "Saint-Cloud", "2030-12-31", "under_construction", 2.217139, 48.844091, "92", "Saint-Cloud", 8, "Transilien L/U interchange."),
    ("GPE L15 Ouest", "15", "Rueil-Suresnes Mont-Valerien", "2030-12-31", "under_construction", 2.202130, 48.872481, "92", "Rueil-Malmaison", 0, "New station."),
    ("GPE L15 Ouest", "15", "Nanterre La Boule", "2030-12-31", "under_construction", 2.201417, 48.887772, "92", "Nanterre", 0, "New station, town centre."),
    ("GPE L15 Ouest", "15", "Nanterre La Folie", "2030-12-31", "under_construction", 2.226481, 48.898239, "92", "Nanterre", 8, "RER E (EOLE) interchange."),
    ("GPE L15 Ouest", "15", "La Defense", "2030-12-31", "under_construction", 2.237688, 48.890854, "92", "Puteaux", 12, "Major business-district hub (RER A/E, M1, T2)."),
    ("GPE L15 Ouest", "15", "Becon-les-Bruyeres", "2030-12-31", "under_construction", 2.267019, 48.905329, "92", "Courbevoie", 8, "Transilien L interchange."),
    ("GPE L15 Ouest", "15", "Bois-Colombes", "2030-12-31", "under_construction", 2.272014, 48.914987, "92", "Bois-Colombes", 8, "Transilien J interchange."),
    ("GPE L15 Ouest", "15", "Les Agnettes", "2030-12-31", "under_construction", 2.287632, 48.922467, "92", "Asnieres-sur-Seine", 8, "Interchange with M13."),
    ("GPE L15 Ouest", "15", "Les Gresillons", "2030-12-31", "under_construction", 2.313045, 48.919973, "92", "Gennevilliers", 8, "RER C interchange."),
    # --- Saint-Denis Pleyel super-hub (L14 open; L15/L16/L17) ---
    ("GPE Saint-Denis Pleyel", "14/15/16/17", "Saint-Denis Pleyel", "2027-06-30", "under_construction", 2.346560, 48.917683, "93", "Saint-Denis", 15, "Quad-line GPE super-hub; Pleyel renewal + Olympic legacy."),
    # --- Line 15 East (Saint-Denis Pleyel - Champigny): under construction, ~2031 ---
    ("GPE L15 Est", "15", "Stade de France", "2031-12-31", "under_construction", 2.363380, 48.918015, "93", "Saint-Denis", 8, "RER B/D area; Plaine Saint-Denis."),
    ("GPE L15 Est", "15", "Mairie d'Aubervilliers", "2031-12-31", "under_construction", 2.381799, 48.914172, "93", "Aubervilliers", 8, "Interchange with M12."),
    ("GPE L15 Est", "15", "Fort d'Aubervilliers", "2031-12-31", "under_construction", 2.405437, 48.914163, "93", "Aubervilliers", 8, "M7; Fort d'Aubervilliers eco-district."),
    ("GPE L15 Est", "15", "Drancy-Bobigny", "2031-12-31", "under_construction", 2.427073, 48.915809, "93", "Drancy", 0, "New station."),
    ("GPE L15 Est", "15", "Bobigny Pablo Picasso", "2031-12-31", "under_construction", 2.450070, 48.906309, "93", "Bobigny", 8, "M5 + T1 interchange."),
    ("GPE L15 Est", "15", "Pont de Bondy", "2031-12-31", "under_construction", 2.469731, 48.904265, "93", "Bondy", 8, "T1; Canal de l'Ourcq renewal."),
    ("GPE L15 Est", "15", "Bondy", "2031-12-31", "under_construction", 2.480199, 48.894259, "93", "Bondy", 8, "RER E + T4 interchange."),
    ("GPE L15 Est", "15", "Rosny Bois-Perrier", "2031-12-31", "under_construction", 2.481742, 48.882738, "93", "Rosny-sous-Bois", 12, "RER E + M11 (since 2024); regional mall renewal."),
    ("GPE L15 Est", "15", "Val de Fontenay", "2031-12-31", "under_construction", 2.489657, 48.855919, "94", "Fontenay-sous-Bois", 12, "RER A + RER E major hub."),
    ("GPE L15 Est", "15", "Nogent-Le Perreux", "2031-12-31", "under_construction", 2.494725, 48.839023, "94", "Nogent-sur-Marne", 8, "RER E interchange."),
    # --- Line 16 (Saint-Denis Pleyel - Noisy-Champs): under construction, first section 2027 ---
    ("GPE L16", "16", "La Courneuve Six Routes", "2027-06-30", "under_construction", 2.384491, 48.929252, "93", "La Courneuve", 8, "T1; shared L16/L17 trunk."),
    ("GPE L16", "16", "Le Bourget RER", "2027-06-30", "under_construction", 2.422115, 48.930580, "93", "Le Bourget", 12, "RER B; L16/L17 hub, Bourget renewal."),
    ("GPE L16", "16", "Le Blanc-Mesnil", "2027-06-30", "under_construction", 2.462742, 48.945530, "93", "Le Blanc-Mesnil", 0, "New station."),
    ("GPE L16", "16", "Aulnay", "2027-06-30", "under_construction", 2.487857, 48.951838, "93", "Aulnay-sous-Bois", 8, "RER B interchange."),
    ("GPE L16", "16", "Sevran-Beaudottes", "2028-12-31", "under_construction", 2.525529, 48.947215, "93", "Sevran", 8, "RER B; NPNRU renewal area."),
    ("GPE L16", "16", "Sevran-Livry", "2028-12-31", "under_construction", 2.535318, 48.935846, "93", "Sevran", 8, "RER B interchange."),
    ("GPE L16", "16", "Clichy-Montfermeil", "2028-12-31", "under_construction", 2.556592, 48.904653, "93", "Clichy-sous-Bois", 8, "T4; major NPNRU urban-renewal site."),
    # --- Line 17 (Saint-Denis Pleyel - Le Bourget, then north to CDG): under construction ---
    ("GPE L17", "17", "Le Bourget Aeroport", "2028-12-31", "under_construction", 2.436410, 48.946702, "93", "Le Bourget", 8, "Le Bourget airport / exhibition park."),
    # --- Tram T1 east extension (approx. positions; not in the GPE coordinate set) ---
    ("Tram T1 Est (ph.1)", "T1", "Montreuil (Rue de Rosny)", "2026-12-31", "commissioning", 2.452000, 48.862500, "93", "Montreuil", 0, "Bobigny-Montreuil extension; approximate position."),
    ("Tram T1 Est (ph.2)", "T1", "Val de Fontenay (T1)", "2029-12-31", "planned", 2.489700, 48.855900, "94", "Fontenay-sous-Bois", 8, "Extension to Val de Fontenay; approximate position."),
]


def seed_frame() -> gpd.GeoDataFrame:
    """Verified Grand Paris core transport projects as a scored GeoDataFrame."""
    rows = []
    for (project, line, station, opening, status, lon, lat, dept, commune, hub, note) in _GPE:
        mode = "tram" if line.startswith("T") else "metro"
        open_date = dt.date.fromisoformat(opening)
        years_to_open = max(0.0, open_date.year - REFERENCE_YEAR)
        rows.append({
            "project": project,
            "line": line,
            "station": station,
            "mode": mode,
            "opening": open_date,
            "status": status,
            "code_dept": dept,
            "commune": commune,
            "description": f"{project} {mode} station ({status.replace('_', ' ')}), "
                           f"opening {open_date:%Y-%m}. {note}".strip(),
            "impact_score": project_impact_score(mode, years_to_open, hub_bonus=hub),
            "source": _SRC,
            "lon": lon,
            "lat": lat,
        })
    df = pd.DataFrame(rows)
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.pop("lon"), df.pop("lat")), crs=4326)
    return gdf
