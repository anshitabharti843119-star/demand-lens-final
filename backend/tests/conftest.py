import pytest

from backend.app.main import _refit_requests, _refit_requests_lock


@pytest.fixture(autouse=True)
def reset_refit_rate_limit():
    """Keep each test independent of prior requests from the shared test client."""
    with _refit_requests_lock:
        _refit_requests.clear()
