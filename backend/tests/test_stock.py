"""Tests for stock upload and usage in /api/restock and /api/whatif."""
import pytest
from pathlib import Path
from datetime import date

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.stock import clear_stock_state

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_stock_state():
    clear_stock_state()
    yield
    clear_stock_state()


class TestStockUpload:
    """Tests for POST /api/stock/upload."""
    
    def test_valid_upload(self):
        """Valid CSV upload succeeds."""
        csv_content = """store,item,current_stock
1,1,100
1,2,200
2,1,150"""
        
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted_rows"] == 3
        assert data["missing_series_count"] == 247
        assert "uploaded_at" in data

    def test_csv_headers_are_normalized_and_fractional_stock_is_preserved(self):
        csv_content = ' STORE , ITEM , CURRENT_STOCK , note\n1,2,2.75,"warehouse, east"\n'
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })

        assert resp.status_code == 200
        assert resp.json()["missing_series_count"] == 249

        restock = client.post("/api/restock", json={
            "horizon": 30,
            "service_level": 0.95,
            "lead_time": 3,
            "stock_multiplier": 1.0,
            "store": 1,
            "use_uploaded_stock": True,
        })
        assert restock.status_code == 200
        row = next(row for row in restock.json()["rows"] if row["series_id"] == "S1_I2")
        assert row["current_stock"] == 2.75

    def test_upload_rejects_more_than_250_rows_and_caps_errors(self):
        rows = [
            f"{store},{item},100"
            for store in range(1, 6)
            for item in range(1, 51)
        ]
        rows.append("1,1,100")
        csv_content = "store,item,current_stock\n" + "\n".join(rows)
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })
        assert resp.status_code == 422
        assert 0 < len(resp.json()["errors"]) <= 20
        assert any("at most 250 data rows" in error["message"] for error in resp.json()["errors"])

    def test_upload_returns_all_required_header_errors(self):
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", "location,quantity\n1,10\n", "text/csv")
        })
        assert resp.status_code == 422
        assert {error["message"] for error in resp.json()["errors"]} == {
            "Missing 'store' column",
            "Missing 'item' column",
            "Missing 'current_stock' column",
        }
    
    def test_bad_rows_reported(self):
        """Invalid rows are reported with line numbers."""
        csv_content = """store,item,current_stock
1,1,100
6,1,200
1,51,150
1,1,300"""
        
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })
        assert resp.status_code == 422
        data = resp.json()
        assert "errors" in data
        
        # CSV line 1 is the header; all three bad records are reported.
        assert {error["line"] for error in data["errors"]} == {3, 4, 5}
        assert len(data["errors"]) == 3

    def test_template_contains_all_series_and_uploads_without_missing_series(self):
        template = client.get("/api/stock/template")
        assert template.status_code == 200
        assert template.headers["content-type"].startswith("text/csv")
        assert len(template.text.splitlines()) == 251

        uploaded = client.post("/api/stock/upload", files={
            "file": ("template.csv", template.text, "text/csv")
        })
        assert uploaded.status_code == 200
        assert uploaded.json()["accepted_rows"] == 250
        assert uploaded.json()["missing_series_count"] == 0
    
    def test_duplicate_rows_reported(self):
        """Duplicate (store,item) rows are rejected."""
        csv_content = """store,item,current_stock
1,1,100
1,1,200"""
        
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })
        assert resp.status_code == 422
    
    def test_negative_stock_rejected(self):
        """Negative current_stock is rejected."""
        csv_content = """store,item,current_stock
1,1,-10"""
        
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })
        assert resp.status_code == 422
    
    def test_non_numeric_stock_rejected(self):
        """Non-numeric current_stock is rejected."""
        csv_content = """store,item,current_stock
1,1,abc"""
        
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })
        assert resp.status_code == 422
    
    def test_oversize_file_rejected(self):
        """Oversize file returns 413."""
        # Create a file > 1 MB (1024*1024 bytes = 1048576 bytes)
        # Using larger numbers to exceed 1 MB
        large_content = "store,item,current_stock\n"
        for i in range(100000):
            large_content += f"{(i % 5) + 1},{(i % 50) + 1},{100000 + i}\n"
        
        # This should exceed 1 MB
        assert len(large_content) > 1024 * 1024, f"Test data too small: {len(large_content)}"
        
        resp = client.post("/api/stock/upload", files={
            "file": ("large.csv", large_content, "text/csv")
        })
        assert resp.status_code == 413
    
    def test_wrong_extension_rejected(self):
        """Non-CSV file is rejected."""
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.txt", "store,item,current_stock\n1,1,100", "text/plain")
        })
        assert resp.status_code == 422


class TestStockRestockIntegration:
    """Tests for stock usage in /api/restock."""
    
    def test_restock_uses_uploaded_stock(self):
        """When use_uploaded_stock=true and stock is active, uses uploaded values."""
        # Upload stock with specific values
        csv_content = """store,item,current_stock
1,1,5000"""
        
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })
        assert resp.status_code == 200
        
        # Request with use_uploaded_stock=true
        resp = client.post("/api/restock", json={
            "horizon": 30,
            "service_level": 0.95,
            "lead_time": 3,
            "stock_multiplier": 1.0,
            "use_uploaded_stock": True
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # S1_I1 should have 5000 current_stock (uploaded)
        s1_i1 = next((r for r in data["rows"] if r["series_id"] == "S1_I1"), None)
        assert s1_i1 is not None
        assert s1_i1["current_stock"] == 5000
        
        assert data["stock_source"] == "mixed (1 uploaded)"

    def test_restock_reports_simulated_when_upload_is_disabled(self):
        client.post("/api/stock/upload", files={
            "file": ("stock.csv", "store,item,current_stock\n1,1,5000", "text/csv")
        })
        resp = client.post("/api/restock", json={
            "horizon": 30,
            "service_level": 0.95,
            "lead_time": 3,
            "stock_multiplier": 1.0,
            "store": 1,
            "use_uploaded_stock": False,
        })
        assert resp.status_code == 200
        assert resp.json()["stock_source"] == "simulated"

    def test_restock_source_reflects_filtered_series(self):
        client.post("/api/stock/upload", files={
            "file": ("stock.csv", "store,item,current_stock\n1,1,5000", "text/csv")
        })
        resp = client.post("/api/restock", json={
            "horizon": 30,
            "service_level": 0.95,
            "lead_time": 3,
            "stock_multiplier": 1.0,
            "store": 1,
            "use_uploaded_stock": True,
        })
        assert resp.status_code == 200
        assert resp.json()["stock_source"] == "mixed (1 uploaded)"
    
    def test_restock_falls_back_to_simulated(self):
        """When use_uploaded_stock=true but no upload, uses simulated."""
        # Ensure no active upload
        client.delete("/api/stock")
        
        resp = client.post("/api/restock", json={
            "horizon": 30,
            "service_level": 0.95,
            "lead_time": 3,
            "stock_multiplier": 1.0,
            "use_uploaded_stock": True
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Stock source should be "simulated"
        assert data["stock_source"] == "simulated"
    
    def test_restock_doubles_stock(self):
        """Doubling stock reduces restock_qty."""
        simulated_response = client.post("/api/restock", json={
            "horizon": 30,
            "service_level": 0.95,
            "lead_time": 3,
            "stock_multiplier": 1.0,
            "use_uploaded_stock": False,
        })
        assert simulated_response.status_code == 200
        simulated_row = next(
            row for row in simulated_response.json()["rows"]
            if row["series_id"] == "S1_I1"
        )

        # Upload with doubled stock
        csv_content = """store,item,current_stock
1,1,4000"""
        
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })
        assert resp.status_code == 200
        
        # Request with use_uploaded_stock=true
        resp = client.post("/api/restock", json={
            "horizon": 30,
            "service_level": 0.95,
            "lead_time": 3,
            "stock_multiplier": 1.0,
            "use_uploaded_stock": True
        })
        assert resp.status_code == 200
        data = resp.json()
        
        s1_i1 = next((r for r in data["rows"] if r["series_id"] == "S1_I1"), None)
        assert s1_i1 is not None
        
        # With higher current_stock, restock_qty should be lower or zero
        assert s1_i1["current_stock"] == 4000
        assert s1_i1["restock_qty"] <= simulated_row["restock_qty"]


class TestStockWhatIfIntegration:
    """Tests for stock usage in /api/whatif."""
    
    def test_whatif_uses_uploaded_stock(self):
        """whatif uses uploaded stock when option is true."""
        # Upload stock with specific values
        csv_content = """store,item,current_stock
1,1,1000"""
        
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })
        assert resp.status_code == 200
        
        # Request with use_uploaded_stock=true
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
                "stock_multiplier": 1.0,
                "use_uploaded_stock": True
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Baseline should use uploaded stock
        s1_i1 = next((r for r in data["baseline"]["rows"] if r["series_id"] == "S1_I1"), None)
        assert s1_i1 is not None
        assert s1_i1["current_stock"] == 1000
    
    def test_whatif_uses_mixed_stock(self):
        """whatif returns mixed stock source when some uploaded, some simulated."""
        # Upload only S1_I1
        csv_content = """store,item,current_stock
1,1,1000"""
        
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })
        assert resp.status_code == 200
        
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
                "stock_multiplier": 1.0,
                "use_uploaded_stock": True
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["stock_source"] == "mixed (1 uploaded)"

    def test_whatif_source_is_simulated_when_upload_is_disabled(self):
        client.post("/api/stock/upload", files={
            "file": ("stock.csv", "store,item,current_stock\n1,1,1000", "text/csv")
        })
        resp = client.post("/api/whatif", json={
            "scenario": {"demand_uplift_pct": 0, "start_day": 1, "end_day": 30},
            "options": {
                "horizon": 30,
                "service_level": 0.95,
                "lead_time": 3,
                "stock_multiplier": 1.0,
                "use_uploaded_stock": False,
            },
        })
        assert resp.status_code == 200
        assert resp.json()["stock_source"] == "simulated"


class TestStockClear:
    """Tests for clearing stock."""
    
    def test_clear_restores_simulated(self):
        """Clearing stock restores simulated stock."""
        # Upload stock
        csv_content = """store,item,current_stock
1,1,1000"""
        
        resp = client.post("/api/stock/upload", files={
            "file": ("stock.csv", csv_content, "text/csv")
        })
        assert resp.status_code == 200
        
        # Clear
        resp = client.delete("/api/stock")
        assert resp.status_code == 200
        
        # Verify cleared
        resp = client.get("/api/stock")
        assert resp.json()["active"] == False
        
        # Verify restock uses simulated
        resp = client.post("/api/restock", json={
            "horizon": 30,
            "service_level": 0.95,
            "lead_time": 3,
            "stock_multiplier": 1.0,
            "use_uploaded_stock": True
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Stock source should be simulated
        assert data["stock_source"] == "simulated"
