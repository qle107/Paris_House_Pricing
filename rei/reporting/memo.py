"""Auto-generated one-page investment memo per IRIS (blueprint Phase 7.2).

Pure templating over ``rei.reporting.decompose`` plus the optional ML price forecast.
No I/O: hand it a scored row (and optionally that commune's ml_forecast row) and it
returns committee-ready markdown. The thesis, drivers, risks and recommendation are
derived from the same numbers the score is built on, so the memo can never disagree
with the ranking.
"""
from __future__ import annotations

import math

from rei.reporting.decompose import decompose


def _val(row, col):
    v = row.get(col)
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def _verdict(score, trap) -> str:
    if score is None:
        return "Insufficient data to recommend"
    tier = ("Shortlist for acquisition" if score >= 70 else
            "Investigate further" if score >= 55 else
            "Watch" if score >= 40 else "Pass")
    return tier + (" - elevated value-trap risk" if trap >= 60 else "")


def _factors(items) -> str:
    return ", ".join(f"{k} ({v:+.1f} pts)" for k, v in items) or "none material"


def investment_memo(row, forecast: dict | None = None) -> str:
    """Render a markdown investment memo for one scored IRIS row."""
    d = decompose(row)
    name, code = row.get("iris_name") or "IRIS", row.get("iris_code") or "?"
    score, trap = d["institutional_score"], d["value_trap_score"]
    parts = [f"# Investment memo - {name} ({code})", ""]

    head = (f"**Score {score:.0f}/100**" if score is not None else "**Score n/a**")
    if d["data_coverage"] is not None:
        head += f"  ·  data-backed {d['data_coverage'] * 100:.0f}%"
    head += f"  ·  value-trap {trap:.0f}/100"
    parts += [head, ""]

    top = d["positive_contributors"][0][0] if d["positive_contributors"] else "no standout strength"
    drag = d["negative_contributors"][0][0] if d["negative_contributors"] else "no material weakness"
    parts += [f"**Thesis.** Carried by {top}, held back by {drag}. "
              f"Screen verdict: {_verdict(score, trap)}.", ""]

    parts += [f"**Drivers.** {_factors(d['positive_contributors'])}.",
              f"**Risks & penalties.** {_factors(d['negative_contributors'])}. "
              f"Gates: {'; '.join(d['gates_fired']) or 'none'}. "
              f"Trap haircut -{d['trap_haircut_pct']:.0f}%, climate haircut -{d['climate_haircut_pct']:.0f}%.", ""]

    if forecast:
        cagr, lo, hi = forecast.get("expected_price_cagr"), forecast.get("cagr_p10"), forecast.get("cagr_p90")
        if cagr is not None:
            band = f" (p10-p90 {lo:+.1%} to {hi:+.1%})" if lo is not None and hi is not None else ""
            hz = f" over {forecast['horizon']}y" if forecast.get("horizon") else ""
            parts += [f"**Forward outlook.** Expected price CAGR {cagr:+.1%}{hz}{band}.", ""]

    obs, exp, disc = _val(row, "observed_prix_m2"), _val(row, "expected_prix_m2"), _val(row, "discount_pct")
    if obs is not None and exp is not None:
        ds = f" ({disc:+.0f}% vs fair)" if disc is not None else ""
        parts += [f"**Value.** Trades at EUR {obs:,.0f}/m2 vs expected EUR {exp:,.0f}/m2{ds}.", ""]

    parts += [f"**Recommendation.** {_verdict(score, trap)}."]
    return "\n".join(parts)
