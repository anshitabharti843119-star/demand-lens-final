import os
import glob
import json
import shutil
import statistics

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 1.a Read ALL 250 series JSON files from public/data/series/S*_I*.json
    series_pattern = os.path.join(base_dir, "public", "data", "series", "S*_I*.json")
    series_files = glob.glob(series_pattern)
    print(f"Found {len(series_files)} series JSON files.")

    portfolio = []
    coverages = []

    for filepath in series_files:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        series_id = data["series_id"]
        store = data["store"]
        item = data["item"]
        metrics = data["metrics"]

        model_mape = metrics["h30"]["model"]["mape"]
        baseline_mape = metrics["h30"]["baseline"]["mape"]
        improvement_pct = round((baseline_mape - model_mape) / baseline_mape * 100, 2)
        winner = metrics["winner"]
        coverage_80 = metrics["coverage_80"]

        portfolio.append({
            "series_id": series_id,
            "store": store,
            "item": item,
            "model_mape": model_mape,
            "baseline_mape": baseline_mape,
            "improvement_pct": improvement_pct,
            "winner": winner
        })
        coverages.append(coverage_80)

    # Sort by series_id
    portfolio.sort(key=lambda x: x["series_id"])

    # 1.b Create public/data/portfolio.json
    portfolio_path = os.path.join(base_dir, "public", "data", "portfolio.json")
    with open(portfolio_path, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, indent=2)
    print(f"Created {portfolio_path} with {len(portfolio)} entries.")

    # 1.c Rename public/data/restock.json to public/data/restock_inputs.json
    restock_path = os.path.join(base_dir, "public", "data", "restock.json")
    restock_inputs_path = os.path.join(base_dir, "public", "data", "restock_inputs.json")
    if os.path.exists(restock_path):
        if os.path.exists(restock_inputs_path):
            os.remove(restock_inputs_path)
        shutil.move(restock_path, restock_inputs_path)
        print(f"Renamed {restock_path} -> {restock_inputs_path}")
    elif os.path.exists(restock_inputs_path):
        print(f"{restock_inputs_path} already exists; {restock_path} not present.")
    else:
        print(f"Warning: Neither {restock_path} nor {restock_inputs_path} found.")

    # 1.d Print summary: win-rate (% of model wins), median MAPE improvement %, average coverage_80 across all 250 series
    total = len(portfolio)
    model_wins = sum(1 for r in portfolio if r["winner"] == "model")
    win_rate = (model_wins / total * 100) if total > 0 else 0.0
    median_improvement = statistics.median([r["improvement_pct"] for r in portfolio]) if portfolio else 0.0
    avg_coverage_80 = statistics.mean(coverages) if coverages else 0.0

    print("--- Summary ---")
    print(f"Win-rate (% of model wins): {win_rate:.2f}% ({model_wins}/{total})")
    print(f"Median MAPE improvement %: {median_improvement:.2f}%")
    print(f"Average coverage_80 across all {total} series: {avg_coverage_80:.4f}")

    # 1.e Create parquet versions of pipeline/data/processed/metrics.csv and pipeline/data/processed/restock.csv
    metrics_csv = os.path.join(base_dir, "pipeline", "data", "processed", "metrics.csv")
    metrics_parquet = os.path.join(base_dir, "pipeline", "data", "processed", "metrics.parquet")
    restock_csv = os.path.join(base_dir, "pipeline", "data", "processed", "restock.csv")
    restock_parquet = os.path.join(base_dir, "pipeline", "data", "processed", "restock.parquet")

    try:
        import pandas as pd
        if os.path.exists(metrics_csv):
            df_m = pd.read_csv(metrics_csv)
            df_m.to_parquet(metrics_parquet, index=False)
            print(f"Created {metrics_parquet}")
        else:
            print(f"Warning: {metrics_csv} not found.")

        if os.path.exists(restock_csv):
            df_r = pd.read_csv(restock_csv)
            df_r.to_parquet(restock_parquet, index=False)
            print(f"Created {restock_parquet}")
        else:
            print(f"Warning: {restock_csv} not found.")
    except ImportError as e:
        print(f"Warning: pandas not available ({e}). Skipping parquet creation.")
    except Exception as e:
        print(f"Warning: Failed to create parquet ({e}). Skipping.")

if __name__ == "__main__":
    main()
