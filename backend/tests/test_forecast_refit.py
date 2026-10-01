"""Tests for POST /api/forecast/refit endpoint."""
import pytest
import asyncio
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
import backend.app.forecast as forecast_module
import backend.app.main as main_module
from backend.app.main import app
from backend.app.store import store
from backend.app.config import RAW_CSV
from backend.app.forecast import (
    PROPHET_PARAMS,
    _build_fit_df,
    _get_cache_path,
    _predict_forecast,
)

client = TestClient(app)


def load_backtest_forecast():
    """Load backtest model forecasts from series files."""
    manifest = store.load_manifest()
    results = {}
    for sid in manifest.series_ids:
        series = store.load_series(sid)
        backtest_model = series.backtest.model
        results[sid] = backtest_model
    return results


def load_future_forecast():
    """Load future model forecasts from series files."""
    manifest = store.load_series("S1_I1")  # Any series will do
    future = store.load_series("S1_I1").future.model
    return future


class TestForecastParity:
    """Test that refit reproduces pipeline backtest.forecast exactly."""
    
    @pytest.mark.parametrize("series_id", ["S1_I1", "S3_I25", "S5_I50"])
    def test_refit_matches_backtest(self, series_id):
        """refit with train_end=2017-11-30, horizon=31 should match backtest.model yhat."""
        _get_cache_path(series_id, "2017-11-30", 31).unlink(missing_ok=True)
        # Use train_end just before test period starts
        resp = client.post("/api/forecast/refit", json={
            "series_id": series_id,
            "train_end": "2017-11-30",
            "horizon": 31
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Load expected from backtest.model
        series = store.load_series(series_id)
        expected = series.backtest.model
        assert len(data["forecast"]) == len(expected) == 31
        
        # Compare yhat values
        actual_forecast = data["forecast"]
        max_diff = 0.0
        for i, (a, e) in enumerate(zip(actual_forecast, expected)):
            # a is dict from API, e is ForecastPoint from Pydantic
            diff = abs(a["yhat"] - e.yhat)
            max_diff = max(max_diff, diff)
            assert diff <= 0.05, f"{series_id} day {i}: {a['yhat']} vs {e.yhat} diff={diff}"
        
        print(f"\n{series_id} max_diff: {max_diff}")
        print(f"{series_id} fit_seconds: {data['fit_seconds']}")
    
    @pytest.mark.parametrize("series_id", ["S1_I1", "S3_I25", "S5_I50"])
    def test_refit_matches_future(self, series_id):
        """refit with train_end=2017-12-31, horizon=30 should match future.model yhat."""
        _get_cache_path(series_id, "2017-12-31", 30).unlink(missing_ok=True)
        # Use train_end at end of known data
        resp = client.post("/api/forecast/refit", json={
            "series_id": series_id,
            "train_end": "2017-12-31",
            "horizon": 30
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Load expected from future.model
        series = store.load_series(series_id)
        expected = series.future.model
        
        # Compare yhat values
        actual_forecast = data["forecast"]
        max_diff = 0.0
        for i, (a, e) in enumerate(zip(actual_forecast, expected)):
            # a is dict from API, e is ForecastPoint from Pydantic
            diff = abs(a["yhat"] - e.yhat)
            max_diff = max(max_diff, diff)
            # Allow small tolerance due to potential seed differences
            assert diff <= 0.1, f"{series_id} day {i}: {a['yhat']} vs {e.yhat} diff={diff}"
        
        print(f"\n{series_id} future max_diff: {max_diff}")


class TestForecastNoLeakage:
    """Test that refit doesn't leak future data."""
    
    def test_train_end_boundary(self):
        """With train_end=2017-11-30, fit max date is 2017-11-30."""
        fit_df = _build_fit_df(Path(RAW_CSV), "S1_I1", "2017-11-30")
        assert fit_df["ds"].max() == pd.Timestamp("2017-11-30")
    
    def test_poison_test_in_memory(self):
        """Test that poisoning data after train_end doesn't affect forecast."""
        raw_df = pd.read_csv(RAW_CSV)
        poisoned = raw_df.copy()
        later = pd.to_datetime(poisoned["date"]) > pd.Timestamp("2017-11-30")
        poisoned.loc[later, "sales"] *= 3

        clean_fit = _build_fit_df(
            Path(RAW_CSV), "S1_I1", "2017-11-30", source_df=raw_df
        )
        poisoned_fit = _build_fit_df(
            Path(RAW_CSV), "S1_I1", "2017-11-30", source_df=poisoned
        )
        pd.testing.assert_frame_equal(clean_fit, poisoned_fit)
        assert clean_fit["ds"].max() == pd.Timestamp("2017-11-30")

        future_dates = pd.date_range("2017-12-01", periods=31, freq="D")
        clean = _predict_forecast(clean_fit, future_dates, seed=42)
        poisoned_forecast = _predict_forecast(poisoned_fit, future_dates, seed=42)
        for clean_values, poisoned_values in zip(clean, poisoned_forecast):
            np.testing.assert_array_equal(clean_values, poisoned_values)


class TestForecastCache:
    """Test caching behavior."""
    
    def test_second_call_returns_cached(self):
        """Second identical call returns cached=true and is faster."""
        cache_path = _get_cache_path("S1_I1", "2017-11-30", 31)
        cache_path.unlink(missing_ok=True)
        # First call
        resp1 = client.post("/api/forecast/refit", json={
            "series_id": "S1_I1",
            "train_end": "2017-11-30",
            "horizon": 31
        })
        assert resp1.status_code == 200
        data1 = resp1.json()
        
        # Second identical call
        resp2 = client.post("/api/forecast/refit", json={
            "series_id": "S1_I1",
            "train_end": "2017-11-30",
            "horizon": 31
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        
        # Second call should be cached
        assert data2["cached"] == True, "Second call should be cached"
        
        # Cached response should be faster (significantly less fit_seconds)
        print(f"\nFirst call fit_seconds: {data1['fit_seconds']}")
        print(f"Second call fit_seconds: {data2['fit_seconds']}")
        print(f"Cached: {data2['cached']}")
        assert data1["cached"] is False
        assert data2["fit_seconds"] < max(0.01, data1["fit_seconds"] * 0.1)
        assert data1["params"] == data2["params"] == PROPHET_PARAMS
        
        # Results should be identical
        assert data1["forecast"] == data2["forecast"]


class TestForecastValidation:
    """Test 422 validation for invalid inputs."""
    
    def test_invalid_series_id_format(self):
        """Invalid series_id format returns 422."""
        resp = client.post("/api/forecast/refit", json={
            "series_id": "INVALID",
            "train_end": "2017-11-30",
            "horizon": 30
        })
        assert resp.status_code == 422

    def test_series_id_out_of_range(self):
        """series_id S6_I1 returns 422."""
        resp = client.post("/api/forecast/refit", json={
            "series_id": "S6_I1",
            "train_end": "2017-11-30",
            "horizon": 30
        })
        assert resp.status_code == 422

    def test_invalid_train_end_format(self):
        """Invalid train_end format returns 422."""
        resp = client.post("/api/forecast/refit", json={
            "series_id": "S1_I1",
            "train_end": "2017-11",
            "horizon": 30
        })
        assert resp.status_code == 422

    def test_invalid_calendar_date(self):
        response = client.post("/api/forecast/refit", json={
            "series_id": "S1_I1",
            "train_end": "2017-02-30",
            "horizon": 30,
        })
        assert response.status_code == 422

    def test_train_end_before_range(self):
        """train_end=2013-12-31 returns 422."""
        resp = client.post("/api/forecast/refit", json={
            "series_id": "S1_I1",
            "train_end": "2013-12-31",
            "horizon": 30
        })
        assert resp.status_code == 422

    def test_train_end_after_range(self):
        """train_end=2018-01-01 returns 422."""
        resp = client.post("/api/forecast/refit", json={
            "series_id": "S1_I1",
            "train_end": "2018-01-01",
            "horizon": 30
        })
        assert resp.status_code == 422

    def test_invalid_horizon_zero(self):
        """horizon=0 returns 422."""
        resp = client.post("/api/forecast/refit", json={
            "series_id": "S1_I1",
            "train_end": "2017-11-30",
            "horizon": 0
        })
        assert resp.status_code == 422

    def test_invalid_horizon_too_large(self):
        """horizon=61 returns 422."""
        resp = client.post("/api/forecast/refit", json={
            "series_id": "S1_I1",
            "train_end": "2017-11-30",
            "horizon": 61
        })
        assert resp.status_code == 422


def test_missing_raw_csv_returns_503(monkeypatch, tmp_path):
    monkeypatch.setattr(forecast_module, "RAW_CSV", tmp_path / "missing.csv")
    response = client.post("/api/forecast/refit", json={
        "series_id": "S1_I1",
        "train_end": "2017-11-30",
        "horizon": 1,
    })
    assert response.status_code == 503
    assert "Raw CSV not found" in response.json()["detail"]


def test_refit_timeout_returns_504(monkeypatch):
    class FakeLoop:
        def run_in_executor(self, executor, function, *args):
            return None

    class FakeAsyncio:
        TimeoutError = asyncio.TimeoutError

        @staticmethod
        def get_running_loop():
            return FakeLoop()

        @staticmethod
        async def wait_for(awaitable, timeout):
            assert timeout == 90
            raise asyncio.TimeoutError

    monkeypatch.setattr(main_module, "asyncio", FakeAsyncio)
    response = client.post("/api/forecast/refit", json={
        "series_id": "S1_I1",
        "train_end": "2017-11-30",
        "horizon": 1,
    })
    assert response.status_code == 504


class TestForecastMetrics:
    """Test metrics computation."""
    
    def test_metrics_present_when_actual_available(self):
        """Metrics computed when actual sales exist in forecast period."""
        # Use train_end=2017-11-30, horizon=1 to get Dec 1, 2017 (has actuals)
        resp = client.post("/api/forecast/refit", json={
            "series_id": "S1_I1",
            "train_end": "2017-11-30",
            "horizon": 1
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Dec 1, 2017 has actual data, so metrics should be present
        assert data["metrics"] is not None, "Metrics should be present when actual data exists"
    
    def test_metrics_with_actual_data(self):
        """Metrics computed when actual data available (test with Dec 2017)."""
        # Use train_end=2017-11-30 but only forecast 1 day to get Dec 1
        resp = client.post("/api/forecast/refit", json={
            "series_id": "S1_I1",
            "train_end": "2017-11-30",
            "horizon": 1
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Dec 1, 2017 should have actual data
        # So metrics should be present
        assert data["metrics"] is not None, "Metrics should be present when actual data exists"
