"""
02_eda.py
Compute EDA statistics from the full dataset (2013-01-01 to 2017-12-31).
EDA is descriptive — the full date range is intentional (no leakage risk).

Output: public/data/eda.json  (matches EdaData TypeScript type)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED  = Path(__file__).parent / "data" / "processed"
PUBLIC_DIR = Path(__file__).parent.parent / "public" / "data"

STORES = list(range(1, 6))


def _round2(x: float) -> float:
    return round(float(x), 2)


def _rolling_12m(monthly: list[dict]) -> list[dict]:
    """Add rolling_12m starting from index 11 (i.e. 12th month)."""
    out = []
    for i, row in enumerate(monthly):
        if i >= 11:
            window_sales = [monthly[j]["sales"] for j in range(i - 11, i + 1)]
            row = dict(row, rolling_12m=_round2(sum(window_sales) / 12))
        out.append(row)
    return out


def _store_eda(df_store: pd.DataFrame, store: int) -> dict:
    """Build EdaData for a single store."""
    df = df_store.copy()
    df["month"] = df["date"].dt.to_period("M").astype(str)

    # --- monthly_total (sum across all items in this store) ---
    monthly = (
        df.groupby("month", sort=True)["sales"]
        .sum()
        .reset_index()
        .rename(columns={"sales": "sales"})
    )
    monthly_list = [
        {"month": row["month"], "sales": int(row["sales"])}
        for _, row in monthly.iterrows()
    ]
    monthly_list = _rolling_12m(monthly_list)

    # --- weekday_avg (avg per item per day, DOW 0=Mon … 6=Sun) ---
    # DOW: pandas weekday() gives 0=Mon…6=Sun — matches TypeScript (0=Mon)
    df["dow"] = df["date"].dt.weekday  # 0=Mon, 6=Sun
    n_items = df["item"].nunique()
    weekday_rows = []
    for dow in range(7):
        mask = df["dow"] == dow
        if mask.any():
            avg = _round2(df.loc[mask, "sales"].mean() / n_items)  # already daily mean per item
            # Actually: mean() already averages over all days with that DOW,
            # and each day has n_items rows summed, so we don't double-divide.
            # Correct: total_sales_on_dow / n_days_with_that_dow / n_items
            n_days = df.loc[mask, "date"].nunique()
            avg = _round2(df.loc[mask, "sales"].sum() / n_days / n_items)
        else:
            avg = 0.0
        weekday_rows.append({"store": store, "dow": dow, "avg_sales": avg})

    # --- weekend_vs_weekday ---
    weekday_mask = df["dow"] < 5
    weekend_mask = df["dow"] >= 5

    def _period_avg(mask: pd.Series) -> float:
        sub = df[mask]
        n_days = sub["date"].nunique()
        return _round2(sub["sales"].sum() / n_days / n_items) if n_days else 0.0

    wvw = [{
        "store": store,
        "weekday_avg": _period_avg(weekday_mask),
        "weekend_avg": _period_avg(weekend_mask),
    }]

    # --- month_year_heatmap ---
    df["year"]  = df["date"].dt.year
    df["month_num"] = df["date"].dt.month
    heatmap = (
        df.groupby(["year", "month_num"])
        .apply(lambda g: _round2(g["sales"].sum() / g["date"].nunique() / n_items), include_groups=False)
        .reset_index()
        .rename(columns={0: "avg_sales"})
    )
    heatmap_list = [
        {"year": int(r["year"]), "month": int(r["month_num"]), "avg_sales": r["avg_sales"]}
        for _, r in heatmap.iterrows()
    ]

    return {
        "monthly_total": monthly_list,
        "weekday_avg": weekday_rows,
        "weekend_vs_weekday": wvw,
        "month_year_heatmap": heatmap_list,
    }


def compute_eda(df: pd.DataFrame) -> dict:
    """Build the full EdaData object."""
    print("[02_eda] Computing EDA …")

    by_store = {}
    for store in STORES:
        df_store = df[df["store"] == store].copy()
        by_store[store] = _store_eda(df_store, store)

    # --- all-store monthly_total (sum of all stores) ---
    n_months = len(by_store[1]["monthly_total"])
    all_monthly = []
    for i in range(n_months):
        month_str = by_store[1]["monthly_total"][i]["month"]
        total_sales = sum(by_store[s]["monthly_total"][i]["sales"] for s in STORES)
        all_monthly.append({"month": month_str, "sales": total_sales})
    all_monthly = _rolling_12m(all_monthly)

    # --- all-store weekday_avg (all 35 rows) ---
    all_weekday = [row for s in STORES for row in by_store[s]["weekday_avg"]]

    # --- all-store weekend_vs_weekday (all 5 rows) ---
    all_wvw = [by_store[s]["weekend_vs_weekday"][0] for s in STORES]

    # --- all-store month_year_heatmap (60-row average across stores) ---
    hm0 = by_store[1]["month_year_heatmap"]
    all_heatmap = []
    for i, base in enumerate(hm0):
        avg = _round2(sum(by_store[s]["month_year_heatmap"][i]["avg_sales"] for s in STORES) / len(STORES))
        all_heatmap.append({"year": base["year"], "month": base["month"], "avg_sales": avg})

    # Convert by_store keys to string (JSON requirement)
    by_store_str = {str(k): v for k, v in by_store.items()}

    eda = {
        "monthly_total": all_monthly,
        "weekday_avg": all_weekday,
        "weekend_vs_weekday": all_wvw,
        "month_year_heatmap": all_heatmap,
        "by_store": by_store_str,
    }

    print(f"[02_eda] monthly_total={len(all_monthly)}, weekday_avg={len(all_weekday)}, "
          f"weekend_vs_weekday={len(all_wvw)}, heatmap={len(all_heatmap)}")

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    out = PUBLIC_DIR / "eda.json"
    with open(out, "w") as f:
        json.dump(eda, f, separators=(",", ":"))
    print(f"[02_eda] Saved → {out}")
    return eda


if __name__ == "__main__":
    df = pd.read_parquet(PROCESSED / "filtered.parquet")
    compute_eda(df)
