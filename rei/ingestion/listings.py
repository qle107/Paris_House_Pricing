"""Property *listings* (for-sale / for-rent) → one geocoded point per advert, keyed to IRIS.

Unlike DVF (closed *sales*, open data), live *listings* with *asking* prices have no
free, legal bulk feed in France, and the big portals (SeLoger, LeBonCoin, Bien'ici)
protect their listing databases under the EU sui-generis right — scraping them at scale
has been sanctioned repeatedly (see LISTINGS_FEASIBILITY.md). So the data *source* here is
a pluggable adapter:

  * default  → a bundled SAMPLE feed, so the pipeline runs end-to-end with no key/scraper;
  * scraper  → a rate-limited TEMPLATE you point at a source you are entitled to crawl;
  * (api)    → drop in a licensed aggregator (MoteurImmo/Fluximmo) the same way.

Pick via env `REI_LISTINGS_PROVIDER` (sample|scraper). Each listing is normalised,
geocoded via BAN when it lacks coordinates, tagged with its IRIS by point-in-polygon,
and written to the `listings` table; the map renders a point per listing linked to `url`.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

import pandas as pd

from rei.common import store
from rei.common.db import upsert_dataframe
from rei.common.http import HttpClient
from rei.common.logging import get_logger
from rei.ingestion.ban import BanCollector
from rei.ingestion.base import Collector

log = get_logger("ingest.listings")

# Normalised schema (one row per advert). prix_m2 is €/m² for sales, monthly €/m² for rent.
COLUMNS = ["listing_id", "source", "url", "transaction", "type_local", "price",
           "surface", "rooms", "prix_m2", "address", "postcode", "code_commune",
           "lat", "lon", "posted_at"]
CONFLICT = ("listing_id",)


# --------------------------------------------------------------------------- providers
class ListingsProvider(ABC):
    """A source of raw listings. `fetch()` returns a DataFrame with at least
    listing_id, url, transaction (sale|rent), type_local, price, surface and
    either (lat, lon) or (address[, postcode])."""
    name = "provider"

    @abstractmethod
    def fetch(self, **kwargs) -> pd.DataFrame:
        ...


class SampleProvider(ListingsProvider):
    """Bundled synthetic IDF listings so the pipeline runs without any feed.
    Coordinates are real points; URLs are illustrative portal search pages."""
    name = "sample"

    def fetch(self, **kwargs) -> pd.DataFrame:
        return pd.DataFrame(_SAMPLE)


class ScraperProvider(ListingsProvider):
    """TEMPLATE for a self-operated scraper — intentionally NOT wired to any
    specific portal. Scraping SeLoger/LeBonCoin/Bien'ici breaches their ToS and
    sui-generis database right (LISTINGS_FEASIBILITY.md). Only point this at a
    source you are legally entitled to crawl, respect robots.txt, keep rps low,
    and implement parse() for that source's HTML/JSON."""
    name = "scraper"

    def __init__(self, base_url: str | None = None, rps: float = 0.2):
        self.base_url = base_url or os.environ.get("REI_LISTINGS_SCRAPE_URL", "")
        self.http = HttpClient(rps=rps)

    def fetch(self, pages: int = 1, **kwargs) -> pd.DataFrame:
        if not self.base_url:
            raise RuntimeError(
                "ScraperProvider needs REI_LISTINGS_SCRAPE_URL and a parse() implementation. "
                "See LISTINGS_FEASIBILITY.md before scraping any portal.")
        rows: list[dict] = []
        for page in range(1, pages + 1):
            html = self.http.get(self.base_url, params={"page": page}).text
            rows.extend(self.parse(html))
        return pd.DataFrame(rows)

    def parse(self, html: str) -> list[dict]:  # noqa: ARG002
        raise NotImplementedError(
            "Implement parse() for YOUR permitted source → list of dicts using the "
            "fields in COLUMNS. Do not target portals whose ToS forbid scraping.")


class BieniciProvider(ListingsProvider):
    """Self-operated reader for Bien'ici's public map JSON API, with rate-limited
    LAZY pagination (100/page, stop at `limit`, polite rps). OPT-IN only
    (FREI_LISTINGS_PROVIDER=bienici).

    ⚠️  Bien'ici listings are protected by its ToS and the EU sui-generis database
    right (see LISTINGS_FEASIBILITY.md). Bulk extraction has been sanctioned in
    France. Use only if you accept that risk, keep `REI_LISTINGS_RPS` low, and
    respect robots.txt. API shape reused from github.com/lobstrio/bieniciscraper (MIT);
    coordinates (blurInfo) + ad URL + surface are added here.

    Config (env): REI_LISTINGS_LOCATIONS="saint-ouen-93400,paris-11e",
    REI_LISTINGS_TRANSACTION=buy|rent|both, REI_LISTINGS_LIMIT=200, REI_LISTINGS_RPS=0.5.
    Bien'ici caps a search at 100 pages (~2,500 ads) — scope by commune to get more.
    """
    name = "bienici"
    SUGGEST = "https://res.bienici.com/suggest.json"
    ADS = "https://www.bienici.com/realEstateAds.json"
    HEADERS = {"accept": "*/*", "accept-language": "fr-FR,fr;q=0.9",
               "x-requested-with": "XMLHttpRequest",
               "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")}
    PTYPE = {"flat": "Appartement", "house": "Maison"}

    def __init__(self, rps: float | None = None):
        self.http = HttpClient(rps=rps if rps is not None else float(os.environ.get("REI_LISTINGS_RPS", "0.5")),
                               headers=self.HEADERS)
        self._zcache: dict = {}

    def _zone_ids(self, location: str) -> list:
        if location in self._zcache:          # one suggest call per location, reused across buy/rent
            return self._zcache[location]
        data = self.http.get_json(self.SUGGEST, params={"q": location})
        ids = data[0].get("zoneIds", []) if isinstance(data, list) and data else []
        self._zcache[location] = ids
        return ids

    def _page(self, zone_ids, filter_type, property_type, page, size=100):
        import json
        filters = {"size": size, "from": (page - 1) * size, "page": page, "onTheMarket": [True],
                   "filterType": filter_type, "propertyType": property_type,
                   "zoneIdsByTypes": {"zoneIds": zone_ids},
                   "sortBy": "publicationDate", "sortOrder": "desc"}
        return self.http.get_json(self.ADS, params={"filters": json.dumps(filters)})

    def _parse(self, ad: dict, filter_type: str) -> dict:
        pos = (ad.get("blurInfo") or {}).get("position") or {}
        rel = ad.get("userRelativeUrl") or ad.get("relativeUrl")
        url = ("https://www.bienici.com" + rel) if rel else f"https://www.bienici.com/annonce/{ad.get('id', '')}"
        ptype = ad.get("propertyType", "")
        return {"listing_id": f"bienici:{ad.get('id', '')}", "source": "bienici", "url": url,
                "transaction": "rent" if filter_type == "rent" else "sale",
                "type_local": self.PTYPE.get(ptype, ptype.title() if ptype else None),
                "price": ad.get("price"), "surface": ad.get("surfaceArea"), "rooms": ad.get("roomsQuantity"),
                "address": " ".join(str(x) for x in [ad.get("city"), ad.get("postalCode")] if x),
                "postcode": ad.get("postalCode"), "lat": pos.get("lat"), "lon": pos.get("lon"),
                "posted_at": ad.get("publicationDate")}

    def _auto_locations(self) -> list:
        """Every commune the project already covers — so 'fetch all' needs no commune input."""
        names = []
        try:
            g = store.read_geo("communes")
            if g is not None and not g.empty and "name" in g.columns:
                names = g["name"].dropna().astype(str).tolist()
        except Exception as exc:  # noqa: BLE001
            log.warning("bienici: communes geometry unavailable (%s)", exc)
        if not names:
            cs = store.read_table("commune_score")
            if cs is not None and not cs.empty and "name" in cs.columns:
                names = cs["name"].dropna().astype(str).tolist()
        return sorted(set(names))

    @staticmethod
    def _paris_arrondissements() -> list:
        """The 20 Paris arrondissements as Bien'ici name-postcode slugs (paris-75001 .. paris-75020)."""
        return [f"paris-{75000 + n}" for n in range(1, 21)]

    def _resolve_locations(self) -> list:
        """Priority: explicit list → SCOPE=paris → ALL (every covered commune) → single default."""
        env = os.environ.get("REI_LISTINGS_LOCATIONS", "").strip()
        if env:
            return [s for s in env.split(",") if s]
        scope = os.environ.get("REI_LISTINGS_SCOPE", "").lower()
        if scope == "paris":
            return self._paris_arrondissements()
        if scope in ("all", "idf") or os.environ.get("REI_LISTINGS_ALL", "").lower() in ("1", "true", "yes"):
            locs = self._auto_locations()
            cap = int(os.environ.get("REI_LISTINGS_MAX_COMMUNES", "0") or 0)
            log.info("bienici: 'all' mode → %d communes from project data%s",
                     len(locs), f" (capped to {cap})" if cap else "")
            return locs[:cap] if cap else locs
        return ["saint-ouen-93400"]

    @staticmethod
    def _transactions(transaction) -> list:
        """buy | rent | both → the filterType(s) to fetch in one run."""
        tx = (transaction or os.environ.get("REI_LISTINGS_TRANSACTION", "buy")).lower()
        if tx in ("both", "all", "buy+rent", "buyrent"):
            return ["buy", "rent"]
        return ["rent" if tx in ("rent", "location") else "buy"]

    def fetch(self, locations=None, transaction=None, limit=None, max_pages=100, per_commune=None, **kwargs) -> pd.DataFrame:
        locations = locations or self._resolve_locations()
        fts = self._transactions(transaction)
        limit = int(limit or os.environ.get("REI_LISTINGS_LIMIT", "2000"))
        per_commune = int(per_commune or os.environ.get("REI_LISTINGS_PER_COMMUNE", "50"))
        size = int(os.environ.get("REI_LISTINGS_PAGE_SIZE", "100"))   # larger page = fewer requests
        rows: list[dict] = []
        for ft in fts:
            for i, loc in enumerate(locations):
                if len(rows) >= limit:
                    break
                zone_ids = self._zone_ids(loc.strip())
                if not zone_ids:
                    log.warning("bienici: no zoneIds for '%s' (skipped)", loc)
                    continue
                got = 0
                for page in range(1, max_pages + 1):
                    data = self._page(zone_ids, ft, ["flat", "house"], page, size) or {}
                    ads = data.get("realEstateAds", [])
                    if not ads:
                        break
                    rows.extend(self._parse(a, ft) for a in ads)
                    got += len(ads)
                    if got >= per_commune or len(rows) >= limit or got >= (data.get("total") or 0):
                        break
                if (i + 1) % 25 == 0:
                    log.info("bienici: %s %d/%d communes scanned, %d ads so far", ft, i + 1, len(locations), len(rows))
        log.info("bienici: fetched %d ads from %d location(s) x [%s]", len(rows), len(locations), "+".join(fts))
        return pd.DataFrame(rows[:limit])


def get_provider(name: str | None = None) -> ListingsProvider:
    name = (name or os.environ.get("REI_LISTINGS_PROVIDER", "sample")).lower()
    return {"sample": SampleProvider, "scraper": ScraperProvider,
            "bienici": BieniciProvider}.get(name, SampleProvider)()


# --------------------------------------------------------------------------- collector
class ListingsCollector(Collector):
    source_id = "listings"
    rps = 5.0

    def _normalise(self, raw: pd.DataFrame) -> pd.DataFrame:
        df = raw.copy()
        for c in COLUMNS:
            if c not in df.columns:
                df[c] = pd.NA
        for c in ("price", "surface", "rooms", "lat", "lon"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["transaction"] = df["transaction"].fillna("sale")
        # prix_m2 from price/surface when not supplied
        m = df["prix_m2"].isna() & df["surface"].gt(0)
        df.loc[m, "prix_m2"] = (df.loc[m, "price"] / df.loc[m, "surface"]).round(0)
        df = df.dropna(subset=["listing_id"]).drop_duplicates(subset=["listing_id"])
        return df

    def _geocode_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        need = df[df["lat"].isna() | df["lon"].isna()]
        if need.empty:
            return df
        try:
            q = need.reset_index()[["address", "postcode"]].astype(str)
            res = BanCollector().geocode_dataframe(q, columns=["address"])
            df.loc[need.index, "lat"] = pd.to_numeric(res["latitude"], errors="coerce").values
            df.loc[need.index, "lon"] = pd.to_numeric(res["longitude"], errors="coerce").values
            self.log.info("geocoded %d listings via BAN", len(need))
        except Exception as exc:  # noqa: BLE001 - geocoding is best-effort
            self.log.warning("BAN geocode skipped (%s); %d listings left un-located", exc, len(need))
        return df

    def collect(self, provider=None, **kwargs) -> int:
        prov = provider if isinstance(provider, ListingsProvider) else get_provider(provider)
        raw = prov.fetch(**kwargs)
        if raw is None or raw.empty:
            self.log.warning("provider '%s' returned no listings", getattr(prov, "name", prov))
            return 0
        df = self._geocode_missing(self._normalise(raw))
        df = df.dropna(subset=["lat", "lon"])
        if df.empty:
            self.log.warning("no listings with coordinates after geocoding")
            return 0
        df = _assign_iris(df)
        keep = [c for c in COLUMNS + ["iris_code", "iris_name"] if c in df.columns]
        out = df[keep]
        self.log.info("listings ready: %d (provider=%s)", len(out), getattr(prov, "name", prov))
        self._save_snapshot(out)
        return upsert_dataframe(out, "listings", conflict_cols=CONFLICT)

    def _save_snapshot(self, df: pd.DataFrame) -> None:
        """Archive a dated copy under data/listings_snapshots/ so listings accumulate over
        time — enables later price-change / new-vs-removed / time-on-market analysis."""
        try:
            from datetime import date
            from config.settings import settings
            d = settings.data_dir / "listings_snapshots"
            d.mkdir(parents=True, exist_ok=True)
            stamp = date.today().isoformat()
            df.to_parquet(d / f"listings_{stamp}.parquet", index=False)
            df.to_csv(d / f"listings_{stamp}.csv", index=False, encoding="utf-8-sig")
            self.log.info("snapshot saved: data/listings_snapshots/listings_%s (%d rows)", stamp, len(df))
        except Exception as exc:  # noqa: BLE001 - snapshot is best-effort
            self.log.warning("snapshot skipped (%s)", exc)


def _assign_iris(df: pd.DataFrame) -> pd.DataFrame:
    """Point-in-polygon: tag each listing with its IRIS (and the IRIS commune)."""
    import geopandas as gpd
    iris = store.read_geo("iris")
    df = df.copy()
    if iris is None or iris.empty:
        log.warning("no IRIS geometry loaded; listings left without iris_code")
        df["iris_code"] = pd.NA
        return df
    cols = [c for c in ["iris_code", "iris_name", "code_commune", "geometry"] if c in iris.columns]
    irisj = iris[cols].to_crs(4326).rename(columns={"code_commune": "iris_commune"})
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326)
    j = gpd.sjoin(pts, irisj, how="left", predicate="within")
    j = pd.DataFrame(j).drop(columns=["geometry", "index_right"], errors="ignore")
    if "iris_commune" in j.columns:  # IRIS commune is authoritative where a point joined
        j["code_commune"] = j["iris_commune"].fillna(j.get("code_commune"))
        j = j.drop(columns=["iris_commune"])
    return j


# --------------------------------------------------------------------------- sample data
# Illustrative IDF listings (synthetic ids, real coordinates, real portal search-page URLs).
# Replace by setting REI_LISTINGS_PROVIDER=scraper (+ a parse()) or a licensed API adapter.
_SAMPLE = [
    {"listing_id": "S-75111-1001", "source": "sample", "transaction": "sale", "type_local": "Appartement",
     "price": 612000, "surface": 56, "rooms": 3, "address": "Rue Saint-Ambroise, Paris 11e", "postcode": "75011",
     "code_commune": "75111", "lat": 48.8607, "lon": 2.3760,
     "url": "https://www.bienici.com/recherche/achat/paris-11e", "posted_at": "2026-06-18"},
    {"listing_id": "S-75118-1002", "source": "sample", "transaction": "sale", "type_local": "Appartement",
     "price": 408000, "surface": 41, "rooms": 2, "address": "Rue Ordener, Paris 18e", "postcode": "75018",
     "code_commune": "75118", "lat": 48.8920, "lon": 2.3444,
     "url": "https://www.bienici.com/recherche/achat/paris-18e", "posted_at": "2026-06-15"},
    {"listing_id": "S-92012-1003", "source": "sample", "transaction": "sale", "type_local": "Appartement",
     "price": 742000, "surface": 84, "rooms": 4, "address": "Rue de Billancourt, Boulogne-Billancourt", "postcode": "92100",
     "code_commune": "92012", "lat": 48.8350, "lon": 2.2400,
     "url": "https://www.bienici.com/recherche/achat/boulogne-billancourt-92100", "posted_at": "2026-06-12"},
    {"listing_id": "S-92040-1004", "source": "sample", "transaction": "sale", "type_local": "Appartement",
     "price": 451000, "surface": 55, "rooms": 3, "address": "Rue du Général Leclerc, Issy-les-Moulineaux", "postcode": "92130",
     "code_commune": "92040", "lat": 48.8240, "lon": 2.2730,
     "url": "https://www.bienici.com/recherche/achat/issy-les-moulineaux-92130", "posted_at": "2026-06-20"},
    {"listing_id": "S-93070-1005", "source": "sample", "transaction": "sale", "type_local": "Appartement",
     "price": 330000, "surface": 50, "rooms": 2, "address": "Avenue Gabriel Péri, Saint-Ouen-sur-Seine", "postcode": "93400",
     "code_commune": "93070", "lat": 48.9100, "lon": 2.3340,
     "url": "https://www.bienici.com/recherche/achat/saint-ouen-sur-seine-93400", "posted_at": "2026-06-19"},
    {"listing_id": "S-93066-1006", "source": "sample", "transaction": "sale", "type_local": "Appartement",
     "price": 301000, "surface": 55, "rooms": 3, "address": "Rue du Landy, Saint-Denis (Pleyel)", "postcode": "93200",
     "code_commune": "93066", "lat": 48.9190, "lon": 2.3430,
     "url": "https://www.bienici.com/recherche/achat/saint-denis-93200", "posted_at": "2026-06-21"},
    {"listing_id": "S-93048-1007", "source": "sample", "transaction": "sale", "type_local": "Maison",
     "price": 489000, "surface": 84, "rooms": 4, "address": "Rue de Paris, Montreuil", "postcode": "93100",
     "code_commune": "93048", "lat": 48.8610, "lon": 2.4430,
     "url": "https://www.bienici.com/recherche/achat/montreuil-93100", "posted_at": "2026-06-10"},
    {"listing_id": "S-78646-1008", "source": "sample", "transaction": "sale", "type_local": "Appartement",
     "price": 455000, "surface": 65, "rooms": 3, "address": "Avenue de Saint-Cloud, Versailles", "postcode": "78000",
     "code_commune": "78646", "lat": 48.8014, "lon": 2.1301,
     "url": "https://www.bienici.com/recherche/achat/versailles-78000", "posted_at": "2026-06-17"},
    {"listing_id": "S-77284-1009", "source": "sample", "transaction": "sale", "type_local": "Maison",
     "price": 268000, "surface": 90, "rooms": 4, "address": "Rue Saint-Rémy, Meaux", "postcode": "77100",
     "code_commune": "77284", "lat": 48.9606, "lon": 2.8783,
     "url": "https://www.bienici.com/recherche/achat/meaux-77100", "posted_at": "2026-06-09"},
    {"listing_id": "R-75111-2001", "source": "sample", "transaction": "rent", "type_local": "Appartement",
     "price": 1450, "surface": 38, "rooms": 2, "address": "Boulevard Voltaire, Paris 11e", "postcode": "75011",
     "code_commune": "75111", "lat": 48.8585, "lon": 2.3790,
     "url": "https://www.bienici.com/recherche/location/paris-11e", "posted_at": "2026-06-22"},
    {"listing_id": "R-94028-2002", "source": "sample", "transaction": "rent", "type_local": "Appartement",
     "price": 1180, "surface": 62, "rooms": 3, "address": "Avenue de Verdun, Créteil", "postcode": "94000",
     "code_commune": "94028", "lat": 48.7900, "lon": 2.4550,
     "url": "https://www.bienici.com/recherche/location/creteil-94000", "posted_at": "2026-06-16"},
]
