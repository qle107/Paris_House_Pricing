"""INSEE SIRENE establishments and business creation."""
from __future__ import annotations

import pandas as pd

from config.settings import settings
from rei.common.db import upsert_dataframe
from rei.ingestion.base import Collector

SIRENE = "https://api.insee.fr/api-sirene/3.11"


class SireneCollector(Collector):
    source_id = "sirene_businesses"
    rps = 0.5  # 30/min on the free tier

    def __init__(self):
        super().__init__()
        if settings.insee_sirene_key:
            self.http.session.headers["X-INSEE-Api-Key-Integration"] = settings.insee_sirene_key

    def creations_since(self, insee: str, since: str) -> pd.DataFrame:
        """Establishments created in a commune since `since` (YYYY-MM-DD)."""
        q = f'codeCommuneEtablissement:{insee} AND dateCreationEtablissement:[{since} TO *]'
        rows: list[dict] = []
        cursor = "*"
        while True:
            payload = self.http.get_json(
                f"{SIRENE}/siret",
                params={"q": q, "nombre": 1000, "curseur": cursor},
            )
            etabs = payload.get("etablissements", [])
            rows.extend(etabs)
            nxt = payload.get("header", {}).get("curseurSuivant")
            if not nxt or nxt == cursor or not etabs:
                break
            cursor = nxt
        return pd.json_normalize(rows)

    def collect(self, communes: list[str] | None = None, since: str = "2020-01-01") -> int:
        if not settings.insee_sirene_key:
            self.log.warning("No SIRENE key set; register a free app at portail-api.insee.fr")
            return 0
        if not communes:
            raise ValueError("SireneCollector requires `communes`")
        frames = [self.creations_since(c, since) for c in communes]
        df = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()
        if df.empty:
            return 0
        df = df.rename(columns={"siret": "siret", "etablissement.codeCommuneEtablissement": "code_commune"})
        keep = [c for c in df.columns if c in ("siret", "code_commune") or "dateCreation" in c or "activitePrincipale" in c]
        return upsert_dataframe(df[keep], "establishments", conflict_cols=("siret",))
