import os
from pathlib import Path

# Paths are anchored to the repository, independent of the launch directory.
# Repository-root path resolution is stable across working directories.
# When running tests from different dir: we need to handle both
REPO_ROOT = Path(__file__).resolve().parents[2]

# Resolve relative environment paths against the repository root.
def _repo_path(environment_variable: str, default: str) -> Path:
    configured_path = Path(os.environ.get(environment_variable, default))
    if not configured_path.is_absolute():
        configured_path = REPO_ROOT / configured_path
    return configured_path.resolve()


DATA_DIR = _repo_path("DEMANDLENS_DATA_DIR", "public/data")
RAW_CSV = _repo_path("DEMANDLENS_RAW_CSV", "pipeline/data/raw/train.csv")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DEMANDLENS_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

# State and cache directories (gitignored, per RULES.md)
STATE_DIR = REPO_ROOT / "backend" / ".state"
CACHE_DIR = REPO_ROOT / "backend" / ".cache"

# Ensure directories exist
STATE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
