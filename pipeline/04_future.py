"""
04_future.py
For each series, fit Prophet on the FULL dataset (2013-01-01 to 2017-12-31)
and forecast 2018-01-01 to 2018-01-30 (30 days).

No leakage issue here — this is a genuine future forecast after all known data.
"""
import warnings
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

warnings.filterwarnings("ignore")
logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

FULL_END    = "2017-12-31"
FUTURE_START = "2018-01-01"
FUTURE_END   = "2018-01-30"

STORES = list(range(1, 6))
ITEMS  = list(range(1, 51))


def _round2(x: float) -> float:
    return round(float(x), 2)


def run_future(df: pd.DataFrame, backtest_results: list[dict]) -> list[dict]:
    """
    Adds 'future' key to each backtest_result dict.
    Returns the updated list.
    """
    from prophet import Prophet

    series_list = [(s, i) for s in STORES for i in ITEMS]
    result_map = {r["series_id"]: r for r in backtest_results}

    for idx, (store, item) in enumerate(tqdm(series_list, desc="Future")):
        seed = 42 + idx + 1000  # different seed from backtest
        series_id = f"S{store}_I{item}"
        r = result_map[series_id]

        # ── full data = train + test ─────────────────────────────────────────
        mask = (df["store"] == store) & (df["item"] == item)
        s = df[mask].sort_values("date").copy()
        prophet_df = s[["date", "sales"]].rename(columns={"date": "ds", "sales": "y"})
        prophet_df["y"] = prophet_df["y"].astype(float)

        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.8,
            uncertainty_samples=500,
        )
        m.fit(prophet_df, seed=seed)

        # forecast 30 days beyond 2017-12-31
        future_df = m.make_future_dataframe(periods=30, freq="D")
        fc = m.predict(future_df)

        fc_future = fc[fc["ds"].dt.strftime("%Y-%m-%d").between(FUTURE_START, FUTURE_END)].copy()
        fc_future = fc_future.sort_values("ds").reset_index(drop=True)
        assert len(fc_future) == 30, f"{series_id}: future len={len(fc_future)}"

        yhat       = fc_future["yhat"].clip(lower=0).values
        yhat_lower = fc_future["yhat_lower"].clip(lower=0).values
        yhat_upper = fc_future["yhat_upper"].clip(lower=0).values

        yhat_lower = np.minimum(yhat_lower, yhat)
        yhat_upper = np.maximum(yhat_upper, yhat)

        future_dates = [d.strftime("%Y-%m-%d") for d in fc_future["ds"]]

        r["future"] = {
            "model": [
                {"ds": d, "yhat": _round2(yh), "yhat_lower": _round2(yl), "yhat_upper": _round2(yu)}
                for d, yh, yl, yu in zip(future_dates, yhat, yhat_lower, yhat_upper)
            ]
        }

    return backtest_results


if __name__ == "__main__":
    from pathlib import Path
    PROCESSED = Path(__file__).parent / "data" / "processed"
    df = pd.read_parquet(PROCESSED / "filtered.parquet")
    # Quick test on one series
    from pipeline import run_pipeline  # noqa: would need full pipeline
    print("Run via pipeline.py")
