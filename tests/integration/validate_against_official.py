"""Cross-checks of dbt outputs against OFFICIAL CNMV figures.

1. Official quarterly return (FONDTRIM) vs the return computed from the daily NAV.
2. Official quarterly volatility vs the daily-return deviation, to find its annualisation.
3. Peer percentile recomputed from the Sortino ranking.
4. Management fee realised (FONDPATRIMDISVAR) vs the rate reported by FONDTRIM.

Usage (from the repository root, after `dbt build` against the real data):
    python tests/integration/validate_against_official.py . data/gold/cnmv.duckdb
"""

import os
import sys

import duckdb
import numpy as np
import pandas as pd

ROOT, DB = os.path.abspath(sys.argv[1]), sys.argv[2]
con = duckdb.connect(DB, read_only=True)
# Staging views read Silver with paths relative to dbt/, so resolve them from there.
con.execute(f"set file_search_path = '{ROOT}/dbt'")
raw = f"read_parquet('{ROOT}/data/silver/fund_nav_daily/**/*.parquet', hive_partitioning=true)"

# ------------------------------------------------------------------ 1. quarterly return and volatility
off = con.sql(
    """select c.class_key, q.date_key, q.return_rate, q.volatility_rate
       from fact_fund_quarterly_metrics q join dim_class c using (class_id)
       where q.return_rate is not null"""
).df()
off["qend"] = pd.to_datetime(off["date_key"].astype(str), format="%Y%m%d")

nav = con.sql(
    f"""select Tipo||'|'||NumeroRegistro||'|'||NumeroCompartimento||'|'||NumeroClase as class_key,
               value_date, cast(VL as double) as nav
        from {raw} where VL > 0 and Patrimonio >= 0"""
).df()
nav["value_date"] = pd.to_datetime(nav["value_date"]).astype("datetime64[ns]")
nav = nav[nav["value_date"].dt.dayofweek < 5].sort_values(["class_key", "value_date"])

rng = np.random.default_rng(7)
classes = rng.choice(np.sort(off["class_key"].unique()), size=1500, replace=False)
nav = nav[nav["class_key"].isin(classes)]
off = off[off["class_key"].isin(classes)].copy()
off["qprev"] = off["qend"] - pd.offsets.QuarterEnd(1)
# need NAV data before the quarter starts; derived from the data, not a fixed date
off = off[off["qprev"] >= nav["value_date"].min()]


navr = nav.rename(columns={"value_date": "d"}).sort_values("d")
off = off.reset_index(drop=True)
off["oid"] = range(len(off))


def asof(col):
    left = (
        off[["oid", "class_key", col]]
        .rename(columns={col: "d"})
        .astype({"d": "datetime64[ns]"})
        .sort_values("d")
    )
    m = pd.merge_asof(left, navr, on="d", by="class_key")
    return m.set_index("oid")["nav"].reindex(off["oid"]).to_numpy()


off["nav_end"] = asof("qend")
off["nav_start"] = asof("qprev")
off["ret_calc"] = off["nav_end"] / off["nav_start"] - 1
d = off.dropna(subset=["ret_calc"]).copy()
d["diff_pp"] = (d["return_rate"] - d["ret_calc"]).abs() * 100
print(
    f"[1] rentabilidad trimestral oficial vs calculada desde el NAV: {len(d)} observaciones, {d.class_key.nunique()} clases"
)
print(
    f"    diferencia absoluta (puntos porcentuales): mediana {d.diff_pp.median():.3f} | p90 {d.diff_pp.quantile(0.9):.3f} | p99 {d.diff_pp.quantile(0.99):.2f}"
)
print(
    f"    dentro de 0,05 pp: {(d.diff_pp <= 0.05).mean():.1%} | dentro de 0,5 pp: {(d.diff_pp <= 0.5).mean():.1%} | mas de 2 pp: {(d.diff_pp > 2).mean():.2%}"
)

# volatility: daily returns inside the quarter
nav["ret"] = nav.groupby("class_key")["nav"].pct_change()
res = []
grp = {
    k: (g["value_date"].to_numpy(), g["ret"].to_numpy())
    for k, g in nav.groupby("class_key")
}
for r in d.itertuples():
    dates, rets = grp[r.class_key]
    lo = np.searchsorted(dates, np.datetime64(r.qprev), side="right")
    hi = np.searchsorted(dates, np.datetime64(r.qend), side="right")
    seg = rets[lo:hi]
    seg = seg[~np.isnan(seg)]
    if len(seg) >= 40 and pd.notna(r.volatility_rate):
        res.append((r.volatility_rate, seg.std(ddof=1), len(seg)))
v = pd.DataFrame(res, columns=["official", "daily_std", "n"])
v = v[v.daily_std > 0]
for name, k in (
    ("sqrt(252)", np.sqrt(252)),
    ("sqrt(260)", np.sqrt(260)),
    ("sqrt(365)", np.sqrt(365)),
):
    ratio = v.official / (v.daily_std * k)
    print(
        f"[2] volatilidad oficial / (desv. diaria x {name}): mediana {ratio.median():.3f} | p10 {ratio.quantile(0.1):.3f} | p90 {ratio.quantile(0.9):.3f}  (n={len(v)})"
    )
# ------------------------------------------------------------------ 3. peer ranking recomputed
pr = con.sql(
    "select compartment_key, vocation, sortino, pct_exact, percentile_in_vocation, quartile_in_vocation, star_rating, n_peers from int_fund_peer_ranking"
).df()
pr["rank_c"] = pr.groupby("vocation")["sortino"].rank(method="min", ascending=False)
pr["n"] = pr.groupby("vocation")["sortino"].transform("count")
pr["pct_exact_chk"] = 100 * (pr["rank_c"] - 1) / (pr["n"] - 1).replace(0, np.nan)
ok = pr["pct_exact"].notna() | pr["pct_exact_chk"].notna()
print(
    f"[3] pct_exact recalculado: {int(ok.sum())} compartimentos, error maximo {(pr.pct_exact - pr.pct_exact_chk).abs().max():.2e}; n_peers coincide: {(pr.n == pr.n_peers).all()}"
)

# ------------------------------------------------------------------ 4. management fee: FONDPATRIMDISVAR vs contractual FONDTRIM rate
fee = con.sql(
    """with c as (
         select compartment_key, sum(aum) as aum, sum(aum*management_fee_rate)/nullif(sum(aum),0) as contractual
         from stg_fund_quarterly where period='202512' and management_fee_rate is not null and aum>0 group by 1),
       f as (
         select co.compartment_key, p.management_fee_yield_annualized_rate as realised, p.average_patrimony
         from fact_fund_period_financials p join dim_compartment co using (compartment_id) where p.date_key=20251231 and p.management_fee_yield_annualized_rate>0)
       select c.contractual, f.realised, f.average_patrimony from c join f using (compartment_key)
       where f.average_patrimony > 5e6"""
).df()
fee["ratio"] = fee.realised / fee.contractual
print(
    f"[4] comision de gestion REALIZADA (FONDPATRIMDISVAR, anualizada) / CONTRACTUAL (FONDTRIM): {len(fee)} compartimentos (>5 M EUR)"
)
print(
    f"    mediana {fee.ratio.median():.3f} | p10 {fee.ratio.quantile(0.1):.3f} | p90 {fee.ratio.quantile(0.9):.3f} | correlacion {fee.realised.corr(fee.contractual):.3f}"
)
