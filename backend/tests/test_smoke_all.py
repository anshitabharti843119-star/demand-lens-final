"""Smoke coverage for every public API endpoint and the API hardening behavior."""
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.main import _check_refit_rate_limit


def test_every_api_endpoint_once(monkeypatch, caplog):
    monkeypatch.setattr(
        main,
        "refit",
        lambda series_id, train_end, horizon: {
            "series_id": series_id,
            "train_end": train_end.isoformat(),
            "horizon": horizon,
            "forecast": [],
            "actual": [],
            "metrics": None,
            "fit_seconds": 0.01,
            "cached": False,
            "params": {},
        },
    )

    with TestClient(main.app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/manifest").status_code == 200
        assert client.get("/api/series/S1_I1").status_code == 200
        assert client.get("/api/portfolio").status_code == 200
        assert client.get("/api/eda").status_code == 200
        assert client.get("/api/restock-inputs").status_code == 200
        assert client.get("/api/stock").status_code == 200
        assert client.get("/api/stock/template").status_code == 200

        upload = client.post(
            "/api/stock/upload",
            files={"file": ("..\\..\\stock.csv", "store,item,current_stock\n1,1,500\n", "text/csv")},
        )
        assert upload.status_code == 200
        assert client.get("/api/stock").json()["source_filename"] == "stock.csv"
        assert client.post("/api/restock", json={}).status_code == 200
        assert client.post(
            "/api/forecast/refit",
            json={"series_id": "S1_I1", "train_end": "2017-11-30", "horizon": 30},
        ).status_code == 200
        assert client.post(
            "/api/whatif",
            json={
                "scenario": {"demand_uplift_pct": 0, "start_day": 1, "end_day": 1},
                "options": {},
            },
        ).status_code == 200
        assert client.delete("/api/stock").status_code == 200

    assert "GET /api/health 200" in caplog.text


def test_refit_rate_limit_allows_ten_and_rejects_eleven():
    for request_number in range(10):
        assert not _check_refit_rate_limit("rate-limit-test", now=100.0 + request_number)
    assert _check_refit_rate_limit("rate-limit-test", now=109.0)
    assert not _check_refit_rate_limit("rate-limit-test", now=160.0)


def test_stock_upload_rejects_non_csv_content_type():
    with TestClient(main.app) as client:
        response = client.post(
            "/api/stock/upload",
            files={"file": ("stock.csv", "store,item,current_stock\n1,1,10\n", "text/plain")},
        )
    assert response.status_code == 415
    assert set(response.json()) == {"error", "detail"}


def test_cors_allows_only_configured_origins():
    with TestClient(main.app) as client:
        allowed = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"},
        )
        denied = client.get(
            "/api/health",
            headers={"Origin": "https://untrusted.example"},
        )

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in denied.headers


def test_refit_middleware_returns_rate_limit_error(monkeypatch):
    monkeypatch.setattr(main, "_check_refit_rate_limit", lambda client_key: True)
    with TestClient(main.app) as client:
        response = client.post(
            "/api/forecast/refit",
            json={"series_id": "S1_I1", "train_end": "2017-11-30", "horizon": 30},
        )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert set(response.json()) == {"error", "detail"}


def test_store_rejects_path_traversal_series_id():
    from backend.app.store import store

    try:
        store.load_series("../manifest")
    except ValueError as exc:
        assert "Invalid series_id" in str(exc)
    else:
        raise AssertionError("Invalid series ID must not be used to build an artifact path")


def test_unhandled_exception_response_has_no_traceback():
    async def fail():
        raise RuntimeError("internal test detail")

    main.app.add_api_route("/_test/unhandled", fail, methods=["GET"])
    route = main.app.router.routes[-1]
    try:
        with TestClient(main.app, raise_server_exceptions=False) as client:
            response = client.get("/_test/unhandled")
    finally:
        main.app.router.routes.remove(route)

    assert response.status_code == 500
    assert response.json() == {
        "error": "Internal Server Error",
        "detail": "An unexpected error occurred.",
    }
    assert "internal test detail" not in response.text
