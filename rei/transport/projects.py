"""Grand Paris Express and other transport project seeds."""
from __future__ import annotations

import pandas as pd

GPE_SEED = [
    {"project": "GPE L15 Sud", "line": "15", "mode": "metro", "opening": "2026-01-01", "status": "commissioning"},
    {"project": "GPE L16",     "line": "16", "mode": "metro", "opening": "2026-12-31", "status": "under_construction"},
    {"project": "GPE L17",     "line": "17", "mode": "metro", "opening": "2027-12-31", "status": "under_construction"},
    {"project": "GPE L18",     "line": "18", "mode": "metro", "opening": "2026-12-31", "status": "under_construction"},
    {"project": "GPE L15 Ouest","line": "15", "mode": "metro", "opening": "2030-12-31", "status": "planned"},
    {"project": "GPE L15 Est", "line": "15", "mode": "metro", "opening": "2031-12-31", "status": "planned"},
    {"project": "M14 Sud (Orly)","line": "14","mode": "metro", "opening": "2024-06-24", "status": "commissioning"},
]


def seed_frame() -> pd.DataFrame:
    """Return the seed as a DataFrame (station name + coordinates to be enriched)."""
    df = pd.DataFrame(GPE_SEED)
    df["opening"] = pd.to_datetime(df["opening"]).dt.date
    df["station"] = None  # fill per-station from the official station layer
    return df
