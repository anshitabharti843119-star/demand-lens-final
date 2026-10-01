"""Tests for read-only API endpoints."""
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import json
import importlib

from backend.app.main import app
from backend.app import config
from backend.app.store import store
from backend.app.store import ArtifactStore


client = TestClient(app)


class TestHealth:
    def test_health_ok(self):
        """GET /api/health returns status ok."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["series_count"] == 250
        assert "data_dir" in data
        assert "prophet_available" in data
        assert data["prophet_available"] is True
        assert "version" in data


class TestManifest:
    def test_manifest_has_250_series_ids(self):
        """GET /api/manifest returns 250 series_ids."""
        resp = client.get("/api/manifest")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["series_ids"]) == 250


class TestSeries:
    def test_series_s1_i1_structure(self):
        """GET /api/series/S1_I1 has correct structure."""
        resp = client.get("/api/series/S1_I1")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify required fields
        assert "schema_version" in data
        assert "series_id" in data
        assert "store" in data
        assert "item" in data
        assert "history" in data
        assert "backtest" in data
        assert "future" in data
        assert "metrics" in data
        
        # Load actual file to get exact counts
        data_dir = config.DATA_DIR
        with open(data_dir / "series" / "S1_I1.json") as f:
            raw = json.load(f)
        
        # Check lengths match actual file
        assert len(data["history"]) == len(raw["history"])
        assert len(data["backtest"]["actual"]) == len(raw["backtest"]["actual"])
        assert len(data["backtest"]["model"]) == len(raw["backtest"]["model"])
        assert len(data["future"]["model"]) == len(raw["future"]["model"])
        assert len(data["backtest"]["actual"]) == 31
        assert len(data["backtest"]["model"]) == 31
        assert len(data["backtest"]["baseline"]) == 31
        assert len(data["future"]["model"]) == 30
    
    def test_series_bad_format_returns_422(self):
        """Bad series_id format returns 422."""
        resp = client.get("/api/series/S99_I1")
        assert resp.status_code == 422
        
        resp = client.get("/api/series/1_I1")
        assert resp.status_code == 422
        
        resp = client.get("/api/series/S1_X1")
        assert resp.status_code == 422
    
    def test_series_invalid_format_returns_422(self):
        """Invalid series_id format returns 422."""
        # S9_I9: store 9 is invalid (must be 1-5)
        resp = client.get("/api/series/S9_I9")
        assert resp.status_code == 422
        
        # S1_I51: item 51 is invalid (must be 1-50)
        resp = client.get("/api/series/S1_I51")
        assert resp.status_code == 422
    
    def test_series_missing_returns_404(self, tmp_path, monkeypatch):
        """Missing series_id returns 404 (valid format but file not found)."""
        (tmp_path / "series").mkdir()
        monkeypatch.setattr(store, "data_dir", tmp_path)
        resp = client.get("/api/series/S1_I1")
        assert resp.status_code == 404


class TestPortfolio:
    def test_portfolio_has_250_rows(self):
        """GET /api/portfolio returns 250 rows."""
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 250


class TestEda:
    def test_eda_loads(self):
        """GET /api/eda returns EDA data."""
        resp = client.get("/api/eda")
        assert resp.status_code == 200
        data = resp.json()
        assert "monthly_total" in data
        assert "weekday_avg" in data
        assert "weekend_vs_weekday" in data


class TestRestockInputs:
    def test_restock_inputs_loads(self):
        """GET /api/restock-inputs returns restock data."""
        resp = client.get("/api/restock-inputs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 250


class TestSeriesFileValidation:
    def test_all_series_files_load_through_pydantic(self):
        """Every one of the 250 series files loads through the Pydantic model."""
        manifest = store.load_manifest()
        for series_id in manifest.series_ids:
            try:
                series = store.load_series(series_id)
                # Verify it's a valid SeriesData
                assert series.series_id == series_id
                assert series.store >= 1 and series.store <= 5
                assert series.item >= 1 and series.item <= 50
                assert len(series.history) > 0
                assert len(series.backtest.actual) > 0
                assert len(series.backtest.model) > 0
                assert len(series.future.model) > 0
            except Exception as e:
                pytest.fail(f"Failed to load {series_id}: {e}")


def test_data_directory_is_repo_relative_from_another_working_directory(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEMANDLENS_DATA_DIR", raising=False)
    monkeypatch.delenv("DEMANDLENS_RAW_CSV", raising=False)
    reloaded_config = importlib.reload(config)

    assert reloaded_config.DATA_DIR == reloaded_config.REPO_ROOT / "public" / "data"
    assert (
        reloaded_config.RAW_CSV
        == reloaded_config.REPO_ROOT / "pipeline" / "data" / "raw" / "train.csv"
    )


def test_artifact_store_rejects_non_standard_json_numbers(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"stores":[NaN]}', encoding="utf-8")
    artifact_store = ArtifactStore(tmp_path)

    with pytest.raises(ValueError, match=r"manifest\.json.*Non-standard JSON number"):
        artifact_store.load_manifest()
