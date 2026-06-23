"""ANIL carte des loyers (commune-level asking rents)."""
from __future__ import annotations

import io

import pandas as pd

from rei.common.db import upsert_dataframe
from rei.ingestion.base import Collector

DATAGOUV = "https://www.data.gouv.fr/api/1"
SLUG_PREFIX = "carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-"


class RentObservatoryCollector(Collector):
    source_id = "rental_observatoires"
    rps = 4.0

    def _latest_slug(self) -> str:
        """Resolve the most recent yearly 'carte des loyers' dataset slug."""
        meta = self.http.get_json(
            f"{DATAGOUV}/datasets/",
            params={"q": "carte des loyers indicateurs de loyers", "page_size": 30},
        )
        years = []
        for d in meta.get("data", []):
            slug = d.get("slug", "")
            tail = slug[len(SLUG_PREFIX):] if slug.startswith(SLUG_PREFIX) else ""
            if tail.isdigit():
                years.append((int(tail), slug))
        if not years:
            raise RuntimeError("No 'carte des loyers' dataset found on data.gouv.fr")
        slug = max(years)[1]
        self.log.info("Latest carte-des-loyers dataset: %s", slug)
        return slug

    def collect(self, communes: list[str] | None = None,
                departements: list[str] | None = None) -> int:
        meta = self.http.get_json(f"{DATAGOUV}/datasets/{self._latest_slug()}/")
        csvs = [r for r in meta.get("resources", []) if (r.get("format") or "").lower().startswith("csv")]
        if not csvs:
            return 0
        csvs.sort(key=lambda r: ("appart" in (r.get("title") or r.get("url") or "").lower(),
                                 r.get("last_modified", "")), reverse=True)
        resp = self.http.get(csvs[0]["url"])
        df = pd.read_csv(io.BytesIO(resp.content), sep=";", low_memory=False, encoding="latin-1")  # ISO-8859-1
        df.columns = [c.lower() for c in df.columns]
        comm = next((c for c in ["insee_c", "code_commune", "depcom", "insee"] if c in df.columns), None)
        if comm is None:
            return 0
        df = df.rename(columns={comm: "code_commune"})
        df["code_commune"] = df["code_commune"].astype(str)
        if departements:
            df = df[df["code_commune"].str[:2].isin(set(departements))]
        elif communes:
            df = df[df["code_commune"].isin(communes)]
        keep = [c for c in df.columns if c in ("code_commune",) or "loyer" in c or "loypredm2" in c]
        return upsert_dataframe(df[keep].drop_duplicates("code_commune"), "rents", conflict_cols=("code_commune",))
