"""Prophet forecast fitting and prediction for POST /api/forecast/refit.

Matches the explicit model settings in pipeline/03_train_backtest.py and
pipeline/04_future.py:
- yearly_seasonality=True
- weekly_seasonality=True  
- daily_seasonality=False
- interval_width=0.8
- uncertainty_samples=500
- Prophet defaults (including additive seasonality and changepoint_prior_scale=0.05)
- Backtest seed=42+series index, as in pipeline/03_train_backtest.py

The fit uses ONLY rows with date <= train_end (no leakage).
"""

import hashlib
import json
import logging
import re
import time
from datetime import date
from pathlib import Path
from typing import Optional, Tuple
import threading

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from prophet import Prophet

from .config import RAW_CSV, CACHE_DIR as BACKEND_CACHE_DIR

# Prophet parameters matching pipeline exactly
PROPHET_PARAMS = {
    "yearly_seasonality": True,
    "weekly_seasonality": True,
    "daily_seasonality": False,
    "interval_width": 0.8,
    "uncertainty_samples": 500,
    "seasonality_mode": "additive",
    "changepoint_prior_scale": 0.05,
}

# Silence Prophet/cmdstan logging
logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet.models").setLevel(logging.WARNING)

# Cache directory
CACHE_DIR = BACKEND_CACHE_DIR / "forecast"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Semaphore for concurrent fits (max 2)
_fit_semaphore = threading.Semaphore(2)
_executor = ThreadPoolExecutor(max_workers=2)
_numpy_rng_lock = threading.Lock()


def _hash_params(params: dict) -> str:
    """Hash Prophet params for cache key."""
    # Sort keys for deterministic hash
    params_str = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(params_str.encode()).hexdigest()[:8]


def _round2(x: float) -> float:
    """Round to 2 decimal places."""
    return round(float(x), 2)


def _parse_series_id(series_id: str) -> Tuple[int, int]:
    """Parse store and item from series_id (S{store}_I{item})."""
    match = re.fullmatch(r"S([1-5])_I([1-9]|[1-4][0-9]|50)", series_id)
    if not match:
        raise ValueError(f"Invalid series_id format: {series_id}")
    return (int(match.group(1)), int(match.group(2)))


def _get_cache_path(series_id: str, train_end: str, horizon: int) -> Path:
    """Get cache file path for a forecast."""
    hash_val = _hash_params(PROPHET_PARAMS)
    return CACHE_DIR / f"{series_id}_{train_end}_{horizon}_{hash_val}.json"


def _load_cache(series_id: str, train_end: str, horizon: int) -> Optional[dict]:
    """Load cached forecast if exists and valid."""
    cache_path = _get_cache_path(series_id, train_end, horizon)
    if cache_path.exists():
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
            # Verify it's valid
            if "forecast" in data and "metrics" in data:
                data["cached"] = True
                return data
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logging.getLogger(__name__).warning(
                "Ignoring invalid forecast cache %s: %s",
                cache_path,
                exc,
            )
    return None


def _save_cache(series_id: str, train_end: str, horizon: int, data: dict) -> None:
    """Save forecast to cache."""
    cache_path = _get_cache_path(series_id, train_end, horizon)
    with open(cache_path, "w") as f:
        json.dump(data, f, separators=(",", ":"), allow_nan=False)


def _build_fit_df(
    raw_csv_path: Path,
    series_id: str,
    train_end: str,
    source_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Build fit dataframe with rows date <= train_end ONLY (no leakage)."""
    # Parse store and item from series_id (S{store}_I{item})
    store, item = _parse_series_id(series_id)
    
    # Read CSV and filter
    df = source_df.copy() if source_df is not None else pd.read_csv(raw_csv_path)
    df["date"] = pd.to_datetime(df["date"])
    
    # Filter for this series
    mask = (df["store"] == store) & (df["item"] == item)
    s = df[mask].copy()
    
    # Filter for train_end (date <= train_end, NO LEAKAGE)
    train_date = pd.Timestamp(train_end)
    fit_df = s[s["date"] <= train_date].copy()
    
    if len(fit_df) == 0:
        raise ValueError(f"No data for {series_id} before or on {train_end}")
    
    # Return with prophet column names
    fit_df = (
        fit_df.sort_values("date")[["date", "sales"]]
        .rename(columns={"date": "ds", "sales": "y"})
    )
    fit_df["y"] = fit_df["y"].astype(float)
    
    return fit_df


def _compute_metrics(
    actual_vals: np.ndarray,
    yhat_vals: np.ndarray,
    exclude_zeros_for_mape: bool = True,
) -> dict:
    """Compute MAPE and RMSE matching pipeline format."""
    yhat_vals = np.maximum(yhat_vals, 0)
    mask = actual_vals != 0 if exclude_zeros_for_mape else np.ones(len(actual_vals), dtype=bool)
    mape = (
        float(np.mean(np.abs((actual_vals[mask] - yhat_vals[mask]) / actual_vals[mask]))) * 100
        if mask.any()
        else 0.0
    )
    rmse = float(np.sqrt(np.mean((actual_vals - yhat_vals) ** 2)))
    return {"mape": _round2(mape), "rmse": _round2(rmse)}


def _predict_forecast(
    fit_df: pd.DataFrame,
    forecast_dates: pd.DatetimeIndex,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit one pipeline-configured Prophet model and return clipped forecast bands."""
    model = Prophet(**PROPHET_PARAMS)
    logging.getLogger("prophet").setLevel(logging.CRITICAL)
    logging.getLogger("cmdstanpy").setLevel(logging.CRITICAL)
    with _fit_semaphore, _numpy_rng_lock:
        numpy_state = np.random.get_state()
        try:
            np.random.seed(seed)
            model.fit(fit_df, seed=seed)
            future = model.make_future_dataframe(
                periods=len(forecast_dates), freq="D"
            )
            predicted = model.predict(future)
        finally:
            np.random.set_state(numpy_state)
    forecast = predicted[predicted["ds"].isin(forecast_dates)].sort_values("ds")
    if len(forecast) != len(forecast_dates):
        raise ValueError(
            f"Expected {len(forecast_dates)} forecast rows, got {len(forecast)}"
        )
    yhat = np.maximum(forecast["yhat"].to_numpy(dtype=float), 0)
    yhat_lower = np.minimum(
        np.maximum(forecast["yhat_lower"].to_numpy(dtype=float), 0), yhat
    )
    yhat_upper = np.maximum(
        np.maximum(forecast["yhat_upper"].to_numpy(dtype=float), 0), yhat
    )
    return yhat, yhat_lower, yhat_upper


def refit(
    series_id: str,
    train_end: date,
    horizon: int = 30
) -> dict:
    """
    Fit Prophet on series data up to train_end and forecast `horizon` days.
    
    Returns:
        {
            series_id, train_end, horizon,
            forecast: ForecastPoint[],
            actual: Point[] (empty if no actual data in forecast period),
            metrics: {model:{mape,rmse}, baseline:{mape,rmse}} or null,
            fit_seconds: float,
            cached: bool,
            params: PROPHET_PARAMS
        }
    """
    raw_csv_path = Path(RAW_CSV)
    
    # Parse store and item for later use
    store, item = _parse_series_id(series_id)
    
    # Check CSV exists
    if not raw_csv_path.exists():
        raise FileNotFoundError(
            f"Raw CSV not found: {RAW_CSV}. "
            "Set DEMANDLENS_RAW_CSV env var or ensure pipeline has run."
        )
    
    # Check cache first
    train_end_str = train_end.isoformat()
    start_time = time.perf_counter()
    cached = _load_cache(series_id, train_end_str, horizon)
    if cached:
        cached["fit_seconds"] = round(time.perf_counter() - start_time, 3)
        return cached

    # Build fit dataframe with NO LEAKAGE (date <= train_end only)
    source_df = pd.read_csv(raw_csv_path)
    fit_df = _build_fit_df(
        raw_csv_path, series_id, train_end_str, source_df=source_df
    )
    
    # Debug: verify no leakage
    max_date_in_fit = fit_df["ds"].max()
    if max_date_in_fit > pd.Timestamp(train_end_str):
        raise ValueError(
            f"LEAKAGE DETECTED: fit max date {max_date_in_fit} > train_end {train_end_str}"
        )
    
    # Build future dates (horizon days after train_end)
    future_dates = pd.date_range(
        start=pd.Timestamp(train_end_str) + pd.Timedelta(days=1),
        periods=horizon,
        freq="D"
    )
    
    # Match run_backtest's per-series seed: store-major order, zero-based index.
    seed = 42 + (store - 1) * 50 + (item - 1)
    if train_end == date(2017, 12, 31):
        seed += 1000
    yhat, yhat_lower, yhat_upper = _predict_forecast(
        fit_df, future_dates, seed
    )
    
    # Format forecast points
    forecast = [
        {
            "ds": d.strftime("%Y-%m-%d"),
            "yhat": _round2(yh),
            "yhat_lower": _round2(yl),
            "yhat_upper": _round2(yu),
        }
        for d, yh, yl, yu in zip(future_dates, yhat, yhat_lower, yhat_upper)
    ]
    
    source_df["date"] = pd.to_datetime(source_df["date"])
    s = source_df[(source_df["store"] == store) & (source_df["item"] == item)].copy()
    
    # Get actual values for forecast period (if any)
    forecast_dates_set = set(future_dates)
    actual_rows = s[s["date"].isin(forecast_dates_set)].sort_values("date")
    actual = []
    actual_vals = np.array([])
    forecast_vals = np.array([])
    
    if len(actual_rows) > 0:
        # Sort by date and align with forecast
        actual_rows = actual_rows.sort_values("date")
        actual_vals = actual_rows["sales"].values.astype(float)
        dates_to_positions = {
            forecast_date: position
            for position, forecast_date in enumerate(future_dates)
        }
        forecast_vals = np.array([
            yhat[dates_to_positions[pd.Timestamp(actual_date)]]
            for actual_date in actual_rows["date"]
        ])
        
        for _, row in actual_rows.iterrows():
            actual.append({
                "ds": row["date"].strftime("%Y-%m-%d"),
                "y": int(row["sales"])
            })
    
    # Compute metrics if we have actual values
    metrics = None
    if len(actual) > 0:
        # Baseline: last 28 days mean (only using data <= train_end)
        last28 = fit_df.tail(28)["y"].values
        baseline_val = float(np.mean(last28))
        baseline_vals = np.full(len(actual_vals), baseline_val)
        
        model_metrics = _compute_metrics(actual_vals, forecast_vals)
        baseline_metrics = _compute_metrics(actual_vals, baseline_vals)
        
        metrics = {
            "model": model_metrics,
            "baseline": baseline_metrics
        }
    
    fit_seconds = round(time.perf_counter() - start_time, 3)
    
    result = {
        "series_id": series_id,
        "train_end": train_end_str,
        "horizon": horizon,
        "forecast": forecast,
        "actual": actual,
        "metrics": metrics,
        "fit_seconds": fit_seconds,
        "cached": False,
        "params": PROPHET_PARAMS
    }
    
    # Save to cache
    _save_cache(series_id, train_end_str, horizon, result)
    
    return result
