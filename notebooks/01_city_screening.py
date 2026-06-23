# City screening: ingest → score → rank (requires DB)
WATCHLIST = ["93066", "93070", "94043", "92050", "92040"]

from rei.ingestion.registry import get_collector

get_collector("insee_population").run()
get_collector("insee_income").run()
get_collector("sitadel_permits").run(communes=WATCHLIST)
get_collector("dvf_transactions").run(communes=WATCHLIST)
get_collector("cadastre_parcels").run(communes=WATCHLIST)
get_collector("gpu_zoning").run(communes=WATCHLIST)
get_collector("transit_gtfs").run(area_query="Ile-de-France")

# %% Refresh features + score
from rei.etl.load import refresh_matviews
from rei.scoring.engine import score
from rei.zoning.detectors import score_communes

refresh_matviews()
density = score_communes(WATCHLIST)
ranking = score("value_add_opportunistic", min_population=2000, density_scores=density)
print(ranking.head(20).to_string(index=False))

# %% Density-change detection + transport impact for the top commune
from rei.transport.impact import project_parcel_impact, rank_projects
from rei.zoning.plu_diff import diff_latest_two

top = ranking.iloc[0]["code_commune"]
print("Zoning reclassifications:\n", diff_latest_two(top))
print("Transport project ranking:\n", rank_projects().head(10).to_string(index=False))
print("Parcel-level uplift:\n", project_parcel_impact(top, today_year=2026).head().to_string(index=False))
