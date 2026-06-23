"""Base Adresse Nationale geocoding."""
from __future__ import annotations

import io

import pandas as pd

from rei.ingestion.base import Collector

API = "https://api-adresse.data.gouv.fr"


class BanCollector(Collector):
    source_id = "ban_addresses"
    rps = 10.0

    def geocode_one(self, query: str, postcode: str | None = None) -> dict:
        params = {"q": query, "limit": 1}
        if postcode:
            params["postcode"] = postcode
        feats = self.http.get_json(f"{API}/search/", params=params).get("features", [])
        if not feats:
            return {}
        f = feats[0]
        lon, lat = f["geometry"]["coordinates"]
        p = f["properties"]
        return {"lat": lat, "lon": lon, "score": p.get("score"), "citycode": p.get("citycode")}

    def geocode_dataframe(
        self, df: pd.DataFrame, columns: list[str], result_columns=("latitude", "longitude", "result_score", "result_citycode")
    ) -> pd.DataFrame:
        """Bulk-geocode using the CSV endpoint. `columns` are the address parts."""
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        files = {"data": ("addresses.csv", buf.getvalue(), "text/csv")}
        data = [("columns", c) for c in columns] + [("result_columns", c) for c in result_columns]
        resp = self.http.request("POST", f"{API}/search/csv/", files=files, data=data)
        return pd.read_csv(io.StringIO(resp.text))

    def collect(self, df: pd.DataFrame | None = None, columns: list[str] | None = None) -> int:
        """Geocode an address frame; result stored in self.last_result."""
        if df is None or not columns:
            raise ValueError("BanCollector.collect requires `df` and `columns`")
        self.last_result = self.geocode_dataframe(df, columns)
        return len(self.last_result)
