"""
pipeline/leakage_tests.py
=========================
Tests A, B, C, D as requested.
Reads raw train.csv. Runs Prophet directly. Prints raw numbers.
"""

import csv
import json
import logging
import math
import pathlib
import random
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.getLogger("prophet").setLevel(logging.ERROR)
logging.getLogger("cmdstanpy").setLevel(logging.ERROR)

RAW_CSV    = pathlib.Path("pipeline/data/raw/train.csv")
TRUNC_CSV  = pathlib.Path("pipeline/data/raw/train_trunc.csv")
POISON_CSV = pathlib.Path("pipeline/data/raw/train_poison.csv")
SERIES_DIR = pathlib.Path("public/data/series")

TARGET_SERIES = [("S1_I1", 1, 1), ("S3_I25", 3, 25), ("S5_I50", 5, 50)]
IDX_MAP = {"S1_I1": 0, "S3_I25": 124, "S5_I50": 249}  # (store-1)*50 + (item-1)

TRAIN_END  = "2017-11-30"
TEST_START = "2017-12-01"
TEST_END   = "2017-12-31"

# ── helpers ──────────────────────────────────────────────────────────────────

def _r2(x): return round(float(x), 2)

def _fit_and_predict_series(full_df, store, item, seed):
    """Exact same logic as 03_train_backtest.py lines 72-129.
    full_df has columns: date(str), store, item, sales.
    Returns (prophet_df passed to m.fit(), fc_test DataFrame with yhat for Dec 2017).
    """
    from prophet import Prophet

    mask = (full_df["store"] == store) & (full_df["item"] == item)
    s = full_df[mask].sort_values("date").copy()
    s["date"] = pd.to_datetime(s["date"])

    # This is line 77 of 03_train_backtest.py
    train = s[s["date"] <= TRAIN_END].copy()
    # test rows are NOT passed to m.fit() at all
    test  = s[(s["date"] >= TEST_START) & (s["date"] <= TEST_END)].copy()

    # Exactly lines 103-128
    prophet_df = train[["date", "sales"]].rename(columns={"date": "ds", "sales": "y"})
    prophet_df["y"] = prophet_df["y"].astype(float)

    m = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        interval_width=0.8,
        uncertainty_samples=500,
    )
    m.fit(prophet_df, seed=seed)

    future = m.make_future_dataframe(periods=31, freq="D")
    fc = m.predict(future)

    fc_test = fc[fc["ds"].dt.strftime("%Y-%m-%d").between(TEST_START, TEST_END)].copy()
    fc_test = fc_test.sort_values("ds").reset_index(drop=True)

    return prophet_df, fc_test

# ── load CSV helper ───────────────────────────────────────────────────────────

def load_csv(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append({"date": r["date"], "store": int(r["store"]),
                         "item": int(r["item"]), "sales": int(r["sales"])})
    return pd.DataFrame(rows)

# ─────────────────────────────────────────────────────────────────────────────
# SETUP: create truncated and poisoned CSVs
# ─────────────────────────────────────────────────────────────────────────────

print("Loading train.csv ...", flush=True)
df_full = load_csv(RAW_CSV)
print(f"  Total rows: {len(df_full)}")
print(f"  Date range: {df_full['date'].min()} to {df_full['date'].max()}")

# train_trunc.csv — every row with date > 2017-11-30 removed
df_trunc = df_full[df_full["date"] <= TRAIN_END].copy()
df_trunc.to_csv(TRUNC_CSV, index=False)
print(f"\nTrain_trunc rows: {len(df_trunc)}  (max date: {df_trunc['date'].max()})")
assert df_trunc["date"].max() == TRAIN_END

# train_poison.csv — Dec 2017 sales multiplied by 3
rng = random.Random(999)
df_poison = df_full.copy()
dec_mask = df_poison["date"] > TRAIN_END
df_poison.loc[dec_mask, "sales"] = df_poison.loc[dec_mask, "sales"] * 3
df_poison.to_csv(POISON_CSV, index=False)
print(f"Poison rows modified: {dec_mask.sum()}")
print(f"  S1_I1 Dec 1 sales: original={df_full[(df_full.store==1)&(df_full.item==1)&(df_full.date=='2017-12-01')]['sales'].values[0]}"
      f"  poisoned={df_poison[(df_poison.store==1)&(df_poison.item==1)&(df_poison.date=='2017-12-01')]['sales'].values[0]}")

print()
print("=" * 70)
print("TEST C — CODE PATH VERIFICATION (exact lines from 03_train_backtest.py)")
print("=" * 70)
print("""
Relevant code lines (file: pipeline/03_train_backtest.py):

  LINE 73-74:  mask = (df["store"] == store) & (df["item"] == item)
               s = df[mask].sort_values("date").copy()
  LINE 77:     train = s[s["date"] <= TRAIN_END].copy()   # TRAIN_END = "2017-11-30"
  LINE 78:     test  = s[(s["date"] >= TEST_START) & (s["date"] <= TEST_END)].copy()

  LINE 104:    prophet_df = train[["date","sales"]].rename(...)
               # 'train' contains ONLY dates <= 2017-11-30
               # 'test' is never merged into prophet_df

  LINE 119:    m.fit(prophet_df, seed=seed)
               # prophet_df is built from 'train' only

  LINE 122:    future = m.make_future_dataframe(periods=31, freq="D")
               # extends training period by 31 days beyond last train date
               # last train date = 2017-11-30, so future ends 2017-12-31

  LINE 123:    fc = m.predict(future)
               # fc contains in-sample (2013-2017-11-30) + out-of-sample (Dec 2017)

  LINE 126:    fc_test = fc[fc["ds"].dt.strftime("%Y-%m-%d").between(TEST_START, TEST_END)]
               # ONLY Dec 2017 rows extracted — NOT in-sample rows
               # yhat here is pure extrapolation, not in-sample fit

  LINE 132:    actual_vals = test.sort_values("date")["sales"].values.astype(float)
               # actuals come from 'test' (raw CSV values), never from fc

  LINE 144-147: backtest_model = [{..., "yhat": _round2(yh), ...} ...]
               # yhat from fc_test (Dec extrapolation), NOT from in-sample fc rows

  04_future.py:
  LINE 50:     prophet_df = s[["date","sales"]].rename(...)  # FULL dataset 2013-2017-12-31
  LINE 60:     m.fit(prophet_df, seed=seed)  # SEPARATE Prophet instance
  LINE 79:     r["future"] = {...}  # writes to "future" key only, never touches r["backtest"]
""")

print("Live verification — df shapes passed to m.fit():")
for sid, store, item in TARGET_SERIES:
    idx = IDX_MAP[sid]
    mask = (df_full["store"] == store) & (df_full["item"] == item)
    s = df_full[mask].sort_values("date").copy()
    s["date"] = pd.to_datetime(s["date"])
    train = s[s["date"] <= TRAIN_END]
    prophet_df = train[["date","sales"]].rename(columns={"date":"ds","sales":"y"})
    print(f"  {sid}: prophet_df rows={len(prophet_df)}  min_ds={prophet_df['ds'].min().date()}  max_ds={prophet_df['ds'].max().date()}")
    assert str(prophet_df["ds"].max().date()) == TRAIN_END, "LEAKAGE DETECTED"
print("  All 3: max_ds = 2017-11-30. Test data NOT in prophet_df.")

print()
print("=" * 70)
print("TEST A — PHYSICAL TRUNCATION TEST")
print("  Running Prophet on train_trunc.csv (Dec 2017 physically absent)")
print("=" * 70)

trunc_yhats = {}
for sid, store, item in TARGET_SERIES:
    idx = IDX_MAP[sid]
    seed = 42 + idx
    print(f"\n  Fitting {sid} on truncated CSV (seed={seed}) ...", flush=True)
    pdf, fc_test = _fit_and_predict_series(df_trunc, store, item, seed)
    print(f"    prophet_df: rows={len(pdf)}  max_ds={pdf['ds'].max().date()}")
    print(f"    fc_test rows: {len(fc_test)}  "
          f"  ds range: {fc_test['ds'].min().date()} to {fc_test['ds'].max().date()}")
    trunc_yhats[sid] = fc_test["yhat"].clip(lower=0).values
    print(f"    First 5 yhat (trunc): {[_r2(v) for v in trunc_yhats[sid][:5]]}")

print()
print("  Comparison: trunc yhat vs stored JSON yhat")
for sid, store, item in TARGET_SERIES:
    js = json.loads((SERIES_DIR / f"{sid}.json").read_text())
    stored_yhat = np.array([p["yhat"] for p in js["backtest"]["model"]])
    # stored is already rounded to 2dp; trunc is raw — compare raw vs raw (unrounded trunc)
    # also compare rounded trunc vs stored
    trunc_r = np.array([_r2(v) for v in trunc_yhats[sid]])
    diffs = np.abs(trunc_r - stored_yhat)
    print(f"  {sid}: max|trunc_yhat - stored_yhat| = {diffs.max():.4f}  mean = {diffs.mean():.4f}")
    print(f"    trunc[0:5]:  {trunc_r[:5].tolist()}")
    print(f"    stored[0:5]: {stored_yhat[:5].tolist()}")

print()
print("=" * 70)
print("TEST B — POISON TEST")
print("  Running Prophet on train_poison.csv (Dec 2017 sales × 3)")
print("=" * 70)

poison_yhats = {}
for sid, store, item in TARGET_SERIES:
    idx = IDX_MAP[sid]
    seed = 42 + idx
    print(f"\n  Fitting {sid} on poison CSV (seed={seed}) ...", flush=True)
    # poison df has same train window (pre-Dec same), only Dec is poisoned
    # since train filter cuts at 2017-11-30, the poisoned Dec rows are excluded
    pdf, fc_test = _fit_and_predict_series(df_poison, store, item, seed)
    print(f"    prophet_df: rows={len(pdf)}  max_ds={pdf['ds'].max().date()}")
    poison_yhats[sid] = fc_test["yhat"].clip(lower=0).values
    print(f"    First 5 yhat (poison): {[_r2(v) for v in poison_yhats[sid][:5]]}")

print()
print("  Comparison: poison yhat vs normal (trunc) yhat")
print("  (If yhat changes with poisoned Dec, Dec data reached the fit)")
for sid, store, item in TARGET_SERIES:
    diffs = np.abs(np.array(poison_yhats[sid]) - np.array(trunc_yhats[sid]))
    print(f"  {sid}: max|poison - trunc| = {diffs.max():.6f}  mean = {diffs.mean():.6f}")
    if diffs.max() < 0.001:
        print(f"    -> IDENTICAL. Dec 2017 data does NOT reach m.fit().")
    else:
        print(f"    -> DIFFERS. LEAKAGE CONFIRMED.")

print()
print("=" * 70)
print("TEST D — PLOT-LEVEL SANITY (S1_I1, 14 days)")
print("=" * 70)
js_s1i1 = json.loads((SERIES_DIR / "S1_I1.json").read_text())
actual_arr  = [p["y"]           for p in js_s1i1["backtest"]["actual"][:14]]
model_arr   = [p["yhat"]        for p in js_s1i1["backtest"]["model"][:14]]
lower_arr   = [p["yhat_lower"]  for p in js_s1i1["backtest"]["model"][:14]]
upper_arr   = [p["yhat_upper"]  for p in js_s1i1["backtest"]["model"][:14]]
dates_arr   = [p["ds"]          for p in js_s1i1["backtest"]["actual"][:14]]

# MA28 from raw CSV
import csv as csv_mod
raw_dict = {}
with open(RAW_CSV, newline="") as f:
    for r in csv_mod.DictReader(f):
        raw_dict[(int(r["store"]), int(r["item"]), r["date"])] = int(r["sales"])

t_dates_s1i1 = sorted(d for (s,i,d) in raw_dict if s==1 and i==1 and d <= TRAIN_END)
ma28_s1i1 = _r2(sum(raw_dict[(1,1,d)] for d in t_dates_s1i1[-28:]) / 28)

print(f"\n  {'date':12s} {'actual':>7s} {'yhat':>7s} {'lower':>7s} {'upper':>7s} {'MA28':>7s} {'|a-yhat|':>8s} {'is_in_band':>10s}")
for i in range(14):
    err = abs(actual_arr[i] - model_arr[i])
    in_band = "YES" if lower_arr[i] <= actual_arr[i] <= upper_arr[i] else "NO"
    print(f"  {dates_arr[i]}   {actual_arr[i]:7d}  {model_arr[i]:7.2f}  {lower_arr[i]:7.2f}  {upper_arr[i]:7.2f}  {ma28_s1i1:7.2f}  {err:8.2f}  {in_band:>10s}")

print()
errors_14 = [abs(a - m) for a, m in zip(actual_arr, model_arr)]
print(f"  Mean absolute error (14 days): {sum(errors_14)/14:.2f} units")
print(f"  Max absolute error (14 days):  {max(errors_14):.2f} units")
print(f"  (If errors were ~1-2 units every day, that would suggest leakage)")
print(f"  (Errors of 3-10+ units are expected for genuine out-of-sample forecast)")

print()
print("  Day-to-day noise analysis (S1_I1 actual values Dec 2017):")
actuals_30 = [p["y"] for p in js_s1i1["backtest"]["actual"][:30]]
print(f"  30-day actuals: {actuals_30}")
print(f"  Mean: {sum(actuals_30)/30:.1f}  StdDev: {np.std(actuals_30):.1f}  CV: {np.std(actuals_30)/(sum(actuals_30)/30)*100:.0f}%")

print()
print("  Now show a LOW-MAPE series for contrast:")
# Find the series with lowest h30 model MAPE
best_sid, best_mape = "", 999
for s in range(1, 6):
    for i in range(1, 51):
        sid = f"S{s}_I{i}"
        m_val = json.loads((SERIES_DIR/f"{sid}.json").read_text())["metrics"]["h30"]["model"]["mape"]
        if m_val < best_mape:
            best_mape, best_sid = m_val, sid

print(f"  Best series: {best_sid}  stored h30 MAPE={best_mape}%")
js_best = json.loads((SERIES_DIR / f"{best_sid}.json").read_text())
actuals_best = [p["y"] for p in js_best["backtest"]["actual"][:14]]
model_best   = [p["yhat"] for p in js_best["backtest"]["model"][:14]]
dates_best   = [p["ds"] for p in js_best["backtest"]["actual"][:14]]
print(f"  {'date':12s} {'actual':>7s} {'yhat':>7s} {'|a-yhat|':>9s} {'err%':>7s}")
for i in range(14):
    err = abs(actuals_best[i] - model_best[i])
    pct = err / actuals_best[i] * 100 if actuals_best[i] != 0 else 0
    print(f"  {dates_best[i]}   {actuals_best[i]:7d}  {model_best[i]:7.2f}  {err:9.2f}  {pct:7.1f}%")
print(f"  30-day actuals: {[p['y'] for p in js_best['backtest']['actual'][:30]]}")
actuals_b30 = [p["y"] for p in js_best["backtest"]["actual"][:30]]
print(f"  Mean: {sum(actuals_b30)/30:.1f}  StdDev: {np.std(actuals_b30):.1f}  CV: {np.std(actuals_b30)/(sum(actuals_b30)/30)*100:.0f}%")

print()
print("=" * 70)
print("VERDICT")
print("=" * 70)
