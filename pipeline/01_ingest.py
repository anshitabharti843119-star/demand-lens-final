"""
01_ingest.py
Read train.csv, filter stores 1-5, validate, save parquet.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).parent / "data" / "raw" / "train.csv"
PROCESSED = Path(__file__).parent / "data" / "processed"

STORES = list(range(1, 6))   # 1..5
ITEMS  = list(range(1, 51))  # 1..50

TRAIN_START = "2013-01-01"
TRAIN_END   = "2017-11-30"
TEST_START  = "2017-12-01"
TEST_END    = "2017-12-31"


def ingest() -> pd.DataFrame:
    print("[01_ingest] Reading train.csv …")
    df = pd.read_csv(RAW, parse_dates=["date"])

    # ---------- filter -------------------------------------------------
    df = df[df["store"].isin(STORES) & df["item"].isin(ITEMS)].copy()
    df = df.sort_values(["store", "item", "date"]).reset_index(drop=True)

    # ---------- validate -----------------------------------------------
    assert df["sales"].notna().all(), "NaN sales"
    assert (df["sales"] >= 0).all(), "Negative sales"
    dups = df.duplicated(subset=["date", "store", "item"])
    assert not dups.any(), f"{dups.sum()} duplicate (date,store,item) rows"

    expected_rows = len(STORES) * len(ITEMS) * pd.date_range(TRAIN_START, TEST_END).size
    assert len(df) == expected_rows, (
        f"Expected {expected_rows} rows, got {len(df)}"
    )

    print(f"[01_ingest] OK — {len(df):,} rows, "
          f"{df['store'].nunique()} stores, {df['item'].nunique()} items")

    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / "filtered.parquet"
    df.to_parquet(out, index=False)
    print(f"[01_ingest] Saved → {out}")
    return df


if __name__ == "__main__":
    ingest()
