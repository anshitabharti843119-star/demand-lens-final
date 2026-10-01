"""
pipeline/export_processed.py
Generate pipeline/data/processed/restock.csv and metrics.csv from public/data/
Uses the same default params as lib/restock-view.ts defaultRestockOptions:
  horizon=30, serviceLevel=0.95 (z=1.65), leadTime=3, stockMultiplier=1
"""
import csv, json, math, pathlib

DATA = pathlib.Path("public/data")
OUT  = pathlib.Path("pipeline/data/processed")
OUT.mkdir(parents=True, exist_ok=True)

HORIZON = 30
Z = 1.65        # serviceLevel=0.95
LEAD_TIME = 3
STOCK_MULT = 1  # stockMultiplier=1

restock = json.loads((DATA / "restock.json").read_text())

# ── restock.csv ──────────────────────────────────────────────────────────────
restock_rows = []
for sid, inp in restock.items():
    stock   = inp["current_stock"] * STOCK_MULT
    demand  = sum(inp["yhat_future"][:HORIZON])
    ss      = Z * inp["sigma_daily"] * math.sqrt(LEAD_TIME)
    qty     = max(0, math.ceil(demand + ss - stock))
    doc     = stock / (demand / HORIZON) if demand > 0 else float("inf")
    pri     = "HIGH" if doc < LEAD_TIME else ("MEDIUM" if doc < HORIZON else "LOW")
    restock_rows.append({
        "series_id": sid,
        "store": inp["store"],
        "item": inp["item"],
        "current_stock": round(stock, 2),
        "forecast_demand": round(demand, 2),
        "safety_stock": round(ss, 2),
        "restock_qty": qty,
        "days_of_cover": round(doc, 2) if math.isfinite(doc) else "inf",
        "priority": pri,
    })

restock_rows.sort(key=lambda r: (r["days_of_cover"] if isinstance(r["days_of_cover"], float) else 1e9, r["series_id"]))

with open(OUT / "restock.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(restock_rows[0].keys()))
    w.writeheader(); w.writerows(restock_rows)
print(f"restock.csv: {len(restock_rows)} rows")

# ── metrics.csv ───────────────────────────────────────────────────────────────
metrics_rows = []
for sid_path in sorted((DATA / "series").glob("S*.json")):
    s = json.loads(sid_path.read_text())
    m = s["metrics"]
    metrics_rows.append({
        "series_id": s["series_id"],
        "store": s["store"],
        "item": s["item"],
        "h14_model_mape":    m["h14"]["model"]["mape"],
        "h14_model_rmse":    m["h14"]["model"]["rmse"],
        "h14_baseline_mape": m["h14"]["baseline"]["mape"],
        "h14_baseline_rmse": m["h14"]["baseline"]["rmse"],
        "h30_model_mape":    m["h30"]["model"]["mape"],
        "h30_model_rmse":    m["h30"]["model"]["rmse"],
        "h30_baseline_mape": m["h30"]["baseline"]["mape"],
        "h30_baseline_rmse": m["h30"]["baseline"]["rmse"],
        "coverage_80":       m["coverage_80"],
        "winner":            m["winner"],
        "improvement_pct":   round((m["h30"]["baseline"]["mape"] - m["h30"]["model"]["mape"])
                                   / m["h30"]["baseline"]["mape"] * 100, 2)
                             if m["h30"]["baseline"]["mape"] > 0 else 0,
    })

with open(OUT / "metrics.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(metrics_rows[0].keys()))
    w.writeheader(); w.writerows(metrics_rows)
print(f"metrics.csv: {len(metrics_rows)} rows")
print("Done.")
