"""Tests for POST /api/whatif endpoint."""
import pytest
import math
from pathlib import Path

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


class TestWhatIfZeroUplift:
    """Test that zero uplift gives identical baseline and scenario."""
    
    def test_zero_uplift_identical(self):
        """demand_uplift_pct=0 gives identical baseline and scenario."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": 0,
                "start_day": 1,
                "end_day": 30
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "NaN" not in resp.text
        assert "Infinity" not in resp.text
        
        baseline = data["baseline"]
        scenario = data["scenario"]
        
        # Rows should be identical
        assert len(baseline["rows"]) == len(scenario["rows"])
        
        for b_row, s_row in zip(baseline["rows"], scenario["rows"]):
            assert b_row["series_id"] == s_row["series_id"]
            assert b_row["restock_qty"] == s_row["restock_qty"]
            assert b_row["forecast_demand"] == s_row["forecast_demand"]
            assert b_row["safety_stock"] == s_row["safety_stock"]
            assert b_row["days_of_cover"] == s_row["days_of_cover"]
            assert b_row["priority"] == s_row["priority"]
        
        # Summaries should be identical
        assert baseline["summary"]["total_units"] == scenario["summary"]["total_units"]
        assert baseline["summary"]["total_products"] == scenario["summary"]["total_products"]
        assert baseline["summary"]["high_priority"] == scenario["summary"]["high_priority"]
        assert baseline["summary"]["avg_days_of_cover"] == scenario["summary"]["avg_days_of_cover"]
        
        # Delta should be zero
        assert data["delta"]["total_units_change"] == 0
        assert data["delta"]["products_changing_priority"] == 0


class TestWhatIfPositiveUplift:
    """Test positive uplift behavior."""
    
    def test_positive_uplift_increases_units(self):
        """Positive uplift never decreases total units."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": 30,
                "start_day": 1,
                "end_day": 30
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        
        baseline_units = data["baseline"]["summary"]["total_units"]
        scenario_units = data["scenario"]["summary"]["total_units"]
        
        assert scenario_units >= baseline_units, \
            f"Positive uplift should not decrease units: {baseline_units} -> {scenario_units}"

    def test_positive_partial_period_uplift_never_decreases_units(self):
        response = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": 30,
                "start_day": 5,
                "end_day": 15,
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0,
            },
        })
        assert response.status_code == 200
        data = response.json()
        assert (
            data["scenario"]["summary"]["total_units"]
            >= data["baseline"]["summary"]["total_units"]
        )
    
    def test_positive_uplift_changes_priority(self):
        """Positive uplift can change priorities (some products may no longer need restock)."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": 50,
                "start_day": 1,
                "end_day": 30
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # With 50% uplift, some products may see reduced restock needs
        # or even go to zero (no restock needed)
        assert data["delta"]["total_units_change"] > 0
    
    def test_example_output(self):
        """Test example output: +30% uplift on days 5-15."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": 30,
                "start_day": 5,
                "end_day": 15
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Check structure
        assert "baseline" in data
        assert "scenario" in data
        assert "delta" in data
        assert "disclaimer" in data
        
        # Check disclaimer
        assert data["disclaimer"] == "Scenario scales the existing forecast; it is not a re-trained model."
        
        # Check delta structure
        delta = data["delta"]
        assert "total_units_change" in delta
        assert "products_changing_priority" in delta
        assert "top_changes" in delta
        
        # Check top_changes structure
        top_changes = delta["top_changes"]
        assert len(top_changes) <= 10
        assert data["scenario"]["summary"]["total_units"] >= data["baseline"]["summary"]["total_units"]
        
        if len(top_changes) > 0:
            first_change = top_changes[0]
            assert "series_id" in first_change
            assert "qty_before" in first_change
            assert "qty_after" in first_change
            assert "priority_before" in first_change
            assert "priority_after" in first_change
        
        print(f"\nExample output for +30% uplift on days 5-15:")
        print(f"  Baseline total_units: {data['baseline']['summary']['total_units']}")
        print(f"  Scenario total_units: {data['scenario']['summary']['total_units']}")
        print(f"  Total units change: {delta['total_units_change']}")
        print(f"  Products changing priority: {delta['products_changing_priority']}")
        print(f"  Top 3 changes:")
        for change in delta["top_changes"][:3]:
            print(f"    {change['series_id']}: {change['qty_before']} -> {change['qty_after']} "
                  f"({change['priority_before']} -> {change['priority_after']})")


class TestWhatIfNegativeUplift:
    """Test negative uplift behavior."""
    
    def test_negative_uplift_does_not_increase_units(self):
        """Negative uplift never increases total units."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": -30,
                "start_day": 1,
                "end_day": 30
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        
        baseline_units = data["baseline"]["summary"]["total_units"]
        scenario_units = data["scenario"]["summary"]["total_units"]
        
        assert scenario_units <= baseline_units, \
            f"Negative uplift should not increase units: {baseline_units} -> {scenario_units}"

    def test_negative_partial_period_uplift_never_increases_units(self):
        response = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": -30,
                "start_day": 5,
                "end_day": 15,
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0,
            },
        })
        assert response.status_code == 200
        data = response.json()
        assert (
            data["scenario"]["summary"]["total_units"]
            <= data["baseline"]["summary"]["total_units"]
        )


class TestWhatIfValidation:
    """Test 422 validation for invalid inputs."""
    
    def test_demand_uplift_below_min(self):
        """demand_uplift_pct=-51 returns 422."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": -51,
                "start_day": 1,
                "end_day": 30
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0
            }
        })
        assert resp.status_code == 422

    def test_invalid_lead_time(self):
        response = client.post("/api/whatif", json={
            "scenario": {"demand_uplift_pct": 0, "start_day": 1, "end_day": 30},
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 15,
                "stock_multiplier": 1.0,
            },
        })
        assert response.status_code == 422

    def test_invalid_stock_multiplier(self):
        response = client.post("/api/whatif", json={
            "scenario": {"demand_uplift_pct": 0, "start_day": 1, "end_day": 30},
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 2.1,
            },
        })
        assert response.status_code == 422
    
    def test_demand_uplift_above_max(self):
        """demand_uplift_pct=201 returns 422."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": 201,
                "start_day": 1,
                "end_day": 30
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0
            }
        })
        assert resp.status_code == 422
    
    def test_start_day_greater_than_end_day(self):
        """start_day=10, end_day=5 returns 422."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": 0,
                "start_day": 10,
                "end_day": 5
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0
            }
        })
        assert resp.status_code == 422
    
    def test_invalid_horizon(self):
        """horizon=7 returns 422."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": 0,
                "start_day": 1,
                "end_day": 30
            },
            "options": {
                "horizon": 7,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0
            }
        })
        assert resp.status_code == 422
    
    def test_invalid_service_level(self):
        """service_level=0.8 returns 422."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": 0,
                "start_day": 1,
                "end_day": 30
            },
            "options": {
                "horizon": 30,
                "service_level": 0.8,
                "lead_time": 3,
                "stock_multiplier": 1.0
            }
        })
        assert resp.status_code == 422


class TestWhatIfNoNaNInfinity:
    """Test no NaN/Infinity in JSON responses."""
    
    def test_no_nan_infinity(self):
        """Response has no NaN or Infinity."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": 50,
                "start_day": 1,
                "end_day": 30
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "NaN" not in resp.text
        assert "Infinity" not in resp.text
        
        def check_no_nan_inf(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    check_no_nan_inf(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    check_no_nan_inf(v, f"{path}[{i}]")
            elif isinstance(obj, float):
                assert not math.isnan(obj), f"NaN found at {path}"
                assert not math.isinf(obj), f"Infinity found at {path}"
        
        check_no_nan_inf(data)


class TestWhatIfSeriesFilter:
    """Test series_id filtering."""
    
    def test_filter_single_series(self):
        """series_id filter returns only that series."""
        resp = client.post("/api/whatif", json={
            "scenario": {
                "demand_uplift_pct": 30,
                "start_day": 1,
                "end_day": 30
            },
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0
            },
            "series_id": "S1_I1"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert len(data["baseline"]["rows"]) == 1
        assert len(data["scenario"]["rows"]) == 1
        assert data["baseline"]["rows"][0]["series_id"] == "S1_I1"


class TestStockEndpoint:
    """Tests for stock upload endpoints."""
    
    def test_get_stock_empty(self):
        """GET /api/stock returns empty state initially."""
        resp = client.get("/api/stock")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] == False
    
    def test_stock_template(self):
        """GET /api/stock/template returns CSV with all 250 series."""
        resp = client.get("/api/stock/template")
        assert resp.status_code == 200
        csv_content = resp.text
        
        lines = csv_content.strip().split("\n")
        assert len(lines) == 251  # 1 header + 250 data rows
        assert lines[0] == "store,item,current_stock"
        
        # Check some rows exist
        assert "1,1," in csv_content
        assert "5,50," in csv_content
    
    def test_clear_stock(self):
        """DELETE /api/stock clears stock state."""
        # First upload something
        resp = client.post("/api/stock/upload", files={
            "file": ("test.csv", "store,item,current_stock\n1,1,100", "text/csv")
        })
        assert resp.status_code == 200
        
        # Verify active
        resp = client.get("/api/stock")
        assert resp.json()["active"] == True
        
        # Clear
        resp = client.delete("/api/stock")
        assert resp.status_code == 200
        
        # Verify cleared
        resp = client.get("/api/stock")
        assert resp.json()["active"] == False
