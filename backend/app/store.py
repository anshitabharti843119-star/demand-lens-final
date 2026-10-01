"""ArtifactStore: loads JSON artifacts with in-memory cache."""
import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, TypeVar

from pydantic import TypeAdapter

from .config import DATA_DIR
from .schemas import (
    Manifest, SeriesData, PortfolioRow, EdaData, RestockInput
)

T = TypeVar("T")


class ArtifactStore:
    """Loads JSON artifacts with lazy loading for series files."""
    
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self._manifest: Optional[Manifest] = None
        self._portfolio: Optional[List[PortfolioRow]] = None
        self._eda: Optional[EdaData] = None
        self._restock_inputs: Optional[Dict[str, RestockInput]] = None
        self._series_cache: Dict[str, SeriesData] = {}
    
    def _load_json(self, path: Path, adapter: TypeAdapter[T]) -> T:
        """Load JSON file with strict parsing, raise clear error if missing/invalid."""
        try:
            with path.open("r", encoding="utf-8") as artifact_file:
                data = json.load(
                    artifact_file,
                    parse_constant=self._reject_json_constant,
                    parse_float=self._parse_finite_float,
                )
            return adapter.validate_python(data)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"File not found: {path}") from exc
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Failed to load {path}: {exc}") from exc

    @staticmethod
    def _reject_json_constant(value: str) -> None:
        raise ValueError(f"Non-standard JSON number: {value}")

    @staticmethod
    def _parse_finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"Non-finite JSON number: {value}")
        return parsed
    
    def load_manifest(self) -> Manifest:
        """Load manifest.json once."""
        if self._manifest is None:
            self._manifest = self._load_json(
                self.data_dir / "manifest.json", TypeAdapter(Manifest)
            )
        return self._manifest
    
    def load_portfolio(self) -> List[PortfolioRow]:
        """Load portfolio.json once."""
        if self._portfolio is None:
            self._portfolio = self._load_json(
                self.data_dir / "portfolio.json",
                TypeAdapter(List[PortfolioRow]),
            )
        return self._portfolio
    
    def load_eda(self) -> EdaData:
        """Load eda.json once."""
        if self._eda is None:
            self._eda = self._load_json(
                self.data_dir / "eda.json", TypeAdapter(EdaData)
            )
        return self._eda
    
    def load_restock_inputs(self) -> Dict[str, RestockInput]:
        """Load restock_inputs.json once."""
        if self._restock_inputs is None:
            self._restock_inputs = self._load_json(
                self.data_dir / "restock_inputs.json",
                TypeAdapter(Dict[str, RestockInput]),
            )
        return self._restock_inputs
    
    def load_series(self, series_id: str) -> SeriesData:
        """Load series/<id>.json lazily, cache it."""
        if not self.validate_series_id(series_id):
            raise ValueError(f"Invalid series_id format: {series_id}")
        if series_id not in self._series_cache:
            path = self.data_dir / "series" / f"{series_id}.json"
            self._series_cache[series_id] = self._load_json(
                path, TypeAdapter(SeriesData)
            )
        return self._series_cache[series_id]
    
    def validate_all(self) -> List[str]:
        """Load every file and return list of problems (empty if all good)."""
        problems = []
        
        # Validate manifest
        try:
            manifest = self.load_manifest()
            if len(manifest.series_ids) != 250:
                problems.append(f"manifest.json has {len(manifest.series_ids)} series_ids, expected 250")
        except Exception as e:
            problems.append(f"manifest.json: {e}")
        
        # Validate portfolio
        try:
            portfolio = self.load_portfolio()
            if len(portfolio) != 250:
                problems.append(f"portfolio.json has {len(portfolio)} rows, expected 250")
        except Exception as e:
            problems.append(f"portfolio.json: {e}")
        
        # Validate eda
        try:
            self.load_eda()
        except Exception as e:
            problems.append(f"eda.json: {e}")
        
        # Validate restock_inputs
        try:
            restock = self.load_restock_inputs()
            if len(restock) != 250:
                problems.append(f"restock_inputs.json has {len(restock)} entries, expected 250")
        except Exception as e:
            problems.append(f"restock_inputs.json: {e}")
        
        # Validate all series files
        try:
            manifest = self.load_manifest()
            for sid in manifest.series_ids:
                try:
                    self.load_series(sid)
                except Exception as e:
                    problems.append(f"series/{sid}.json: {e}")
        except Exception as e:
            problems.append(f"Cannot validate series files: {e}")
        
        return problems
    
    def validate_series_id(self, series_id: str) -> bool:
        """Validate series_id format: S{store}_I{item}, store 1-5, item 1-50."""
        pattern = r"^S[1-5]_I([1-9]|[1-4][0-9]|50)$"
        return isinstance(series_id, str) and bool(re.fullmatch(pattern, series_id))
    
    def get_series_count(self) -> int:
        """Return total series count from manifest."""
        try:
            return len(self.load_manifest().series_ids)
        except:
            return 0
    
    def is_series_missing(self, series_id: str) -> bool:
        """Check if series exists but is not found (404 case vs 422 format case)."""
        # First validate format
        if not self.validate_series_id(series_id):
            return False  # Invalid format -> 422, not 404
        # Format is valid, check if file exists
        path = self.data_dir / "series" / f"{series_id}.json"
        return not path.exists()


# Singleton instance
store = ArtifactStore()