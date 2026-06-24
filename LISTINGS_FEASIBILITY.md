# Feasibility: live property listings (for sale and rent) per IRIS

Date: 2026-06-24

Question: can we fetch or scrape what houses and apartments are listed on the market and their asking prices, and plot a point per listing keyed to address and IRIS?

Short answer: yes. The clean route is a licensed aggregator API; a self-operated scraper is possible but carries real legal risk, and either way the address precision is limited because portals mask exact locations. This is not legal advice; confirm with counsel before signing anything or scraping.

What the project ended up using: no paid API. We built a pluggable listings source with a self-operated Bien'ici reader, opt-in and rate-limited. See `rei/ingestion/listings.py` and the README "Property listings" section. The analysis below is why.

## 1. The key distinction

The pipeline already ingests DVF, which is completed sales: actual transacted €/m², geocoded to the parcel. Listings are the other half of the market.

| | DVF (have) | Listings (want) |
|---|---|---|
| Event | sale closed | property on the market |
| Price | transacted | asking |
| Timing | about 6 to 18 months lag (biannual) | real-time |
| Location | exact (parcel) | deliberately approximate |
| Source | DGFiP open data | private portals |

The gap between asking and DVF-sold (the negotiation discount), plus days-on-market and active-supply count, are useful signals the current model lacks. They would sharpen the liquidity, rental-demand, and value-trap scores, so the motivation is sound.

## 2. Source landscape

The portals directly: SeLoger, LeBonCoin, Bien'ici, PAP, Logic-Immo. There is no official public listings API. France has no MLS; supply is scattered across more than 900 portals and agency sites. The only do-it-yourself way in is scraping, which is repeatedly litigated and lost (see the legal section).

Licensed aggregator APIs, the clean route. These third parties already aggregate the portals and resell a de-duplicated feed with coordinates and price per m². They carry the access and compliance burden.

| Provider | Coverage (advertised) | Access | Notes |
|---|---|---|---|
| MoteurImmo | 500k+ live listings, 70+ sources | REST API | Cheapest on the market, from €99/month, about €0.003/item at volume, three months free via a startup program |
| Fluximmo | 40M+ listings and transactions | API, webhook, daily export | Polygon and radius geo-search, under 100 ms, price-change events |
| Stream Estate | 1,500+ sources, 50M+ properties, 50k new per day | Event webhooks | Premium, best real-time breadth |
| Yanport, PriceHubble, Casafari | listings plus valuation | Commercial API | Heavier, valuation-oriented, enterprise pricing |
| Castorus | asking-price history and price drops | Consumer web tool, no clean API | Useful concept reference; refreshes every 24 to 48 hours |

Public and open data: none for listings. DVF, DV3F, Cadastre, BAN, DPE, and Géorisques are open, but they describe sold or physical attributes, not asking listings. There is no open "what is for sale today" feed.

## 3. Legality of scraping the portals

Under the EU Database Directive 96/9/EC (French law 98-536), portals hold a sui generis database right. French courts have consistently ruled that extracting a substantial part of these listing databases is infringement (contrefaçon):

- LeBonCoin v. Entreparticuliers, Paris Court of Appeal, 2 February 2021: €50k plus €20k damages for daily scraping and redistribution of listings.
- SeLoger and LeBonCoin v. Jinka, Nanterre 2024, confirmed by the Versailles Court of Appeal in December 2025: automated extraction ordered to cease, qualified as counterfeiting.
- LeBonCoin v. Jinka (Babel France), Versailles Court of Appeal, 14 April 2026: €200,000 damages.

On top of the database right: portal terms of service prohibit automated access, listings can contain personal data (GDPR), and the sites run active anti-bot defences. Building a production pipeline by scraping SeLoger, LeBonCoin, or Bien'ici directly is a demonstrated legal liability, not a shortcut. Off-the-shelf scrapers exist, but using them at scale puts you in the position Jinka and Entreparticuliers were penalised for.

## 4. The precision caveat

French portals intentionally mask the exact address. They publish a neighbourhood or commune, or a blurred radius, to prevent disintermediation and scraping. Consequences:

- You generally get a commune-level or approximate coordinate, not the building. Aggregator APIs pass through that same approximate point.
- IRIS is sub-commune, so an approximate coordinate can land in the wrong IRIS. Per-listing points are indicative. Aggregating listings to the IRIS or commune level is sound, but individual pins should be marked approximate.
- "Find the exact address" services exist (cross-referencing photos, DPE, and surface against public registers), but they are unreliable, manual, and legally fraught at scale, so they are not suitable for an automated platform.

## 5. How it plugs into this platform

The hard parts already exist; only the source is new.

1. A new collector, `rei/ingestion/listings.py`, normalises each advert to `{listing_id, type (sale or rent), price, surface, prix_m2, lat, lon, posted_at, source, url}`.
2. Geocode any text address through the existing BAN collector (`api-adresse.data.gouv.fr`); otherwise use the source's coordinate.
3. Assign the IRIS by point-in-polygon, reusing the `gpd.sjoin(points, iris, predicate="within")` pattern already in `iris_engine`.
4. Persist `data/tables/listings.parquet`, export `listings.geojson`, and add a map layer with one point per listing.
5. Later, derive per-IRIS signals: asking-versus-DVF spread, median days-on-market, active-listings count, and share with a price cut. These strengthen the liquidity, rental-demand, and value-trap scores (a trap often shows many stale listings with price cuts).

## 6. Recommendation and what was built

The clean, low-effort route is a licensed aggregator (MoteurImmo or Fluximmo), behind a thin collector, treating coordinates as approximate and aggregating to IRIS. Do not scrape the portals directly for production; the case law (up to €200,000) makes it a liability.

This project chose no paid API, so it ships a self-operated Bien'ici reader instead (`BieniciProvider`): opt-in, rate-limited, with lazy pagination, reusing the documented `realEstateAds.json` map endpoint. The legal risk of scraping a portal still applies and is the operator's to accept. Before scaling, pull a few hundred listings, run geocode to IRIS, and measure how many resolve to a confident IRIS versus commune-only; that ratio decides how useful per-point plotting is here.

## Sources

- Apify scrapers: [SeLoger](https://apify.com/lexis-solutions/seloger-scraper/api), [multi-source FR real estate](https://apify.com/ccdeveloppement/real-estate-scraper), [Bien'ici](https://apify.com/qpayre/bien-ici-scraper)
- [api-sites-immo (GitHub, unofficial portal APIs)](https://github.com/0x6e69636f/api-sites-immo), [evolving list of FR real-estate APIs (gist)](https://gist.github.com/alexauvray/098e615e6f01e402a9e222125ef87ae1), [lobstrio/bieniciscraper (MIT, the API reference reused)](https://github.com/lobstrio/bieniciscraper)
- [MoteurImmo API offer](https://moteurimmo.fr/offre-api), [Fluximmo listings API](https://www.fluximmo.com/api-annonces-immobilieres), [Stream Estate real-time listings guide](https://stream.estate/blog/real-estate-data-api-europe-complete-guide-2025)
- [Yanport API docs](https://www.yanport.com/solutions/api/documentation), [PriceHubble real-estate API](https://www.pricehubble.com/use-cases/real-estate-api), [Casafari property data API](https://www.casafari.com/insights/advantages-casafaris-property-data-api/), [Castorus price-history tracker](https://www.castorus.com/)
- Legal: [CMS on LeBonCoin web scraping and the sui generis right](https://cms.law/fr/fra/news-information/arret-leboncoin-web-scraping-droit-sui-generis-sur-les-bases-de-donnees), [Usine Digitale on LeBonCoin v. Jinka](https://www.usine-digitale.fr/les-experts-du-numerique/lefficacite-judiciaire-de-la-protection-des-bases-de-donnees-laffaire-le-bon-coin-c-jinka.XOBROKVL4BCODAEQGEW4IKXSUQ.html), [ImmoMatin on SeLoger v. Jinka](https://www.immomatin.com/portails/sites-professionnels/seloger-obtient-la-condamnation-de-jinka-pour-scraping-illicite-d-annonces-immobilieres.html), [Kohen Avocats on the 2022 to 2026 jurisprudence](https://kohenavocats.fr/2026/05/30/protection-sui-generis-bases-donnees-scraping-jurisprudence-2022-2026/)
- Address masking: [Maitris'immo](https://maitrisimmo.fr/adresse-masquee-leboncoin-seloger/), [LeBonCoin help on locating an advert](https://assistance.leboncoin.info/hc/fr/articles/360000169469-O%C3%B9-dois-je-localiser-mon-annonce)
