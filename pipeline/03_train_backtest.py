"""
03_train_backtest.py
For each of the 250 series:
  - Fit Prophet on the train window (2013-01-01 to 2017-11-30) — no leakage
  - Predict the test hold-out (2017-12-01 to 2017-12-31, 31 days)
  - Compute baselines: flat 28-day mean, seasonal naive
  - Compute h14, h30 metrics (MAPE, RMSE), coverage_80, winner

Saves processed/backtest_results.parquet and per-series dicts (in memory,
passed to 05_export.py).
"""

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

warnings.filterwarnings("ignore")

PROCESSED  = Path(__file__).parent / "data" / "processed"

TRAIN_START = "2013-01-01"
TRAIN_END   = "2017-11-30"
TEST_START  = "2017-12-01"
TEST_END    = "2017-12-31"

STORES = list(range(1, 6))
ITEMS  = list(range(1, 51))


# ── metric helpers ──────────────────────────────────────────────────────────

def _round2(x: float) -> float:
    return round(float(x), 2)


def _mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """MAPE in percent, skipping zeros in actual."""
    mask = actual != 0
    if not mask.any():
        return 0.0
    return _round2(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return _round2(float(np.sqrt(np.mean((actual - predicted) ** 2))))


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    return {"mape": _mape(actual, predicted), "rmse": _rmse(actual, predicted)}


# ── main ─────────────────────────────────────────────────────────────────────

def run_backtest(df: pd.DataFrame) -> list[dict]:
    """
    Returns list of 250 series dicts (backtest portion only).
    Each dict keys: series_id, store, item, history, backtest, metrics_partial
    """
    from prophet import Prophet

    results = []
    series_list = [(s, i) for s in STORES for i in ITEMS]

    for idx, (store, item) in enumerate(tqdm(series_list, desc="Backtest")):
        seed = 42 + idx
        series_id = f"S{store}_I{item}"

        # ── slice this series ───────────────────────────────────────────────
        mask = (df["store"] == store) & (df["item"] == item)
        s = df[mask].sort_values("date").copy()
        s["date"] = pd.to_datetime(s["date"])

        train = s[s["date"] <= TRAIN_END].copy()
        test  = s[(s["date"] >= TEST_START) & (s["date"] <= TEST_END)].copy()

        # ── history = last 365 days of train (2016-12-01 to 2017-11-30) ─────
        history_start = pd.Timestamp("2016-12-01")
        hist = train[train["date"] >= history_start].copy()
        history = [
            {"ds": row["date"].strftime("%Y-%m-%d"), "y": int(row["sales"])}
            for _, row in hist.iterrows()
        ]
        assert len(history) == 365, f"{series_id}: history len={len(history)}"

        # ── baseline: mean of last 28 training days (flat) ──────────────────
        last28 = train.sort_values("date").tail(28)["sales"].values
        baseline_val = _round2(float(np.mean(last28)))
        baseline_sigma = _round2(float(np.std(last28, ddof=1))) if len(last28) > 1 else 0.0

        # ── seasonal naive: same day 1 year ago ─────────────────────────────
        test_dates = pd.to_datetime(test["date"])
        sn_preds = []
        for d in test_dates:
            d_ly = d - pd.DateOffset(years=1)
            row_ly = train[train["date"] == d_ly]
            sn_preds.append(float(row_ly["sales"].iloc[0]) if len(row_ly) else baseline_val)
        sn_preds = np.array(sn_preds)

        # ── fit Prophet on train ─────────────────────────────────────────────
        prophet_df = train[["date", "sales"]].rename(columns={"date": "ds", "sales": "y"})
        prophet_df["y"] = prophet_df["y"].astype(float)

        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.8,
            uncertainty_samples=500,
        )
        # suppress stdout logs
        import logging
        logging.getLogger("prophet").setLevel(logging.WARNING)
        logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

        m.fit(prophet_df, seed=seed)

        # predict train + test (make_future_dataframe extends by 31 days)
        future = m.make_future_dataframe(periods=31, freq="D")
        fc = m.predict(future)

        # align forecast to test dates
        fc_test = fc[fc["ds"].dt.strftime("%Y-%m-%d").between(TEST_START, TEST_END)].copy()
        fc_test = fc_test.sort_values("ds").reset_index(drop=True)

        assert len(fc_test) == 31, f"{series_id}: forecast test len={len(fc_test)}"

        # ── build actual / model / baseline arrays ───────────────────────────
        actual_vals = test.sort_values("date")["sales"].values.astype(float)
        yhat        = fc_test["yhat"].clip(lower=0).values
        yhat_lower  = fc_test["yhat_lower"].clip(lower=0).values
        yhat_upper  = fc_test["yhat_upper"].clip(lower=0).values

        # enforce band sanity: lower <= yhat <= upper
        yhat_lower = np.minimum(yhat_lower, yhat)
        yhat_upper = np.maximum(yhat_upper, yhat)

        test_dates_str = [d.strftime("%Y-%m-%d") for d in test.sort_values("date")["date"]]

        backtest_actual   = [{"ds": d, "y": int(v)} for d, v in zip(test_dates_str, actual_vals)]
        backtest_model    = [
            {"ds": d, "yhat": _round2(yh), "yhat_lower": _round2(yl), "yhat_upper": _round2(yu)}
            for d, yh, yl, yu in zip(test_dates_str, yhat, yhat_lower, yhat_upper)
        ]
        backtest_baseline = [{"ds": d, "yhat": baseline_val} for d in test_dates_str]
        backtest_sn       = [{"ds": d, "yhat": _round2(v)} for d, v in zip(test_dates_str, sn_preds)]

        # ── metrics ──────────────────────────────────────────────────────────
        # IMPORTANT: compute metrics on ROUNDED values (same as what is stored in JSON)
        # so that tests can recompute identical numbers from the exported files.
        # h14 = first 14 days of Dec; h30 = first 30 days of Dec (PRD definition).
        yhat_r    = np.array([p["yhat"]       for p in backtest_model])
        yl_r      = np.array([p["yhat_lower"] for p in backtest_model])
        yu_r      = np.array([p["yhat_upper"] for p in backtest_model])
        sn_r      = np.array([p["yhat"]       for p in backtest_sn])
        bv_arr30  = np.full(30, baseline_val)
        bv_arr14  = np.full(14, baseline_val)

        h14_model    = _metrics(actual_vals[:14], yhat_r[:14])
        h14_baseline = _metrics(actual_vals[:14], bv_arr14)
        h14_sn       = _metrics(actual_vals[:14], sn_r[:14])

        # h30 = first 30 days (Dec 1–30), NOT all 31 (that was a pipeline bug)
        h30_model    = _metrics(actual_vals[:30], yhat_r[:30])
        h30_baseline = _metrics(actual_vals[:30], bv_arr30)
        h30_sn       = _metrics(actual_vals[:30], sn_r[:30])

        # coverage_80: fraction of the first 30 test days where actual falls within
        # the 80% band, computed on rounded bounds (consistent with stored JSON).
        coverage_80 = _round2(
            float(np.mean((actual_vals[:30] >= yl_r[:30]) & (actual_vals[:30] <= yu_r[:30])))
        )

        winner = "model" if h30_model["mape"] < h30_baseline["mape"] else "baseline"

        results.append({
            "series_id": series_id,
            "store": store,
            "item": item,
            "history": history,
            "backtest": {
                "actual": backtest_actual,
                "model": backtest_model,
                "baseline": backtest_baseline,
                "seasonal_naive": backtest_sn,
            },
            "metrics": {
                "h14": {"model": h14_model, "baseline": h14_baseline, "seasonal_naive": h14_sn},
                "h30": {"model": h30_model, "baseline": h30_baseline, "seasonal_naive": h30_sn},
                "coverage_80": coverage_80,
                "winner": winner,
            },
            # stash for future step
            "_train_df": prophet_df,
            "_baseline_val": baseline_val,
            "_baseline_sigma": baseline_sigma,
            "_last28_mean": float(np.mean(last28)),
            "_last28_std": baseline_sigma,
        })

    return results


if __name__ == "__main__":
    df = pd.read_parquet(PROCESSED / "filtered.parquet")
    results = run_backtest(df)
    wins = sum(1 for r in results if r["metrics"]["winner"] == "model")
    print(f"\nBacktest done. Model wins: {wins}/250 ({wins/2.5:.1f}%)")

    # summary stats
    h30_improvements = [
        (r["metrics"]["h30"]["baseline"]["mape"] - r["metrics"]["h30"]["model"]["mape"])
        / r["metrics"]["h30"]["baseline"]["mape"] * 100
        for r in results
    ]
    coverages = [r["metrics"]["coverage_80"] for r in results]
    print(f"Median MAPE improvement: {np.median(h30_improvements):.1f}%")
    print(f"Median coverage_80: {np.median(coverages):.3f}")
