"""Tests for POST /api/restock endpoint parity with TypeScript computeRestock."""
import pytest
import math
from pathlib import Path
import json
import shutil
import subprocess

from fastapi.testclient import TestClient
import backend.app.main as main_module
from backend.app.main import app
from backend.app.store import store
from backend.app.restock import compute_restock, Z_SCORES
from backend.app.schemas import RestockInput


client = TestClient(app)


def load_restock_csv():
    """Load pipeline/data/processed/restock.csv for comparison."""
    import csv
    repo_root = Path(__file__).resolve().parents[2]
    csv_path = repo_root / "pipeline" / "data" / "processed" / "restock.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["series_id"]: row for row in reader}


class TestRestockDefaultOptions:
    """Test POST /api/restock with default options matches pipeline CSV."""
    
    def test_restock_rows_match_csv(self):
        """With default options, endpoint rows match pipeline restock.csv (restock_qty exact)."""
        resp = client.post("/api/restock", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "NaN" not in resp.text
        assert "Infinity" not in resp.text
        rows = data["rows"]
        assert len(rows) == 250
        assert set(data["summary"]) == {
            "total_products",
            "total_units",
            "high_priority",
            "avg_days_of_cover",
        }
        
        csv_data = load_restock_csv()
        
        exact_matches = 0
        within_001 = 0
        
        for row in rows:
            csv_row = csv_data[row["series_id"]]
            
            # restock_qty must match exactly
            assert row["restock_qty"] == int(csv_row["restock_qty"]), \
                f"{row['series_id']}: restock_qty {row['restock_qty']} != {csv_row['restock_qty']}"
            exact_matches += 1
            
            # Other numbers within 0.01
            assert abs(row["current_stock"] - float(csv_row["current_stock"])) <= 0.01, \
                f"{row['series_id']}: current_stock mismatch"
            assert abs(row["forecast_demand"] - float(csv_row["forecast_demand"])) <= 0.01, \
                f"{row['series_id']}: forecast_demand mismatch"
            within_001 += 1
            
            assert abs(row["safety_stock"] - float(csv_row["safety_stock"])) <= 0.01, \
                f"{row['series_id']}: safety_stock mismatch"
            
            # days_of_cover - handle infinity
            csv_doc = csv_row["days_of_cover"]
            if csv_doc in ("∞", "inf"):
                assert row["days_of_cover"] >= 1e8, \
                    f"{row['series_id']}: days_of_cover should be infinite"
            else:
                assert abs(row["days_of_cover"] - float(csv_doc)) <= 0.01, \
                    f"{row['series_id']}: days_of_cover mismatch"
            
            assert row["priority"] == csv_row["priority"], \
                f"{row['series_id']}: priority mismatch"
        
        assert exact_matches == 250
        assert within_001 == 250
        print(f"\nExact restock_qty matches: {exact_matches}/250")
        print(f"Forecast demand matches within 0.01: {within_001}/250")


class TestRestockHandComputed:
    """Test a few hand-computed cases for one series."""
    
    @pytest.fixture
    def s1_i1_inputs(self):
        """Get S1_I1 restock inputs."""
        return store.load_restock_inputs()["S1_I1"]
    
    def test_s1_i1_default_options(self, s1_i1_inputs):
        """Hand-compute S1_I1 with default options and verify."""
        horizon = 30
        service_level = 0.95  # z = 1.65
        lead_time = 3
        stock_multiplier = 1.0
        
        z = Z_SCORES[service_level]
        
        # Manual calculation
        yhat_future = s1_i1_inputs.yhat_future[:horizon]
        forecast_demand = sum(yhat_future)
        
        sigma_daily = s1_i1_inputs.sigma_daily
        safety_stock = z * sigma_daily * math.sqrt(lead_time)
        
        current_stock = s1_i1_inputs.current_stock * stock_multiplier
        restock_qty = max(0, math.ceil(forecast_demand + safety_stock - current_stock))
        
        if forecast_demand > 0:
            days_of_cover = current_stock / (forecast_demand / horizon)
        else:
            days_of_cover = float('inf')
        
        if days_of_cover == float('inf'):
            days_of_cover = 1e9
        
        days_of_cover = round(days_of_cover, 2)
        
        if days_of_cover < lead_time:
            priority = "HIGH"
        elif days_of_cover < horizon:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        
        # Call endpoint
        resp = client.post("/api/restock", json={
            "horizon": horizon,
            "service_level": service_level,
            "lead_time": lead_time,
            "stock_multiplier": stock_multiplier
        })
        assert resp.status_code == 200
        rows = {r["series_id"]: r for r in resp.json()["rows"]}
        row = rows["S1_I1"]
        
        assert row["forecast_demand"] == forecast_demand
        assert row["safety_stock"] == safety_stock
        assert row["restock_qty"] == restock_qty
        assert abs(row["days_of_cover"] - days_of_cover) <= 0.01
        assert row["priority"] == priority
    
    def test_s1_i1_high_service_level(self, s1_i1_inputs):
        """S1_I1 with service_level=0.99 should have higher restock_qty."""
        horizon = 30
        service_level = 0.99  # z = 2.33
        lead_time = 3
        stock_multiplier = 1.0
        
        z_high = Z_SCORES[0.99]
        z_default = Z_SCORES[0.95]
        
        yhat_future = s1_i1_inputs.yhat_future[:horizon]
        forecast_demand = sum(yhat_future)
        
        sigma_daily = s1_i1_inputs.sigma_daily
        
        # Higher z -> higher safety_stock -> higher restock_qty
        ss_high = z_high * sigma_daily * math.sqrt(lead_time)
        ss_default = z_default * sigma_daily * math.sqrt(lead_time)
        
        current_stock = s1_i1_inputs.current_stock * stock_multiplier
        
        qty_high = math.ceil(forecast_demand + ss_high - current_stock)
        qty_default = math.ceil(forecast_demand + ss_default - current_stock)
        
        resp = client.post("/api/restock", json={
            "horizon": horizon,
            "service_level": service_level,
            "lead_time": lead_time,
            "stock_multiplier": stock_multiplier,
        })
        assert resp.status_code == 200
        row = next(r for r in resp.json()["rows"] if r["series_id"] == "S1_I1")
        assert row["restock_qty"] == max(0, qty_high)
        assert row["restock_qty"] >= max(0, qty_default)

    def test_s1_i1_stock_multiplier_and_lead_time(self, s1_i1_inputs):
        """Hand-compute S1_I1 with non-default stock and lead time."""
        horizon, service_level, lead_time, stock_multiplier = 14, 0.9, 7, 1.5
        demand = sum(s1_i1_inputs.yhat_future[:horizon])
        safety = 1.28 * s1_i1_inputs.sigma_daily * math.sqrt(lead_time)
        stock = s1_i1_inputs.current_stock * stock_multiplier

        resp = client.post("/api/restock", json={
            "horizon": horizon,
            "service_level": service_level,
            "lead_time": lead_time,
            "stock_multiplier": stock_multiplier,
        })
        assert resp.status_code == 200
        row = next(r for r in resp.json()["rows"] if r["series_id"] == "S1_I1")
        assert row["forecast_demand"] == pytest.approx(demand)
        assert row["safety_stock"] == pytest.approx(safety)
        assert row["current_stock"] == pytest.approx(stock)
        assert row["restock_qty"] == max(0, math.ceil(demand + safety - stock))


class TestRestockZValues:
    """Test that z-values match TypeScript exactly."""
    
    def test_z_scores(self):
        """Z-scores match TypeScript: 0.9->1.28, 0.95->1.65, 0.99->2.33."""
        assert Z_SCORES[0.9] == 1.28
        assert Z_SCORES[0.95] == 1.65
        assert Z_SCORES[0.99] == 2.33


class TestRestockLeadTimeComparison:
    """Test that lead_time=14 with service_level=0.99 gives higher restock_qty."""
    
    def test_higher_lead_time_and_service_level_gives_higher_qty(self):
        """lead_time=14 with service_level=0.99 >= default for every series."""
        # Get default restock
        resp_default = client.post("/api/restock", json={})
        assert resp_default.status_code == 200
        rows_default = {r["series_id"]: r for r in resp_default.json()["rows"]}
        
        # Get high scenario restock
        resp_high = client.post("/api/restock", json={
            "horizon": 30,
            "service_level": 0.99,
            "lead_time": 14,
            "stock_multiplier": 1.0
        })
        assert resp_high.status_code == 200
        rows_high = {r["series_id"]: r for r in resp_high.json()["rows"]}
        
        for sid, row_default in rows_default.items():
            row_high = rows_high[sid]
            assert row_high["restock_qty"] >= row_default["restock_qty"], \
                f"{sid}: higher scenario should have >= restock_qty"


class TestRestockNoNaNInfinity:
    """Test no NaN/Infinity in JSON responses."""
    
    def test_no_nan_infinity_in_response(self):
        """JSON response has no NaN or Infinity."""
        resp = client.post("/api/restock", json={})
        assert resp.status_code == 200
        data = resp.json()
        
        rows = data["rows"]
        
        for row in rows:
            # Check all numeric fields
            assert not math.isnan(row["forecast_demand"]), \
                f"{row['series_id']}: NaN in forecast_demand"
            assert not math.isinf(row["forecast_demand"]), \
                f"{row['series_id']}: Infinity in forecast_demand"
            
            assert not math.isnan(row["safety_stock"]), \
                f"{row['series_id']}: NaN in safety_stock"
            assert not math.isinf(row["safety_stock"]), \
                f"{row['series_id']}: Infinity in safety_stock"
            
            assert not math.isnan(row["days_of_cover"]), \
                f"{row['series_id']}: NaN in days_of_cover"
            # days_of_cover can be Infinity (handled as large cap)
            # but it should be capped, not actual Infinity
            if math.isinf(row["days_of_cover"]):
                # This is ok only if it's a real infinity case
                # but our code caps it, so this should not happen
                pytest.fail(f"{row['series_id']}: Infinity in days_of_cover (should be capped)")
            
            # restock_qty is int, no NaN/Inf possible
    
    def test_no_nan_infinity_in_summary(self):
        """Summary has no NaN/Infinity."""
        resp = client.post("/api/restock", json={})
        assert resp.status_code == 200
        data = resp.json()
        summary = data["summary"]
        
        assert not math.isnan(summary["avg_days_of_cover"]), "NaN in avg_days_of_cover"
        assert not math.isinf(summary["avg_days_of_cover"]), "Infinity in avg_days_of_cover"


class TestRestockFilters:
    """Test restock filters work correctly."""
    
    def test_filter_by_store(self):
        """Filter by store returns only that store's rows."""
        resp = client.post("/api/restock", json={"store_filter": 1})
        assert resp.status_code == 200
        rows = resp.json()["rows"]
        
        for row in rows:
            assert row["store"] == 1, f"Unexpected store: {row['store']}"
    
    def test_filter_by_priority(self):
        """Filter by priority returns only that priority's rows."""
        resp = client.post("/api/restock", json={"priority_filter": "HIGH"})
        assert resp.status_code == 200
        rows = resp.json()["rows"]
        
        for row in rows:
            assert row["priority"] == "HIGH", f"Unexpected priority: {row['priority']}"
    
    def test_filter_only_restock(self):
        """Filter only_restock returns only rows with restock_qty > 0."""
        resp = client.post("/api/restock", json={"only_restock": True})
        assert resp.status_code == 200
        rows = resp.json()["rows"]
        
        for row in rows:
            assert row["restock_qty"] > 0, f"Unexpected restock_qty: {row['restock_qty']}"


class TestRestockValidation:
    """Test 422 validation for out-of-range values."""
    
    def test_invalid_horizon(self):
        """horizon=7 should be rejected with 422."""
        resp = client.post("/api/restock", json={"horizon": 7})
        assert resp.status_code == 422

    def test_lead_time_above_maximum(self):
        assert client.post("/api/restock", json={"lead_time": 15}).status_code == 422
    
    def test_invalid_service_level(self):
        """service_level=0.8 should be rejected with 422."""
        resp = client.post("/api/restock", json={"service_level": 0.8})
        assert resp.status_code == 422

    @pytest.mark.parametrize("stock_multiplier", [0.49, 2.01])
    def test_stock_multiplier_outside_bounds(self, stock_multiplier):
        assert client.post(
            "/api/restock", json={"stock_multiplier": stock_multiplier}
        ).status_code == 422
    
    def test_invalid_lead_time_zero(self):
        """lead_time=0 should be rejected with 422."""
        resp = client.post("/api/restock", json={"lead_time": 0})
        assert resp.status_code == 422

    def test_store_and_priority_request_names(self):
        response = client.post(
            "/api/restock", json={"store": 1, "priority": "HIGH"}
        )
        assert response.status_code == 200
        assert all(
            row["store"] == 1 and row["priority"] == "HIGH"
            for row in response.json()["rows"]
        )

    def test_invalid_lead_time_negative(self):
        assert client.post("/api/restock", json={"lead_time": -1}).status_code == 422

    def test_invalid_stock_multiplier_negative(self):
        assert client.post(
            "/api/restock", json={"stock_multiplier": -0.5}
        ).status_code == 422

    def test_invalid_store_filter(self):
        assert client.post("/api/restock", json={"store_filter": 6}).status_code == 422

    def test_invalid_priority_filter(self):
        assert client.post(
            "/api/restock", json={"priority_filter": "INVALID"}
        ).status_code == 422


def test_zero_demand_uses_documented_finite_cover_cap(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "load_restock_inputs",
        lambda: {
            "S1_I1": RestockInput(
                store=1,
                item=1,
                current_stock=10,
                avg_daily_28=0,
                sigma_daily=0,
                yhat_future=[0] * 30,
            )
        },
    )
    response = client.post("/api/restock", json={})
    assert response.status_code == 200
    row = response.json()["rows"][0]
    assert row["days_of_cover"] == 1e9
    assert "Infinity" not in response.text


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_five_series_match_typescript_compute_restock():
    """Compare the Python port against lib/restock.ts for five fixed series."""
    repo_root = Path(__file__).resolve().parents[2]
    script = """
import { readFileSync } from "node:fs";
import { computeRestock } from "./lib/restock.ts";
const source = JSON.parse(readFileSync("public/data/restock_inputs.json", "utf8"));
const ids = ["S1_I1", "S2_I15", "S3_I25", "S4_I27", "S5_I50"];
const selected = Object.fromEntries(ids.map((id) => [id, source[id]]));
const rows = computeRestock(selected, {
  horizon: 30, serviceLevel: 0.95, leadTime: 3, stockMultiplier: 1
});
console.log(JSON.stringify(rows, (_, value) => value === Infinity ? "Infinity" : value));
"""
    completed = subprocess.run(
        ["node", "--import", "tsx", "--input-type=module", "-e", script],
        cwd=repo_root,
        capture_output=True,
        check=True,
        text=True,
    )
    ts_rows = {row["series_id"]: row for row in json.loads(completed.stdout)}
    inputs = store.load_restock_inputs()
    ids = list(ts_rows)
    py_rows = {
        row.series_id: row.model_dump()
        for row in compute_restock(
            {series_id: inputs[series_id] for series_id in ids},
            horizon=30,
            service_level=0.95,
            lead_time=3,
            stock_multiplier=1,
        )
    }

    for series_id in ids:
        for field in (
            "store",
            "item",
            "restock_qty",
            "priority",
        ):
            assert py_rows[series_id][field] == ts_rows[series_id][field]
        for field in (
            "current_stock",
            "forecast_demand",
            "safety_stock",
            "days_of_cover",
        ):
            assert py_rows[series_id][field] == pytest.approx(
                ts_rows[series_id][field], abs=1e-10
            )
