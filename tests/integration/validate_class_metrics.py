"""Independent recomputation of the class metrics from the raw Silver parquet.

Does not share any code with the dbt SQL: it follows the definitions in
docs/analytics/financial_metrics.md and compares against int_class_metrics
for every class (volatility, excess return, downside deviation, Sortino, CAGR,
1-year return, maximum drawdown, number of weeks and returns).

Usage (from the repository root, after `dbt build` against the real data):
    python tests/integration/validate_class_metrics.py . data/gold/cnmv.duckdb

It is not part of the pytest suite: it needs the full Silver data and the dbt output.
"""

import sys

import duckdb
import numpy as np
import pandas as pd

ROOT, DB = sys.argv[1], sys.argv[2]
con = duckdb.connect()

AS_OF = pd.Timestamp(
    duckdb.connect(DB, read_only=True)
    .sql("select as_of_date from meta_run")
    .fetchone()[0]
)
WINDOW_START = AS_OF - pd.DateOffset(months=36) + pd.Timedelta(days=1)

nav = con.sql(
    f"""
    select Tipo||'|'||NumeroRegistro||'|'||NumeroCompartimento||'|'||NumeroClase as class_key,
           value_date, cast(VL as double) as nav
    from read_parquet('{ROOT}/data/silver/fund_nav_daily/**/*.parquet', hive_partitioning=true)
    where value_date between date '{WINDOW_START.date()}' and date '{AS_OF.date()}'
      and not (VL < -1 or Patrimonio < -1 or Participes < -1)
    """
).df()
nav["value_date"] = pd.to_datetime(nav["value_date"]).astype("datetime64[ns]")
nav = nav[nav["value_date"].dt.dayofweek < 5].copy()  # weekdays only

# --- weekly NAV: last weekday with nav > 0 in each ISO week; week keyed by its Sunday
nav["week_end"] = nav["value_date"] + pd.to_timedelta(
    6 - nav["value_date"].dt.dayofweek, unit="D"
)
valid = nav[nav["nav"] > 0].sort_values(["class_key", "week_end", "value_date"])
weekly_nav = valid.groupby(["class_key", "week_end"])["nav"].last().rename("nav")
nav["week_end"] = nav["week_end"].astype("datetime64[ns]")
valid = nav[nav["nav"] > 0].sort_values(["class_key", "week_end", "value_date"])
weeks = (
    nav.groupby(["class_key", "week_end"])
    .size()
    .rename("n_days")
    .to_frame()
    .join(weekly_nav)
    .reset_index()
)
weeks = weeks.sort_values(["class_key", "week_end"])
g = weeks.groupby("class_key")
weeks["prev_week"] = g["week_end"].shift(1)
weeks["prev_nav"] = g["nav"].shift(1)
consecutive = (weeks["week_end"] - weeks["prev_week"]) == pd.Timedelta(days=7)
weeks["ret_w"] = np.where(
    consecutive & weeks["nav"].notna() & weeks["prev_nav"].notna(),
    weeks["nav"] / weeks["prev_nav"] - 1,
    np.nan,
)

# --- weekly MAR from the compounded EUR short-term rate index
estr = con.sql(
    f"""select value_date, cast(obs_value as double) as idx
        from read_parquet('{ROOT}/data/silver/estr_daily/**/*.parquet')
        where series = 'EST.B.EU000A2QQF08.CI' order by value_date"""
).df()
estr["value_date"] = pd.to_datetime(estr["value_date"]).astype("datetime64[ns]")
# End at the Sunday closing the cut-off week, which dbt also includes when the
# cut-off date is not itself a Sunday.
sundays = pd.date_range(
    AS_OF - pd.Timedelta(days=4 * 365), AS_OF + pd.Timedelta(days=6), freq="W-SUN"
)
sundays = sundays[
    (sundays >= WINDOW_START) & (sundays - pd.Timedelta(days=6) <= AS_OF)
].astype("datetime64[ns]")
wk = pd.merge_asof(
    pd.DataFrame({"week_end": sundays}), estr, left_on="week_end", right_on="value_date"
)
wk["mar_w"] = wk["idx"] / wk["idx"].shift(1) - 1
weeks = weeks.merge(wk[["week_end", "mar_w"]], on="week_end", how="left")
weeks["excess"] = weeks["ret_w"] - weeks["mar_w"]


def metrics(d):
    r = d["ret_w"].dropna()
    e = d["excess"].dropna()
    has = d.dropna(subset=["nav"])
    out = {"n_returns": len(r), "n_weeks": len(has)}
    out["vol"] = r.std(ddof=1) * np.sqrt(52) if len(r) > 1 else np.nan
    out["mean_excess"] = e.mean() * 52 if len(e) else np.nan
    out["downside_dev"] = (
        np.sqrt((np.minimum(e, 0) ** 2).mean()) * np.sqrt(52) if len(e) else np.nan
    )
    out["sortino"] = (
        out["mean_excess"] / out["downside_dev"]
        if out["downside_dev"] not in (0, np.nan)
        and out["downside_dev"] == out["downside_dev"]
        and out["downside_dev"] != 0
        else np.nan
    )
    if len(has):
        first, last = has.iloc[0], has.iloc[-1]
        days = (last["week_end"] - first["week_end"]).days
        out["cagr_3y"] = (
            (last["nav"] / first["nav"]) ** (365.0 / days) - 1 if days > 0 else np.nan
        )
        back = has[has["week_end"] == last["week_end"] - pd.Timedelta(weeks=52)]
        out["ret_1y"] = last["nav"] / back.iloc[0]["nav"] - 1 if len(back) else np.nan
    return pd.Series(out)


recs = {}
for key, dd in weeks.groupby("class_key"):
    recs[key] = metrics(dd)
mine = pd.DataFrame.from_dict(recs, orient="index")
mine.index.name = "class_key"
print("recalculo:", mine.shape, "| columnas:", list(mine.columns))

# --- max drawdown on the daily weekday series
d = valid.sort_values(["class_key", "value_date"])
d["peak"] = d.groupby("class_key")["nav"].cummax()
d["dd"] = 1 - d["nav"] / d["peak"]
mine["max_drawdown"] = d.groupby("class_key")["dd"].max()

ref = (
    duckdb.connect(DB, read_only=True)
    .sql(
        "select class_key, vol, mean_excess, downside_dev, sortino, cagr_3y, ret_1y, max_drawdown, n_returns, n_weeks from int_class_metrics"
    )
    .df()
    .set_index("class_key")
)

common = ref.index.intersection(mine.index)
print(
    f"clases en dbt: {len(ref)} | recalculadas: {len(mine)} | comunes: {len(common)} | solo dbt: {len(ref.index.difference(mine.index))} | solo recalculo: {len(mine.index.difference(ref.index))}"
)
rows = []
for col in [
    "n_returns",
    "n_weeks",
    "vol",
    "mean_excess",
    "downside_dev",
    "sortino",
    "cagr_3y",
    "ret_1y",
    "max_drawdown",
]:
    a, b = ref.loc[common, col].astype(float), mine.loc[common, col].astype(float)
    both = a.notna() & b.notna()
    null_mismatch = int((a.isna() != b.isna()).sum())
    tol = 1e-9 if col not in ("n_returns", "n_weeks") else 0
    err = (
        (a[both] - b[both]).abs() / np.maximum(b[both].abs(), 1e-12)
        if col not in ("n_returns", "n_weeks")
        else (a[both] - b[both]).abs()
    )
    rows.append(
        (
            col,
            int(both.sum()),
            null_mismatch,
            int((err > max(tol, 1e-9)).sum()),
            float(err.max()) if len(err) else 0.0,
        )
    )
print(
    f"{'metrica':14} {'comparadas':>10} {'nulos distintos':>16} {'fuera de tol.':>14} {'error max':>12}"
)
for r in rows:
    print(f"{r[0]:14} {r[1]:>10} {r[2]:>16} {r[3]:>14} {r[4]:>12.2e}")
