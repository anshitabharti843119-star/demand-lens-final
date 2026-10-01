"""Stock management for POST /api/stock endpoints.

User can upload real current stock CSV, which takes precedence over simulated stock.
"""

import json
import csv
import io
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading

from pydantic import BaseModel

from .config import STATE_DIR
from .store import store
from .schemas import RestockInput


# Stock state structure
class StockRow(BaseModel):
    """Uploaded stock row"""
    series_id: str
    store: int
    item: int
    current_stock: float


class StockState(BaseModel):
    """Current stock state"""
    uploaded_at: str
    source_filename: str
    rows: Dict[str, float]
    row_count: int


# State directory
STATE_DIR.mkdir(parents=True, exist_ok=True)
STOCK_STATE_FILE = STATE_DIR / "stock.json"

# Lock for thread-safe access
_lock = threading.Lock()


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def _load_state() -> Optional[StockState]:
    """Load stock state from file."""
    if not STOCK_STATE_FILE.exists():
        return None
    try:
        with STOCK_STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f, parse_constant=_reject_json_constant)
        return StockState(**data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid persisted stock state at {STOCK_STATE_FILE}: {exc}") from exc


def _save_state(state: StockState) -> None:
    """Save stock state to file."""
    with STOCK_STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state.model_dump(), f, separators=(",", ":"), allow_nan=False)


def get_stock_state() -> Optional[StockState]:
    """Get current stock state (thread-safe)."""
    with _lock:
        return _load_state()


def clear_stock_state() -> None:
    """Clear stock state (thread-safe)."""
    with _lock:
        if STOCK_STATE_FILE.exists():
            STOCK_STATE_FILE.unlink()


def is_stock_active() -> bool:
    """Check if stock upload is active."""
    return get_stock_state() is not None


def get_uploaded_stock(series_id: str) -> Optional[float]:
    """Get uploaded stock for a series, or None if not uploaded."""
    state = get_stock_state()
    if state and series_id in state.rows:
        return state.rows[series_id]
    return None


def parse_stock_csv(csv_content: str, filename: str) -> tuple[List[StockRow], List[Dict[str, Any]]]:
    """
    Parse uploaded stock CSV.
    
    Returns:
        (valid_rows, errors)
        - valid_rows: list of validated StockRow
        - errors: list of {line, message}
    """
    if not csv_content.strip():
        return [], [{"line": 0, "message": "Empty file"}]

    reader = csv.reader(io.StringIO(csv_content, newline=""), strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error):
        return [], [{"line": 1, "message": "Missing or invalid CSV header"}]

    header_parts = [value.strip().lstrip("\ufeff").casefold() for value in header]
    required_columns = ("store", "item", "current_stock")
    indexes = {
        name: header_parts.index(name)
        for name in required_columns
        if name in header_parts
    }
    errors = [
        {"line": 1, "message": f"Missing '{name}' column"}
        for name in required_columns
        if name not in indexes
    ]
    if errors:
        return [], errors

    valid_rows: List[StockRow] = []
    seen_pairs = set()
    parsed_rows = 0

    try:
        for parts in reader:
            line_num = reader.line_num
            if not parts or all(not value.strip() for value in parts):
                continue

            parsed_rows += 1
            row_errors: List[str] = []
            if parsed_rows > 250:
                row_errors.append("CSV may contain at most 250 data rows")

            missing_indexes = [name for name, idx in indexes.items() if idx >= len(parts)]
            if missing_indexes:
                row_errors.append("Missing value(s) for " + ", ".join(missing_indexes))
                errors.extend(
                    {"line": line_num, "message": message}
                    for message in row_errors
                )
                continue

            store_value = parts[indexes["store"]].strip()
            item_value = parts[indexes["item"]].strip()
            stock_value = parts[indexes["current_stock"]].strip()
            store_num: Optional[int] = None
            item_num: Optional[int] = None

            try:
                store_num = int(store_value)
                if not 1 <= store_num <= 5:
                    row_errors.append(f"store must be 1-5, got {store_num}")
            except ValueError:
                row_errors.append(f"store must be an integer, got '{store_value}'")

            try:
                item_num = int(item_value)
                if not 1 <= item_num <= 50:
                    row_errors.append(f"item must be 1-50, got {item_num}")
            except ValueError:
                row_errors.append(f"item must be an integer, got '{item_value}'")

            try:
                current_stock = float(stock_value)
                if not math.isfinite(current_stock) or current_stock < 0:
                    row_errors.append("'current_stock' must be a finite number >= 0")
            except ValueError:
                current_stock = 0.0
                row_errors.append(f"'current_stock' must be numeric, got '{stock_value}'")

            if store_num is not None and item_num is not None:
                pair_key = (store_num, item_num)
                if pair_key in seen_pairs:
                    row_errors.append(f"Duplicate (store, item): ({store_num}, {item_num})")
                else:
                    seen_pairs.add(pair_key)

            if row_errors:
                errors.extend(
                    {"line": line_num, "message": message}
                    for message in row_errors
                )
                continue

            valid_rows.append(StockRow(
                series_id=f"S{store_num}_I{item_num}",
                store=store_num,
                item=item_num,
                current_stock=current_stock,
            ))
    except csv.Error as exc:
        errors.append({"line": reader.line_num, "message": f"Invalid CSV: {exc}"})

    return valid_rows, errors


def process_stock_upload(csv_content: str, filename: str) -> StockState:
    """
    Process uploaded stock CSV and save state.
    
    Returns:
        StockState with rows
    """
    valid_rows, errors = parse_stock_csv(csv_content, filename)
    
    if errors:
        # Return first 20 errors
        raise ValueError([{"line": e["line"], "message": e["message"]} for e in errors[:20]])
    
    # Build rows dict
    rows = {r.series_id: r.current_stock for r in valid_rows}
    
    # Create state
    state = StockState(
        uploaded_at=datetime.utcnow().isoformat() + "Z",
        source_filename=filename,
        rows=rows,
        row_count=len(valid_rows)
    )
    
    # Save state
    with _lock:
        _save_state(state)
    
    return state


def get_stock_state_with_count() -> tuple[Optional[StockState], int, int]:
    """
    Get stock state with additional info.
    
    Returns:
        (state, accepted_rows, missing_series_count)
    """
    state = get_stock_state()
    if not state:
        return None, 0, 0
    
    # Missing catalog entries fall back to their simulated stock values.
    manifest = store.load_manifest()
    manifest_series = set(manifest.series_ids)
    missing_count = len(manifest_series - set(state.rows))

    return state, state.row_count, missing_count


def get_stock_source_info(
    use_uploaded_stock: bool = False,
    series_ids: Optional[List[str]] = None,
) -> tuple[str, int]:
    """
    Get stock source info for response.
    
    Returns:
        (source_type, uploaded_count)
        - "uploaded": every relevant series has uploaded stock
        - "simulated": upload is disabled or no relevant series has uploaded stock
        - "mixed (N uploaded)": only some relevant series have uploaded stock
    """
    state = get_stock_state() if use_uploaded_stock else None
    if not state:
        return "simulated", 0

    relevant_series = set(series_ids) if series_ids is not None else set(store.load_manifest().series_ids)
    uploaded_count = sum(1 for sid in relevant_series if sid in state.rows)
    if not relevant_series or uploaded_count == 0:
        return "simulated", 0
    if uploaded_count == len(relevant_series):
        return "uploaded", uploaded_count
    return f"mixed ({uploaded_count} uploaded)", uploaded_count


def get_template_csv() -> str:
    """
    Get CSV template with all 250 series and simulated stock values.
    
    Returns:
        CSV string with headers: store,item,current_stock
    """
    manifest = store.load_manifest()
    restock_inputs = store.load_restock_inputs()
    
    lines = ["store,item,current_stock"]
    
    for sid in sorted(manifest.series_ids):
        # Parse using regex to avoid parsing bugs
        match = re.match(r"^S([1-5])_I([1-9]|[1-4][0-9]|50)$", sid)
        if match:
            store_num = int(match.group(1))
            item_num = int(match.group(2))
            current_stock = restock_inputs[sid].current_stock
            lines.append(f"{store_num},{item_num},{current_stock}")
    
    return "\n".join(lines)
