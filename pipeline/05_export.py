"""
05_export.py
Export all 250 series JSON + manifest.json + restock.json to public/data/
"""
import json
import random
from pathlib import Path

import numpy as np

PUBLIC_DIR = Path(__file__).parent.parent / "public" / "data"
SERIES_DIR = PUBLIC_DIR / "series"

STORES = list(range(1, 6))
ITEMS  = list(range(1, 51))


def _round2(x: float) -> float:
    return round(float(x), 2)


def export_all(results: list[dict]) -> dict[str, dict]:
    """
    Write:
      public/data/manifest.json
      public/data/series/S{s}_I{i}.json  (250 files)
      public/data/restock.json
    Returns restock_inputs dict.
    """
    SERIES_DIR.mkdir(parents=True, exist_ok=True)

    # ── manifest ─────────────────────────────────────────────────────────────
    manifest = {
        "stores": STORES,
        "items": ITEMS,
        "series_ids": [f"S{s}_I{i}" for s in STORES for i in ITEMS],
        "train_end":   "2017-11-30",
        "test_start":  "2017-12-01",
        "test_end":    "2017-12-31",
        "future_end":  "2018-01-30",
    }
    with open(PUBLIC_DIR / "manifest.json", "w") as f:
        json.dump(manifest, f, separators=(",", ":"))
    print(f"[05_export] manifest.json written ({len(manifest['series_ids'])} series)")

    # ── per-series JSON ───────────────────────────────────────────────────────
    restock_inputs = {}

    for r in results:
        sid = r["series_id"]
        store = r["store"]
        item  = r["item"]

        series_doc = {
            "schema_version": 1,
            "series_id": sid,
            "store": store,
            "item": item,
            "history": r["history"],
            "backtest": r["backtest"],
            "future": r["future"],
            "metrics": r["metrics"],
        }

        out_path = SERIES_DIR / f"{sid}.json"
        with open(out_path, "w") as f:
            json.dump(series_doc, f, separators=(",", ":"))

        # ── restock input ─────────────────────────────────────────────────────
        # Use last 28 actual (backtest) values
        actual_vals = [pt["y"] for pt in r["backtest"]["actual"]]
        last28 = actual_vals[-28:]
        avg_daily_28 = _round2(float(np.mean(last28)))
        sigma_daily  = _round2(float(np.std(last28, ddof=1))) if len(last28) > 1 else 0.0

        # Seeded current_stock (matches mock logic: 0.4 to 42× daily mean)
        rng = random.Random(f"{sid}:inventory")
        multiplier = 0.4 + rng.random() * 41.6  # 0.4 + random() * (42 - 0.4)
        current_stock = max(0, round(avg_daily_28 * multiplier))

        yhat_future = [pt["yhat"] for pt in r["future"]["model"]]

        restock_inputs[sid] = {
            "store": store,
            "item": item,
            "current_stock": current_stock,
            "avg_daily_28": avg_daily_28,
            "sigma_daily": sigma_daily,
            "yhat_future": yhat_future,
        }

    with open(PUBLIC_DIR / "restock.json", "w") as f:
        json.dump(restock_inputs, f, separators=(",", ":"))
    print(f"[05_export] restock.json written ({len(restock_inputs)} entries)")

    with open(PUBLIC_DIR / "restock_inputs.json", "w") as f:
        json.dump(restock_inputs, f, separators=(",", ":"))
    print(f"[05_export] restock_inputs.json written ({len(restock_inputs)} entries)")

    print(f"[05_export] series/ written ({len(results)} files)")

    return restock_inputs


if __name__ == "__main__":
    print("Run via pipeline.py")
