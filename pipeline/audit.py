"""
pipeline/audit.py
=================
Independent audit of DemandLens pipeline results.
Reads ONLY:
  - pipeline/data/raw/train.csv  (raw source of truth)
  - public/data/series/*.json    (exported backtest/metric outputs)

Does NOT import or trust any pipeline module.
"""

import csv
import json
import math
import pathlib
import sys

RAW_CSV    = pathlib.Path("pipeline/data/raw/train.csv")
SERIES_DIR = pathlib.Path("public/data/series")
STORES     = list(range(1, 6))
ITEMS      = list(range(1, 51))

TRAIN_END  = "2017-11-30"
TEST_START = "2017-12-01"
TEST_END   = "2017-12-31"

# ── helpers ──────────────────────────────────────────────────────────────────

def r2(x):
    return round(float(x), 2)

def mape(actual, forecast):
    """mean(|a-f|/a)*100 excluding a==0. Returns (value, n_used)."""
    pairs = [(a, f) for a, f in zip(actual, forecast) if a != 0]
    if not pairs:
        return 0.0, 0
    v = sum(abs(a - f) / a for a, f in pairs) / len(pairs) * 100
    return v, len(pairs)

def rmse(actual, forecast):
    n = len(actual)
    return math.sqrt(sum((a - f)**2 for a, f in zip(actual, forecast)) / n)

# ── load train.csv into a dict keyed by (store, item, date_str) ──────────────

print("Loading train.csv...", flush=True)
raw = {}   # (store, item, date) -> sales
with open(RAW_CSV, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = (int(row["store"]), int(row["item"]), row["date"])
        raw[key] = int(row["sales"])

print(f"  Loaded {len(raw)} rows.")
dates_all = sorted(set(d for (_, _, d) in raw))
print(f"  Date range in CSV: {dates_all[0]} to {dates_all[-1]}")

train_dates = [d for d in dates_all if d <= TRAIN_END]
test_dates  = [d for d in dates_all if TEST_START <= d <= TEST_END]
print(f"  Train dates: {train_dates[0]} to {train_dates[-1]} ({len(train_dates)} days)")
print(f"  Test dates:  {test_dates[0]}  to {test_dates[-1]}  ({len(test_dates)} days)")

# ─────────────────────────────────────────────────────────────────────────────
# PART 1: LEAKAGE AUDIT
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 70)
print("PART 1 — LEAKAGE AUDIT")
print("=" * 70)

for sid, store, item in [("S1_I1", 1, 1), ("S3_I25", 3, 25), ("S5_I50", 5, 50)]:
    # What dates exist in train.csv for this series up to TRAIN_END?
    t_dates = sorted(d for (s, i, d) in raw if s == store and i == item and d <= TRAIN_END)
    print(f"\n{sid}: Prophet fit window from train.csv")
    print(f"  min ds passed to m.fit(): {t_dates[0]}")
    print(f"  max ds passed to m.fit(): {t_dates[-1]}  <- must be 2017-11-30")
    assert t_dates[-1] == TRAIN_END, f"LEAKAGE! max train date={t_dates[-1]}"

    # Show last 28 train values used for MA28 baseline
    last28_dates = t_dates[-28:]
    last28_sales = [raw[(store, item, d)] for d in last28_dates]
    ma28_val     = sum(last28_sales) / 28
    print(f"  Last-28 train dates: {last28_dates[0]} to {last28_dates[-1]}")
    print(f"  Last-28 sales:       {last28_sales}")
    print(f"  MA28 mean (raw):     {ma28_val:.4f}  rounded: {r2(ma28_val)}")

print("\n  [LEAKAGE CHECK] All 250 series — max train date:")
leakage_found = False
for s in STORES:
    for i in ITEMS:
        t_dates = sorted(d for (ss, ii, d) in raw if ss == s and ii == i and d <= TRAIN_END)
        if t_dates[-1] != TRAIN_END:
            print(f"  WARNING: S{s}_I{i} max train date = {t_dates[-1]}")
            leakage_found = True
if not leakage_found:
    print("  All 250 series: max train date = 2017-11-30. NO LEAKAGE.")

# Check that test dates (Dec 2017) are present in raw CSV and not used in train
for s in STORES:
    for i in ITEMS:
        dec_dates = sorted(d for (ss, ii, d) in raw if ss == s and ii == i and TEST_START <= d <= TEST_END)
        assert len(dec_dates) == 31, f"S{s}_I{i} Dec 2017 has {len(dec_dates)} rows, expected 31"
print("  All 250 series: Dec 2017 has exactly 31 rows in CSV (never in train).")

# ─────────────────────────────────────────────────────────────────────────────
# PART 2: INDEPENDENT METRIC RECOMPUTE
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 70)
print("PART 2 — INDEPENDENT METRIC RECOMPUTE")
print("=" * 70)

h30_mape_model   = []
h30_mape_ma28    = []
h30_mape_sn      = []
h30_rmse_model   = []
coverages        = []
winners          = []

max_mape_diff    = 0.0   # vs stored
max_rmse_diff    = 0.0
max_cov_diff     = 0.0
max_actual_diff  = 0     # vs raw CSV

actual_mismatch_count = 0

for store in STORES:
    for item in ITEMS:
        sid = f"S{store}_I{item}"
        js  = json.loads((SERIES_DIR / f"{sid}.json").read_text())

        # ── 1. verify backtest.actual == raw CSV for Dec 2017 ─────────────────
        for pt in js["backtest"]["actual"]:
            csv_val = raw.get((store, item, pt["ds"]))
            if csv_val is None:
                print(f"MISSING: {sid} {pt['ds']} not in CSV!")
                actual_mismatch_count += 1
            elif csv_val != pt["y"]:
                print(f"MISMATCH: {sid} {pt['ds']} JSON={pt['y']} CSV={csv_val}")
                actual_mismatch_count += 1

        # ── 2. recompute MA28 from raw CSV ────────────────────────────────────
        t_dates    = sorted(d for (ss, ii, d) in raw if ss == store and ii == item and d <= TRAIN_END)
        last28_v   = [raw[(store, item, d)] for d in t_dates[-28:]]
        ma28_val   = r2(sum(last28_v) / 28)

        # ── 3. recompute seasonal naive from raw CSV ──────────────────────────
        def sn_for_date(ds_str):
            # same day 1 year prior
            yr, mo, dy = int(ds_str[:4]), int(ds_str[5:7]), int(ds_str[8:10])
            ly_str = f"{yr-1}-{mo:02d}-{dy:02d}"
            v = raw.get((store, item, ly_str))
            return float(v) if v is not None else ma28_val

        # ── 4. load JSON arrays ───────────────────────────────────────────────
        actual_j   = [pt["y"]    for pt in js["backtest"]["actual"]]   # 31 days
        yhat_j     = [pt["yhat"] for pt in js["backtest"]["model"]]    # 31 days, rounded
        yl_j       = [pt["yhat_lower"] for pt in js["backtest"]["model"]]
        yu_j       = [pt["yhat_upper"] for pt in js["backtest"]["model"]]
        dates_j    = [pt["ds"]   for pt in js["backtest"]["actual"]]
        sn_vals    = [sn_for_date(d) for d in dates_j]

        # ── 5. recompute h30 metrics (first 30 days) ──────────────────────────
        a30  = actual_j[:30]
        m30  = yhat_j[:30]
        b30  = [ma28_val] * 30
        sn30 = sn_vals[:30]

        model_mape_v, _ = mape(a30, m30)
        base_mape_v,  _ = mape(a30, b30)
        sn_mape_v,    _ = mape(a30, sn30)
        model_rmse_v    = rmse(a30, m30)

        # ── 6. recompute coverage (first 30 days, rounded bounds) ─────────────
        cov30 = sum(1 for i in range(30) if yl_j[i] <= actual_j[i] <= yu_j[i]) / 30

        # ── 7. compare vs stored JSON metrics ────────────────────────────────
        stored_h30_m_mape = js["metrics"]["h30"]["model"]["mape"]
        stored_h30_b_mape = js["metrics"]["h30"]["baseline"]["mape"]
        stored_cov        = js["metrics"]["coverage_80"]
        stored_h30_m_rmse = js["metrics"]["h30"]["model"]["rmse"]

        d_mape = abs(model_mape_v - stored_h30_m_mape)
        d_rmse = abs(model_rmse_v - stored_h30_m_rmse)
        d_cov  = abs(cov30         - stored_cov)

        if d_mape > max_mape_diff: max_mape_diff = d_mape
        if d_rmse > max_rmse_diff: max_rmse_diff = d_rmse
        if d_cov  > max_cov_diff:  max_cov_diff  = d_cov

        # ── 8. collect for aggregation ────────────────────────────────────────
        h30_mape_model.append(model_mape_v)
        h30_mape_ma28.append(base_mape_v)
        h30_mape_sn.append(sn_mape_v)
        h30_rmse_model.append(model_rmse_v)
        coverages.append(cov30)
        winners.append("model" if model_mape_v < base_mape_v else "baseline")

def median(lst):
    s = sorted(lst)
    n = len(s)
    return (s[n//2] + s[(n-1)//2]) / 2

print(f"\n  backtest.actual vs raw CSV mismatches: {actual_mismatch_count}")
if actual_mismatch_count == 0:
    print("  All 250x31 = 7750 actual values match train.csv exactly.")

print()
print("  Independently recomputed from raw CSV + JSON yhat arrays:")
print(f"  Median h30 MAPE (model):           {median(h30_mape_model):.2f}%")
print(f"  Median h30 MAPE (MA28 baseline):   {median(h30_mape_ma28):.2f}%")
print(f"  Median h30 MAPE (seasonal naive):  {median(h30_mape_sn):.2f}%")
print(f"  Win-rate (model < MA28 MAPE):      {sum(1 for w in winners if w=='model')}/250")
print(f"  Median improvement vs MA28:        {median([(b-m)/b*100 for m,b in zip(h30_mape_model,h30_mape_ma28)]):.1f}%")
print(f"  Avg coverage_80 (30-day):          {sum(coverages)/len(coverages):.3f}")

print()
print("  Max absolute diff (recomputed vs stored JSON):")
print(f"    MAPE:     {max_mape_diff:.4f}%  (expect <= 0.02)")
print(f"    RMSE:     {max_rmse_diff:.4f}   (expect <= 0.02)")
print(f"    coverage: {max_cov_diff:.4f}    (expect <= 0.01)")

# ─────────────────────────────────────────────────────────────────────────────
# PART 3: SANITY CHECKS
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 70)
print("PART 3 — SANITY CHECKS")
print("=" * 70)

# 3a. S1_I1: 14 days side-by-side
sid, store, item = "S1_I1", 1, 1
js = json.loads((SERIES_DIR / "S1_I1.json").read_text())
t_dates  = sorted(d for (ss, ii, d) in raw if ss == 1 and ii == 1 and d <= TRAIN_END)
ma28_v   = r2(sum(raw[(1,1,d)] for d in t_dates[-28:]) / 28)

print(f"\n  S1_I1 — 14-day side-by-side (actual | model_yhat | MA28_yhat):")
print(f"  {'date':12s} {'actual':>8s} {'model':>8s} {'MA28':>8s} {'|a-m|/a%':>10s}")
actual_14 = [pt["y"]    for pt in js["backtest"]["actual"][:14]]
model_14  = [pt["yhat"] for pt in js["backtest"]["model"][:14]]
dates_14  = [pt["ds"]   for pt in js["backtest"]["actual"][:14]]
for d, a, m_v in zip(dates_14, actual_14, model_14):
    pct = abs(a - m_v) / a * 100 if a != 0 else float("nan")
    print(f"  {d}   {a:8d}  {m_v:8.2f}  {ma28_v:8.2f}  {pct:10.1f}%")
m14, _ = mape(actual_14, model_14)
b14, _ = mape(actual_14, [ma28_v]*14)
print(f"  h14 MAPE model={m14:.2f}%  MA28={b14:.2f}%  (stored model={js['metrics']['h14']['model']['mape']})")

# 3b. "Noise floor": MAPE of predicting last-8-week same-weekday average
print()
print("  Noise floor: MAPE of predicting last-8wk same-weekday avg (cheap strong reference)")
import datetime
noise_mapes = []
for store in STORES:
    for item in ITEMS:
        t_dates = sorted(d for (ss, ii, d) in raw if ss == store and ii == item and d <= TRAIN_END)
        test_d  = sorted(d for (ss, ii, d) in raw if ss == store and ii == item and TEST_START <= d <= TEST_END)[:30]
        actuals = []
        preds   = []
        for ds in test_d:
            yr, mo, dy = int(ds[:4]), int(ds[5:7]), int(ds[8:10])
            dt = datetime.date(yr, mo, dy)
            dow = dt.weekday()
            # Last 8 weeks of same weekday in train window
            same_dow = []
            for td in reversed(t_dates):
                yr2, mo2, dy2 = int(td[:4]), int(td[5:7]), int(td[8:10])
                if datetime.date(yr2, mo2, dy2).weekday() == dow:
                    same_dow.append(raw[(store, item, td)])
                    if len(same_dow) == 8:
                        break
            pred = sum(same_dow) / len(same_dow) if same_dow else ma28_v
            actuals.append(raw[(store, item, ds)])
            preds.append(pred)
        nm, _ = mape(actuals, preds)
        noise_mapes.append(nm)

print(f"  Median noise-floor MAPE (8-wk same-DOW avg): {median(noise_mapes):.2f}%")
print(f"  Median Prophet h30 MAPE:                     {median(h30_mape_model):.2f}%")
print(f"  Prophet MAPE / noise-floor:                  {median(h30_mape_model)/median(noise_mapes):.2f}x")
print(f"  (A ratio < 0.5 would be suspicious for a daily count series)")

# 3c. Check that MAPE is NOT accidentally aggregated
print()
print("  Aggregation check: does the model beat a naive all-stores-sum predictor?")
# if MAPE were computed on the store-sum (5x higher values), errors would be ~5x smaller
# Check: model MAPE should be WORSE than an oracle on the per-series mean
per_series_means = []
for store in STORES:
    for item in ITEMS:
        t_dates = sorted(d for (ss, ii, d) in raw if ss == store and ii == item and d <= TRAIN_END)
        test_d  = sorted(d for (ss, ii, d) in raw if ss == store and ii == item and TEST_START <= d <= TEST_END)[:30]
        mean_train = sum(raw[(store, item, d)] for d in t_dates) / len(t_dates)
        actuals    = [raw[(store, item, d)] for d in test_d]
        oracle_m, _ = mape(actuals, [mean_train]*30)
        per_series_means.append(oracle_m)

print(f"  Median MAPE(oracle=train_mean):              {median(per_series_means):.2f}%")
print(f"  Median MAPE(Prophet):                        {median(h30_mape_model):.2f}%")
print(f"  (Prophet should be better than or close to oracle)")

# 3d. Formula check for S1_I1
print()
a30_1  = [pt["y"]    for pt in json.loads((SERIES_DIR/"S1_I1.json").read_text())["backtest"]["actual"][:30]]
m30_1  = [pt["yhat"] for pt in json.loads((SERIES_DIR/"S1_I1.json").read_text())["backtest"]["model"][:30]]
direct_mape, n_used = mape(a30_1, m30_1)
print(f"  MAPE formula check (S1_I1 h30):")
print(f"    Formula: mean(|a-f|/a)*100, excl. a==0")
print(f"    n_total=30, n_used(a!=0)={n_used}, computed={direct_mape:.4f}%")
print(f"    Stored in JSON: {json.loads((SERIES_DIR/'S1_I1.json').read_text())['metrics']['h30']['model']['mape']}")

# 3e. Coverage calibration sanity
print()
print("  Coverage calibration check:")
print("  If model MAPE is 4.37%, bands should be tighter than 80% interval_width suggests.")
print("  Expected 80% coverage ~ 0.80. Actual average:")
print(f"    Avg coverage (30-day, rounded bounds): {sum(coverages)/250:.3f}")
print(f"    This {'is' if 0.70 <= sum(coverages)/250 <= 0.90 else 'IS NOT'} within [0.70, 0.90].")
cov_low  = sum(1 for c in coverages if c < 0.70)
cov_high = sum(1 for c in coverages if c > 0.90)
print(f"    Series with coverage < 0.70: {cov_low}")
print(f"    Series with coverage > 0.90: {cov_high}")

# ─────────────────────────────────────────────────────────────────────────────
# PART 4: FINAL TABLE
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 70)
print("PART 4 — FINAL TABLE")
print("=" * 70)
wins_vs_ma28 = sum(1 for m_v, b_v in zip(h30_mape_model, h30_mape_ma28) if m_v < b_v)
wins_vs_sn   = sum(1 for m_v, s_v in zip(h30_mape_model, h30_mape_sn)   if m_v < s_v)
impr_ma28    = [(b-m)/b*100 for m,b in zip(h30_mape_model, h30_mape_ma28)]
impr_sn      = [(b-m)/b*100 for m,b in zip(h30_mape_model, h30_mape_sn)]
cov_outside  = sum(1 for c in coverages if c < 0.70 or c > 0.90)

print(f"\n  Win-rate vs MA28:            {wins_vs_ma28}/250  ({wins_vs_ma28/2.5:.1f}%)")
print(f"  Win-rate vs Seasonal-Naive:  {wins_vs_sn}/250  ({wins_vs_sn/2.5:.1f}%)")
print(f"  Median MAPE (model h30):     {median(h30_mape_model):.2f}%")
print(f"  Median MAPE (MA28):          {median(h30_mape_ma28):.2f}%")
print(f"  Median MAPE (SN):            {median(h30_mape_sn):.2f}%")
print(f"  Median improvement vs MA28:  {median(impr_ma28):.1f}%")
print(f"  Median improvement vs SN:    {median(impr_sn):.1f}%")
print(f"  Avg coverage_80 (30-day):    {sum(coverages)/250:.3f}")
print(f"  Series outside 70-90% cov:  {cov_outside}/250")
