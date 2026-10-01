"""
pipeline.py  —  DemandLens offline pipeline orchestrator
Usage:  python pipeline/pipeline.py
   or:  cd pipeline && python pipeline.py
"""
import sys
import time
import importlib.util
import warnings
import logging
from pathlib import Path

warnings.filterwarnings("ignore")
logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))


def _load(filename: str):
    """Load a module from a numeric-prefixed .py file."""
    spec = importlib.util.spec_from_file_location(filename, HERE / filename)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


import numpy as np


def main():
    t0 = time.time()
    print("=" * 60)
    print("  DemandLens Pipeline")
    print("=" * 60)

    ingest_mod  = _load("01_ingest.py")
    eda_mod     = _load("02_eda.py")
    bt_mod      = _load("03_train_backtest.py")
    future_mod  = _load("04_future.py")
    export_mod  = _load("05_export.py")

    import pandas as pd
    PROCESSED = HERE / "data" / "processed"

    # ── Step 1: Ingest ────────────────────────────────────────────
    df = ingest_mod.ingest()

    # ── Step 2: EDA ───────────────────────────────────────────────
    eda_mod.compute_eda(df)

    # ── Step 3: Train + Backtest ───────────────────────────────────
    results = bt_mod.run_backtest(df)

    # ── Step 4: Future forecast ────────────────────────────────────
    results = future_mod.run_future(df, results)

    # ── Step 5: Export ─────────────────────────────────────────────
    export_mod.export_all(results)

    # ── Summary ───────────────────────────────────────────────────
    elapsed = time.time() - t0
    wins  = sum(1 for r in results if r["metrics"]["winner"] == "model")
    total = len(results)

    improvements = [
        (r["metrics"]["h30"]["baseline"]["mape"] - r["metrics"]["h30"]["model"]["mape"])
        / r["metrics"]["h30"]["baseline"]["mape"] * 100
        for r in results
    ]
    coverages      = [r["metrics"]["coverage_80"] for r in results]
    model_mapes    = [r["metrics"]["h30"]["model"]["mape"]    for r in results]
    baseline_mapes = [r["metrics"]["h30"]["baseline"]["mape"] for r in results]

    print()
    print("=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Time elapsed       : {elapsed/60:.1f} min")
    print(f"  Series processed   : {total}")
    print(f"  Model wins         : {wins}/{total}  ({wins/total*100:.1f}%)")
    print(f"  Baseline wins      : {total-wins}/{total}  ({(total-wins)/total*100:.1f}%)")
    print(f"  Median MAPE (model): {np.median(model_mapes):.2f}%")
    print(f"  Median MAPE (base) : {np.median(baseline_mapes):.2f}%")
    print(f"  Median improvement : {np.median(improvements):.1f}%")
    print(f"  Median coverage_80 : {np.median(coverages):.3f}")
    print(f"  Min  coverage_80   : {np.min(coverages):.3f}")
    print(f"  Max  coverage_80   : {np.max(coverages):.3f}")
    print("=" * 60)
    print("  public/data/ is ready.")
    print("=" * 60)


if __name__ == "__main__":
    main()
