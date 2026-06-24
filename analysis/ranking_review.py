"""
Institutional Ranking Review — standalone analysis prototype.

READ-ONLY against production data. Does NOT modify any scoring code.
Recomputes an alternative, value-trap-aware ranking from the existing
iris_score outputs + the (currently unused) ml_forecast, to produce the
before/after evidence for the methodology review.

Run:  python3 ranking_review.py
Outputs: prints diagnostics; writes before_after_rankings.csv + value_trap_flags.csv
"""
from __future__ import annotations
import numpy as np, pandas as pd
from pathlib import Path

DATA = Path("/sessions/compassionate-gifted-ritchie/mnt/real-estate-intelligence/data/tables")
OUT  = Path("/sessions/compassionate-gifted-ritchie/mnt/outputs")

def pct(s, direction=1):
    """Percentile 0-100. direction=-1 inverts. NaN -> NaN (NOT 50)."""
    s = pd.to_numeric(s, errors="coerce")
    r = s.rank(pct=True, ascending=(direction > 0))
    return (r * 100).round(1)   # leaves NaN as NaN, unlike production

def zone_of(cc):
    d = str(cc)[:2]
    return ("Paris" if d == "75" else
            "PetiteCouronne" if d in ("92","93","94") else
            "GrandeCouronne" if d in ("77","78","91","95") else "Other")

# ----------------------------------------------------------------------------- load
df = pd.read_parquet(DATA / "iris_score.parquet")
df["cc"] = df["code_commune"].astype(str)
df["zone"] = df["cc"].map(zone_of)
N = len(df)

# FIX 1: loyer_m2 is stored with European comma decimals -> parses to NaN in prod.
df["rent_eur_m2"] = pd.to_numeric(df["loyer_m2"].astype(str).str.replace(",", "."), errors="coerce")

# FIX 2: wire in the (currently unused) ml_forecast forward price CAGR (commune level).
mlf = pd.read_parquet(DATA / "ml_forecast.parquet")[["code_commune","expected_price_cagr"]]
mlf["cc"] = mlf["code_commune"].astype(str)
df = df.merge(mlf[["cc","expected_price_cagr"]], on="cc", how="left")

# ----------------------------------------------------------------------------- clean sub-scores (0-100)
# RENTAL DEMAND = real rent level + transaction liquidity (prod used liquidity ONLY).
df["s_rent"]   = pct(df["rent_eur_m2"], 1)
df["s_liq"]    = pct(df["n_sales"], 1)
df["rental"]   = (0.6*df["s_rent"] + 0.4*df["s_liq"])
df.loc[df["s_rent"].isna(), "rental"] = df["s_liq"]          # fall back if rent missing

# APPRECIATION (forward) = historical momentum + ML forecast (prod used momentum + mostly-missing supply).
df["s_mom"]    = pct(df["price_cagr"], 1)
df["s_fwd"]    = pct(df["expected_price_cagr"], 1)
df["appreciation"] = np.where(df["s_fwd"].notna() & df["s_mom"].notna(),
                              0.5*df["s_fwd"] + 0.5*df["s_mom"],
                              df[["s_fwd","s_mom"]].mean(axis=1))
df["appreciation"] = df["appreciation"].fillna(50.0)

# Re-use prod institutional sub-scores where they are already reasonable:
df["value_raw"]   = df["inst_value"]          # hedonic discount (BIASED - location-blind)
df["development"] = df["inst_development"].fillna(50.0)
df["risk"]        = df["inst_risk"].fillna(50.0)
df["toxicity"]    = df["inst_toxicity"].fillna(50.0)
df["liquidity"]   = df["s_liq"].fillna(50.0)

# ----------------------------------------------------------------------------- STEP 3: VALUE_TRAP_SCORE (0=clean, 100=severe trap)
# A location is a trap when it is cheap (high value_raw) but its FUNDAMENTALS are weak.
# Inputs available in-data (population/employment TRENDS are NOT - single-year census, flagged).
trap_parts = pd.DataFrame({
    "weak_appreciation": 100 - df["appreciation"],   # no growth
    "weak_rental":       100 - df["rental"],          # weak demand (real rent + liquidity)
    "high_toxicity":     df["toxicity"],              # falling price + thin trading
    "illiquidity":       100 - df["liquidity"],       # hard to exit
    "weak_risk":         100 - df["risk"],            # volatile / thin
})
TRAP_W = {"weak_appreciation":0.30,"weak_rental":0.25,"high_toxicity":0.20,
          "illiquidity":0.15,"weak_risk":0.10}
df["value_trap_score"] = sum(trap_parts[k]*w for k,w in TRAP_W.items()).round(1)

# Trap-adjusted value: cheapness only "counts" if fundamentals aren't weak.
df["value_adj"] = (df["value_raw"] * (1 - 0.85*df["value_trap_score"]/100)).round(1)

# ----------------------------------------------------------------------------- STEP 5: QUALITY GATES
def apply_gates(score, d):
    s = score.copy().astype(float)
    # hard caps: a single strong factor cannot promote a structurally weak location
    s = np.where(d["appreciation"] < 40, np.minimum(s, 55), s)
    s = np.where(d["rental"]       < 40, np.minimum(s, 55), s)
    # multiplicative penalties
    s = np.where(d["toxicity"] > 70, s*0.85, s)
    s = np.where(d["risk"]     < 30, s*0.85, s)
    s = np.where(d["liquidity"]< 15, s*0.85, s)      # extremely thin market
    # explicit value-trap haircut
    s = s * (1 - 0.40*d["value_trap_score"]/100)
    return pd.Series(s, index=d.index).round(1)

# ----------------------------------------------------------------------------- STEP 4: NEW INSTITUTIONAL WEIGHTS
# prod: appreciation .30 rental .25 value .20 development .15 risk .10  (value=raw cheapness, no liquidity, no gates)
NEW_W = {"appreciation":0.28,"rental":0.22,"risk":0.15,"value_adj":0.15,"development":0.10,"liquidity":0.10}
inst_base = sum(df[k]*w for k,w in NEW_W.items())
df["inst_new"] = apply_gates(inst_base, df)

# ----------------------------------------------------------------------------- STEP 8: REBUILT ALPHA
# Alpha := probability of strong RISK-ADJUSTED appreciation over 5-15y.
# drivers: forward appreciation, rental demand, development, (trap-adjusted) value, liquidity
# penalties: value-trap haircut + gates. (prod alpha silently dropped a 20% "transit" term = None.)
ALPHA_W = {"appreciation":0.40,"rental":0.20,"development":0.15,"value_adj":0.15,"liquidity":0.10}
alpha_base = sum(df[k]*w for k,w in ALPHA_W.items())
df["alpha_new"] = apply_gates(alpha_base, df)

# ----------------------------------------------------------------------------- STEP 6: INVESTOR PROFILES
PROFILES = {
 "Core":          {"rental":0.30,"risk":0.25,"liquidity":0.20,"appreciation":0.15,"value_adj":0.10},
 "Growth":        {"appreciation":0.45,"development":0.20,"rental":0.15,"value_adj":0.10,"liquidity":0.10},
 "Value":         {"value_adj":0.45,"appreciation":0.20,"rental":0.15,"risk":0.10,"liquidity":0.10},
 "Developer":     {"development":0.45,"appreciation":0.20,"value_adj":0.15,"liquidity":0.10,"rental":0.10},
 "Institutional": NEW_W,
}
for name, w in PROFILES.items():
    df[f"prof_{name}"] = apply_gates(sum(df[k]*wk for k,wk in w.items()), df)

# =============================================================================== REPORTING
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
line = "="*100

def hdr(t): print("\n"+line+"\n"+t+"\n"+line)

hdr("STEP 1 — DISTRIBUTIONS BY ZONE  (current production scores)")
zb = df.groupby("zone")
cur = ["score_total","institutional_score","alpha_score","inst_value","inst_appreciation","inst_rental","inst_toxicity"]
print("MEAN:\n", zb[cur].mean().round(1).T)
print("\nMEDIAN observed EUR/m2 | discount% | value:\n",
      zb[["observed_prix_m2","discount_pct","inst_value"]].median().round(1).T)

hdr("STEP 3 — VALUE-TRAP SCORE distribution by zone")
print(zb["value_trap_score"].describe()[["mean","50%","std","min","max"]].round(1))
print("\nHigh-trap IRIS (trap>=60) that currently rank TOP-20%% on production alpha:")
hi = df[(df.value_trap_score>=60) & (df.alpha_score>=df.alpha_score.quantile(0.80))]
print(f"  count = {len(hi)}  (these are the cheap-but-weak locations the model over-promotes)")

hdr("STEP 7 — BENCHMARK PROVEN CORRIDORS: before vs after (commune mean alpha percentile)")
bench = {"93070":"Saint-Ouen","93055":"Pantin","93048":"Montreuil","92024":"Clichy",
         "92040":"Issy-les-Mlx","92012":"Boulogne-B"}
df["alpha_old_pct"] = df.alpha_score.rank(pct=True)*100
df["alpha_new_pct"] = df.alpha_new.rank(pct=True)*100
rows=[]
for cc,nm in bench.items():
    s=df[df.cc==cc]
    if len(s): rows.append((nm, round(s.observed_prix_m2.median()),
                            round(s.alpha_old_pct.mean()), round(s.alpha_new_pct.mean()),
                            round(s.value_trap_score.mean())))
print(pd.DataFrame(rows, columns=["commune","med_eur_m2","alpha_pct_OLD","alpha_pct_NEW","trap"]).to_string(index=False))

hdr("STEP 9 — BEFORE: top 15 by PRODUCTION alpha")
cshow=["iris_name","zone","observed_prix_m2","inst_value","inst_appreciation","inst_rental","value_trap_score","alpha_score"]
print(df.nlargest(15,"alpha_score")[cshow].round(0).to_string(index=False))

hdr("STEP 9 — AFTER: top 15 by NEW Institutional Composite")
nshow=["iris_name","zone","observed_prix_m2","appreciation","rental","value_adj","value_trap_score","inst_new","alpha_new"]
print(df.nlargest(15,"inst_new")[nshow].round(0).to_string(index=False))

hdr("STEP 9 — BIGGEST FALLERS (value traps demoted): old alpha pct -> new")
df["drop"]= df.alpha_old_pct - df.alpha_new_pct
fall = df.nlargest(12,"drop")[["iris_name","zone","observed_prix_m2","value_trap_score","alpha_old_pct","alpha_new_pct"]]
print(fall.round(0).to_string(index=False))

hdr("STEP 9 — BIGGEST RISERS (sound markets promoted): old alpha pct -> new")
df["rise"]= df.alpha_new_pct - df.alpha_old_pct
ris = df.nlargest(12,"rise")[["iris_name","zone","observed_prix_m2","value_trap_score","alpha_old_pct","alpha_new_pct"]]
print(ris.round(0).to_string(index=False))

hdr("ZONE MIX of Top-200: before vs after")
def mix(col):
    t=df.nlargest(200,col); return t.zone.value_counts(normalize=True).mul(100).round(0).to_dict()
print("OLD alpha   top-200 zone mix:", mix("alpha_score"))
print("NEW inst    top-200 zone mix:", mix("inst_new"))
print("NEW alpha   top-200 zone mix:", mix("alpha_new"))

# ----------------------------------------------------------------------------- write artifacts
keep=["iris_code","iris_name","cc","zone","observed_prix_m2","value_trap_score",
      "alpha_score","alpha_new","institutional_score","inst_new",
      "prof_Core","prof_Growth","prof_Value","prof_Developer","prof_Institutional"]
df[keep].sort_values("inst_new",ascending=False).to_csv(OUT/"before_after_rankings.csv",index=False)
df[df.value_trap_score>=60][["iris_code","iris_name","zone","observed_prix_m2","value_trap_score","alpha_score"]]\
  .sort_values("alpha_score",ascending=False).to_csv(OUT/"value_trap_flags.csv",index=False)
print("\nWROTE before_after_rankings.csv and value_trap_flags.csv")
print(f"value-trap flagged (>=60): {(df.value_trap_score>=60).sum()} of {N}")
