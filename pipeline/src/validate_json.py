#!/usr/bin/env python3
"""
Day-0 JSON validation script for DemandLens dataset.

Validates every JSON file in the data directory (default: public/data relative
to repo root) against the expected shapes and constraints defined in
lib/types.ts and project requirements.

Validated schemas:
1. manifest.json:
   - Must have keys: stores (array of ints), items (array of ints),
     series_ids (array of strings, exactly 250 entries), train_end (string),
     test_start (string), test_end (string), future_end (string).
2. Each series file series/S{s}_I{i}.json:
   - Must have keys: schema_version (must be 1), series_id (string matching S{store}_I{item}),
     store (int 1-5), item (int 1-50), history, backtest, future, metrics.
   - history: array of {ds, y} points, length exactly 365.
   - backtest.actual: array of {ds, y} points, length exactly 31.
   - backtest.model: array of {ds, yhat, yhat_lower, yhat_upper} points, length exactly 31.
   - backtest.baseline: array of {ds, yhat} points, length exactly 31.
   - backtest.seasonal_naive (optional): array of {ds, yhat} points, if present length 31.
   - future.model: array of {ds, yhat, yhat_lower, yhat_upper} points, length exactly 30.
   - metrics.h14 and metrics.h30: each has model and baseline with {mape, rmse}.
   - metrics.coverage_80: float in [0.0, 1.0].
   - metrics.winner: 'model' or 'baseline'.
   - All dates must be ISO YYYY-MM-DD format.
   - All numeric values must be rounded to at most 2 decimal places.
3. portfolio.json:
   - Array of objects with keys: series_id, store, item, model_mape,
     baseline_mape, improvement_pct, winner.
   - Length exactly 250.
4. restock_inputs.json (or restock.json):
   - Dict keyed by series_id, each value has: store, item, current_stock,
     avg_daily_28, sigma_daily, yhat_future (array of length >= 30).
   - Exactly 250 entries.
5. eda.json:
   - Must have keys: monthly_total, weekday_avg, weekend_vs_weekday.
   - monthly_total: array of {month, sales} objects.
   - weekday_avg: array of {store, dow, avg_sales} objects.
   - weekend_vs_weekday: array of {store, weekday_avg, weekend_avg} objects.

CLI Usage:
    python validate_json.py [DATA_DIR] [--data-dir DATA_DIR] [--require-all]

Exit code:
    0: All checked files passed validation.
    1: At least one file failed validation or no files found.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys
from typing import Any


def is_valid_iso_date(val: Any) -> bool:
    """Check if value is a valid ISO YYYY-MM-DD date string."""
    if not isinstance(val, str):
        return False
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", val):
        return False
    try:
        datetime.strptime(val, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def is_valid_iso_year_month(val: Any) -> bool:
    """Check if value is a valid ISO YYYY-MM string."""
    if not isinstance(val, str):
        return False
    if not re.match(r"^\d{4}-\d{2}$", val):
        return False
    try:
        datetime.strptime(val, "%Y-%m")
        return True
    except ValueError:
        return False


def is_at_most_2_decimals(val: Any) -> bool:
    """Check if value is a finite number rounded to at most 2 decimal places."""
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    if math.isnan(val) or math.isinf(val):
        return False
    return abs(val - round(val, 2)) < 1e-5


def validate_manifest(data: Any) -> list[str]:
    """Validate manifest.json schema and rules."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Root must be an object/dict"]

    required_keys = {"stores", "items", "series_ids", "train_end", "test_start", "test_end", "future_end"}
    missing = required_keys - set(data.keys())
    if missing:
        errors.append(f"Missing required keys: {sorted(missing)}")

    stores = data.get("stores")
    if not isinstance(stores, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in stores):
        errors.append("'stores' must be an array of integers")
    elif len(stores) != 5 or set(stores) != {1, 2, 3, 4, 5}:
        errors.append("'stores' must contain stores 1 through 5")

    items = data.get("items")
    if not isinstance(items, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in items):
        errors.append("'items' must be an array of integers")
    elif len(items) != 50 or set(items) != set(range(1, 51)):
        errors.append("'items' must contain items 1 through 50")

    series_ids = data.get("series_ids")
    if not isinstance(series_ids, list) or not all(isinstance(x, str) for x in series_ids):
        errors.append("'series_ids' must be an array of strings")
    elif len(series_ids) != 250:
        errors.append(f"'series_ids' must have exactly 250 entries, found {len(series_ids)}")

    for date_key in ("train_end", "test_start", "test_end", "future_end"):
        if date_key in data and not is_valid_iso_date(data[date_key]):
            errors.append(f"'{date_key}' must be a valid ISO YYYY-MM-DD date string, found {data.get(date_key)!r}")

    return errors


def validate_series(data: Any, expected_store: int | None = None, expected_item: int | None = None) -> list[str]:
    """Validate series/S{s}_I{i}.json schema and rules."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Root must be an object/dict"]

    required_keys = {"schema_version", "series_id", "store", "item", "history", "backtest", "future", "metrics"}
    missing = required_keys - set(data.keys())
    if missing:
        errors.append(f"Missing required keys: {sorted(missing)}")

    if data.get("schema_version") != 1 or isinstance(data.get("schema_version"), bool):
        errors.append(f"'schema_version' must be 1, found {data.get('schema_version')!r}")

    store = data.get("store")
    if not isinstance(store, int) or isinstance(store, bool) or not (1 <= store <= 5):
        errors.append(f"'store' must be an integer between 1 and 5, found {store!r}")
    elif expected_store is not None and store != expected_store:
        errors.append(f"'store' {store} does not match expected store {expected_store}")

    item = data.get("item")
    if not isinstance(item, int) or isinstance(item, bool) or not (1 <= item <= 50):
        errors.append(f"'item' must be an integer between 1 and 50, found {item!r}")
    elif expected_item is not None and item != expected_item:
        errors.append(f"'item' {item} does not match expected item {expected_item}")

    series_id = data.get("series_id")
    expected_id = f"S{store}_I{item}" if (isinstance(store, int) and isinstance(item, int)) else None
    if not isinstance(series_id, str):
        errors.append(f"'series_id' must be a string, found {series_id!r}")
    elif expected_id and series_id != expected_id:
        errors.append(f"'series_id' {series_id!r} does not match expected {expected_id!r}")

    # Validate history: exactly 365 points
    history = data.get("history")
    if not isinstance(history, list):
        errors.append("'history' must be an array")
    elif len(history) != 365:
        errors.append(f"'history' must have exactly 365 points, found {len(history)}")
    else:
        for idx, pt in enumerate(history):
            if not isinstance(pt, dict) or "ds" not in pt or "y" not in pt:
                errors.append(f"history[{idx}] must be an object with 'ds' and 'y'")
                break
            if not is_valid_iso_date(pt["ds"]):
                errors.append(f"history[{idx}].ds is not a valid ISO YYYY-MM-DD date: {pt.get('ds')!r}")
                break
            if not is_at_most_2_decimals(pt["y"]):
                errors.append(f"history[{idx}].y must be numeric with at most 2 decimal places: {pt.get('y')!r}")
                break

    # Validate backtest
    backtest = data.get("backtest")
    if not isinstance(backtest, dict):
        errors.append("'backtest' must be an object")
    else:
        # backtest.actual: exactly 31 points
        actual = backtest.get("actual")
        if not isinstance(actual, list):
            errors.append("'backtest.actual' must be an array")
        elif len(actual) != 31:
            errors.append(f"'backtest.actual' must have exactly 31 points, found {len(actual)}")
        else:
            for idx, pt in enumerate(actual):
                if not isinstance(pt, dict) or "ds" not in pt or "y" not in pt:
                    errors.append(f"backtest.actual[{idx}] must have 'ds' and 'y'")
                    break
                if not is_valid_iso_date(pt["ds"]):
                    errors.append(f"backtest.actual[{idx}].ds invalid date: {pt.get('ds')!r}")
                    break
                if not is_at_most_2_decimals(pt["y"]):
                    errors.append(f"backtest.actual[{idx}].y not rounded to <= 2 decimals: {pt.get('y')!r}")
                    break

        # backtest.model: exactly 31 points
        model = backtest.get("model")
        if not isinstance(model, list):
            errors.append("'backtest.model' must be an array")
        elif len(model) != 31:
            errors.append(f"'backtest.model' must have exactly 31 points, found {len(model)}")
        else:
            for idx, pt in enumerate(model):
                if not isinstance(pt, dict) or not {"ds", "yhat", "yhat_lower", "yhat_upper"}.issubset(pt.keys()):
                    errors.append(f"backtest.model[{idx}] must have ds, yhat, yhat_lower, yhat_upper")
                    break
                if not is_valid_iso_date(pt["ds"]):
                    errors.append(f"backtest.model[{idx}].ds invalid date: {pt.get('ds')!r}")
                    break
                for num_key in ("yhat", "yhat_lower", "yhat_upper"):
                    if not is_at_most_2_decimals(pt.get(num_key)):
                        errors.append(f"backtest.model[{idx}].{num_key} not rounded to <= 2 decimals: {pt.get(num_key)!r}")
                        break

        # backtest.baseline: exactly 31 points
        baseline = backtest.get("baseline")
        if not isinstance(baseline, list):
            errors.append("'backtest.baseline' must be an array")
        elif len(baseline) != 31:
            errors.append(f"'backtest.baseline' must have exactly 31 points, found {len(baseline)}")
        else:
            for idx, pt in enumerate(baseline):
                if not isinstance(pt, dict) or "ds" not in pt or "yhat" not in pt:
                    errors.append(f"backtest.baseline[{idx}] must have 'ds' and 'yhat'")
                    break
                if not is_valid_iso_date(pt["ds"]):
                    errors.append(f"backtest.baseline[{idx}].ds invalid date: {pt.get('ds')!r}")
                    break
                if not is_at_most_2_decimals(pt["yhat"]):
                    errors.append(f"backtest.baseline[{idx}].yhat not rounded to <= 2 decimals: {pt.get('yhat')!r}")
                    break

        # backtest.seasonal_naive: optional, if present length 31
        if "seasonal_naive" in backtest and backtest["seasonal_naive"] is not None:
            s_naive = backtest["seasonal_naive"]
            if not isinstance(s_naive, list):
                errors.append("'backtest.seasonal_naive' must be an array if present")
            elif len(s_naive) != 31:
                errors.append(f"'backtest.seasonal_naive' must have exactly 31 points if present, found {len(s_naive)}")
            else:
                for idx, pt in enumerate(s_naive):
                    if not isinstance(pt, dict) or "ds" not in pt or "yhat" not in pt:
                        errors.append(f"backtest.seasonal_naive[{idx}] must have 'ds' and 'yhat'")
                        break
                    if not is_valid_iso_date(pt["ds"]):
                        errors.append(f"backtest.seasonal_naive[{idx}].ds invalid date: {pt.get('ds')!r}")
                        break
                    if not is_at_most_2_decimals(pt["yhat"]):
                        errors.append(f"backtest.seasonal_naive[{idx}].yhat not rounded to <= 2 decimals: {pt.get('yhat')!r}")
                        break

    # Validate future.model: exactly 30 points
    future = data.get("future")
    if not isinstance(future, dict):
        errors.append("'future' must be an object")
    else:
        fut_model = future.get("model")
        if not isinstance(fut_model, list):
            errors.append("'future.model' must be an array")
        elif len(fut_model) != 30:
            errors.append(f"'future.model' must have exactly 30 points, found {len(fut_model)}")
        else:
            for idx, pt in enumerate(fut_model):
                if not isinstance(pt, dict) or not {"ds", "yhat", "yhat_lower", "yhat_upper"}.issubset(pt.keys()):
                    errors.append(f"future.model[{idx}] must have ds, yhat, yhat_lower, yhat_upper")
                    break
                if not is_valid_iso_date(pt["ds"]):
                    errors.append(f"future.model[{idx}].ds invalid date: {pt.get('ds')!r}")
                    break
                for num_key in ("yhat", "yhat_lower", "yhat_upper"):
                    if not is_at_most_2_decimals(pt.get(num_key)):
                        errors.append(f"future.model[{idx}].{num_key} not rounded to <= 2 decimals: {pt.get(num_key)!r}")
                        break

    # Validate metrics
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        errors.append("'metrics' must be an object")
    else:
        for h in ("h14", "h30"):
            h_metrics = metrics.get(h)
            if not isinstance(h_metrics, dict):
                errors.append(f"'metrics.{h}' must be an object")
            else:
                for src in ("model", "baseline"):
                    src_metrics = h_metrics.get(src)
                    if not isinstance(src_metrics, dict):
                        errors.append(f"'metrics.{h}.{src}' must be an object")
                    else:
                        for m_key in ("mape", "rmse"):
                            val = src_metrics.get(m_key)
                            if not is_at_most_2_decimals(val):
                                errors.append(f"'metrics.{h}.{src}.{m_key}' not rounded to <= 2 decimals: {val!r}")
                if "seasonal_naive" in h_metrics and h_metrics["seasonal_naive"] is not None:
                    sn_metrics = h_metrics["seasonal_naive"]
                    if isinstance(sn_metrics, dict):
                        for m_key in ("mape", "rmse"):
                            val = sn_metrics.get(m_key)
                            if not is_at_most_2_decimals(val):
                                errors.append(f"'metrics.{h}.seasonal_naive.{m_key}' not rounded to <= 2 decimals: {val!r}")

        coverage = metrics.get("coverage_80")
        if not is_at_most_2_decimals(coverage) or not (0.0 <= coverage <= 1.0):
            errors.append(f"'metrics.coverage_80' must be a float in [0.0, 1.0] with <= 2 decimals, found {coverage!r}")

        winner = metrics.get("winner")
        if winner not in ("model", "baseline"):
            errors.append(f"'metrics.winner' must be 'model' or 'baseline', found {winner!r}")

    return errors


def validate_portfolio(data: Any) -> list[str]:
    """Validate portfolio.json schema and rules."""
    errors: list[str] = []
    if not isinstance(data, list):
        return ["Root must be an array/list"]

    if len(data) != 250:
        errors.append(f"portfolio must have exactly 250 entries, found {len(data)}")

    required_keys = {"series_id", "store", "item", "model_mape", "baseline_mape", "improvement_pct", "winner"}
    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            errors.append(f"portfolio[{idx}] must be an object")
            break
        missing = required_keys - set(row.keys())
        if missing:
            errors.append(f"portfolio[{idx}] missing keys: {sorted(missing)}")
            break
        if not isinstance(row.get("series_id"), str):
            errors.append(f"portfolio[{idx}].series_id must be a string")
            break
        if not isinstance(row.get("store"), int) or isinstance(row.get("store"), bool) or not (1 <= row["store"] <= 5):
            errors.append(f"portfolio[{idx}].store must be int between 1 and 5")
            break
        if not isinstance(row.get("item"), int) or isinstance(row.get("item"), bool) or not (1 <= row["item"] <= 50):
            errors.append(f"portfolio[{idx}].item must be int between 1 and 50")
            break
        if not is_at_most_2_decimals(row.get("model_mape")):
            errors.append(f"portfolio[{idx}].model_mape not rounded to <= 2 decimals: {row.get('model_mape')!r}")
            break
        if not is_at_most_2_decimals(row.get("baseline_mape")):
            errors.append(f"portfolio[{idx}].baseline_mape not rounded to <= 2 decimals: {row.get('baseline_mape')!r}")
            break
        if not is_at_most_2_decimals(row.get("improvement_pct")):
            errors.append(f"portfolio[{idx}].improvement_pct not rounded to <= 2 decimals: {row.get('improvement_pct')!r}")
            break
        if row.get("winner") not in ("model", "baseline"):
            errors.append(f"portfolio[{idx}].winner must be 'model' or 'baseline', found {row.get('winner')!r}")
            break

    return errors


def validate_restock_inputs(data: Any) -> list[str]:
    """Validate restock_inputs.json (or restock.json) schema and rules."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Root must be an object/dict keyed by series_id"]

    if len(data) != 250:
        errors.append(f"restock_inputs must have exactly 250 entries, found {len(data)}")

    required_keys = {"store", "item", "current_stock", "avg_daily_28", "sigma_daily", "yhat_future"}
    for sid, val in data.items():
        if not isinstance(sid, str):
            errors.append(f"Key {sid!r} must be a string series_id")
            break
        if not isinstance(val, dict):
            errors.append(f"Value for {sid} must be an object")
            break
        missing = required_keys - set(val.keys())
        if missing:
            errors.append(f"{sid} missing keys: {sorted(missing)}")
            break
        if not isinstance(val.get("store"), int) or isinstance(val.get("store"), bool) or not (1 <= val["store"] <= 5):
            errors.append(f"{sid}.store must be int between 1 and 5")
            break
        if not isinstance(val.get("item"), int) or isinstance(val.get("item"), bool) or not (1 <= val["item"] <= 50):
            errors.append(f"{sid}.item must be int between 1 and 50")
            break
        if not isinstance(val.get("current_stock"), int) or isinstance(val.get("current_stock"), bool) or val["current_stock"] < 0:
            errors.append(f"{sid}.current_stock must be non-negative integer: {val.get('current_stock')!r}")
            break
        if not is_at_most_2_decimals(val.get("avg_daily_28")) or val["avg_daily_28"] <= 0:
            errors.append(f"{sid}.avg_daily_28 must be positive number with <= 2 decimals: {val.get('avg_daily_28')!r}")
            break
        if not is_at_most_2_decimals(val.get("sigma_daily")) or val["sigma_daily"] <= 0:
            errors.append(f"{sid}.sigma_daily must be positive number with <= 2 decimals: {val.get('sigma_daily')!r}")
            break
        yhat_fut = val.get("yhat_future")
        if not isinstance(yhat_fut, list) or len(yhat_fut) < 30:
            errors.append(f"{sid}.yhat_future must be an array of length >= 30, found {len(yhat_fut) if isinstance(yhat_fut, list) else type(yhat_fut)}")
            break
        for idx, yhat in enumerate(yhat_fut):
            if not is_at_most_2_decimals(yhat):
                errors.append(f"{sid}.yhat_future[{idx}] not rounded to <= 2 decimals: {yhat!r}")
                break

    return errors


def validate_eda(data: Any) -> list[str]:
    """Validate eda.json schema and rules."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Root must be an object/dict"]

    required_keys = {"monthly_total", "weekday_avg", "weekend_vs_weekday"}
    missing = required_keys - set(data.keys())
    if missing:
        errors.append(f"Missing required keys: {sorted(missing)}")

    # Validate monthly_total: array of {month, sales}
    monthly_total = data.get("monthly_total")
    if not isinstance(monthly_total, list) or len(monthly_total) == 0:
        errors.append("'monthly_total' must be a non-empty array")
    else:
        for idx, pt in enumerate(monthly_total):
            if not isinstance(pt, dict) or "month" not in pt or "sales" not in pt:
                errors.append(f"monthly_total[{idx}] must have 'month' and 'sales'")
                break
            if not is_valid_iso_year_month(pt["month"]):
                errors.append(f"monthly_total[{idx}].month invalid YYYY-MM: {pt.get('month')!r}")
                break
            if isinstance(pt["sales"], bool) or not isinstance(pt["sales"], (int, float)):
                errors.append(f"monthly_total[{idx}].sales must be numeric: {pt.get('sales')!r}")
                break

    # Validate weekday_avg: array of {store, dow, avg_sales}
    weekday_avg = data.get("weekday_avg")
    if not isinstance(weekday_avg, list) or len(weekday_avg) == 0:
        errors.append("'weekday_avg' must be a non-empty array")
    else:
        for idx, pt in enumerate(weekday_avg):
            if not isinstance(pt, dict) or not {"store", "dow", "avg_sales"}.issubset(pt.keys()):
                errors.append(f"weekday_avg[{idx}] must have 'store', 'dow', 'avg_sales'")
                break
            if not isinstance(pt["store"], int) or isinstance(pt["store"], bool) or not (1 <= pt["store"] <= 5):
                errors.append(f"weekday_avg[{idx}].store must be int 1-5")
                break
            if not isinstance(pt["dow"], int) or isinstance(pt["dow"], bool) or not (0 <= pt["dow"] <= 6):
                errors.append(f"weekday_avg[{idx}].dow must be int 0-6")
                break
            if isinstance(pt["avg_sales"], bool) or not isinstance(pt["avg_sales"], (int, float)):
                errors.append(f"weekday_avg[{idx}].avg_sales must be numeric")
                break

    # Validate weekend_vs_weekday: array of {store, weekday_avg, weekend_avg}
    weekend_vs_weekday = data.get("weekend_vs_weekday")
    if not isinstance(weekend_vs_weekday, list) or len(weekend_vs_weekday) == 0:
        errors.append("'weekend_vs_weekday' must be a non-empty array")
    else:
        for idx, pt in enumerate(weekend_vs_weekday):
            if not isinstance(pt, dict) or not {"store", "weekday_avg", "weekend_avg"}.issubset(pt.keys()):
                errors.append(f"weekend_vs_weekday[{idx}] must have 'store', 'weekday_avg', 'weekend_avg'")
                break
            if not isinstance(pt["store"], int) or isinstance(pt["store"], bool) or not (1 <= pt["store"] <= 5):
                errors.append(f"weekend_vs_weekday[{idx}].store must be int 1-5")
                break
            if isinstance(pt["weekday_avg"], bool) or not isinstance(pt["weekday_avg"], (int, float)):
                errors.append(f"weekend_vs_weekday[{idx}].weekday_avg must be numeric")
                break
            if isinstance(pt["weekend_avg"], bool) or not isinstance(pt["weekend_avg"], (int, float)):
                errors.append(f"weekend_vs_weekday[{idx}].weekend_avg must be numeric")
                break

    return errors


def validate_file(file_path: Path, data_dir: Path) -> tuple[bool, list[str]]:
    """Validate a single JSON file based on its relative path."""
    try:
        rel_path = file_path.relative_to(data_dir).as_posix()
    except ValueError:
        rel_path = file_path.name

    if not file_path.exists():
        return False, [f"File not found: {file_path}"]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
    except Exception as e:
        return False, [f"Failed to parse JSON: {e}"]

    if rel_path == "manifest.json":
        errors = validate_manifest(content)
    elif rel_path == "portfolio.json":
        errors = validate_portfolio(content)
    elif rel_path in ("restock_inputs.json", "restock.json"):
        errors = validate_restock_inputs(content)
    elif rel_path == "eda.json":
        errors = validate_eda(content)
    elif rel_path.startswith("series/") and rel_path.endswith(".json"):
        match = re.match(r"^series/S([1-5])_I([1-9]|[1-4][0-9]|50)\.json$", rel_path)
        if not match:
            errors = [f"Series filename must match series/S{{1-5}}_I{{1-50}}.json, got {rel_path}"]
        else:
            exp_store = int(match.group(1))
            exp_item = int(match.group(2))
            errors = validate_series(content, expected_store=exp_store, expected_item=exp_item)
    else:
        errors = [f"Unrecognized JSON file in data directory: {rel_path}"]

    return (len(errors) == 0), errors


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for JSON schema validation."""
    parser = argparse.ArgumentParser(
        description="Day-0 validation script for DemandLens JSON data files."
    )
    parser.add_argument(
        "data_dir",
        nargs="?",
        type=Path,
        default=None,
        help="Path to data directory containing JSON files (default: public/data relative to repo root)",
    )
    parser.add_argument(
        "--data-dir",
        dest="data_dir_flag",
        type=Path,
        default=None,
        help="Alternative flag for path to data directory",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Require all 250 series files, manifest.json, portfolio.json, restock_inputs.json, and eda.json to exist",
    )
    args = parser.parse_args(argv)

    raw_path = args.data_dir_flag or args.data_dir
    if raw_path is None:
        # Default: public/data relative to repo root (pipeline/src/validate_json.py -> 2 levels up to repo root)
        repo_root = Path(__file__).resolve().parents[2]
        data_dir = repo_root / "public" / "data"
    else:
        data_dir = Path(raw_path).resolve()

    if not data_dir.exists():
        print(f"[FAIL] Data path does not exist: {data_dir}")
        print("\nSummary: 0 files checked, 0 passed, 1 failed")
        return 1

    # If single file passed
    if data_dir.is_file():
        file_path = data_dir
        base_dir = file_path.parent
        if base_dir.name == "series":
            base_dir = base_dir.parent
        passed, errors = validate_file(file_path, base_dir)
        rel_name = file_path.relative_to(base_dir).as_posix()
        if passed:
            print(f"[PASS] {rel_name}")
            print("\nSummary: 1 file checked, 1 passed, 0 failed")
            return 0
        else:
            print(f"[FAIL] {rel_name}: {'; '.join(errors)}")
            print("\nSummary: 1 file checked, 0 passed, 1 failed")
            return 1

    if args.require_all:
        expected_files = [
            data_dir / "manifest.json",
            data_dir / "eda.json",
            data_dir / "portfolio.json",
        ]
        if (data_dir / "restock_inputs.json").exists():
            expected_files.append(data_dir / "restock_inputs.json")
        elif (data_dir / "restock.json").exists():
            expected_files.append(data_dir / "restock.json")
        else:
            expected_files.append(data_dir / "restock_inputs.json")

        for s in range(1, 6):
            for i in range(1, 51):
                expected_files.append(data_dir / "series" / f"S{s}_I{i}.json")
        files_to_check = expected_files
    else:
        files_to_check = sorted(data_dir.rglob("*.json"))

    if not files_to_check:
        print(f"[FAIL] No JSON files found in {data_dir}")
        print("\nSummary: 0 files checked, 0 passed, 1 failed")
        return 1

    passed_count = 0
    failed_count = 0

    for file_path in files_to_check:
        try:
            rel_name = file_path.relative_to(data_dir).as_posix()
        except ValueError:
            rel_name = file_path.name

        passed, errors = validate_file(file_path, data_dir)
        if passed:
            print(f"[PASS] {rel_name}")
            passed_count += 1
        else:
            print(f"[FAIL] {rel_name}: {'; '.join(errors)}")
            failed_count += 1

    total_count = passed_count + failed_count
    print(f"\nSummary: {total_count} files checked, {passed_count} passed, {failed_count} failed")
    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
