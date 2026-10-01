"""Python port of computeRestock from lib/restock.ts.

Matches the TypeScript implementation exactly:
- Same z-values (0.9->1.28, 0.95->1.65, 0.99->2.33)
- Full calculation precision; the pipeline CSV rounds display fields only
- Same priority thresholds (HIGH if DoC < lead_time, MEDIUM if DoC < horizon, else LOW)
- Zero-demand cover is capped at 1e9 because strict JSON cannot contain Infinity

Formulas:
  D = sum(yhat_future[:H])              # forecast_demand
  SS = z * sigma_daily * sqrt(lead_time) # safety_stock
  R = D + SS
  Q = max(0, ceil(R - current_stock * stock_multiplier)) # restock_qty
  DoC = current_stock * multiplier / mean(yhat[:H])      # days_of_cover
  priority: HIGH if DoC < lead_time, MEDIUM if DoC < H, else LOW
"""

import math
from typing import Optional, List

from .store import store
from .schemas import RestockInput, RestockRow


# Z-scores matching TypeScript
Z_SCORES = {0.9: 1.28, 0.95: 1.65, 0.99: 2.33}

# Cap for days_of_cover to avoid Infinity in JSON
# TypeScript uses Infinity for doC = 0 case; we cap at a large number
MAX_DAYS_OF_COVER = 1e9


def _round2(x: float) -> float:
    """Round a display value to two decimal places."""
    return round(float(x), 2)


def compute_restock(
    inputs: dict[str, RestockInput],
    horizon: int,
    service_level: float,
    lead_time: int,
    stock_multiplier: float
) -> List[RestockRow]:
    """Compute restock rows matching TypeScript computeRestock exactly."""
    # Validate inputs match TypeScript validation
    if horizon not in (14, 30):
        raise ValueError(f"Invalid horizon: {horizon}. Must be 14 or 30.")
    if service_level not in Z_SCORES:
        raise ValueError(f"Invalid service_level: {service_level}. Must be 0.9, 0.95, or 0.99.")
    if isinstance(lead_time, bool) or not isinstance(lead_time, int) or not 1 <= lead_time <= 14:
        raise ValueError(f"Invalid lead_time: {lead_time}. Must be an integer from 1 to 14.")
    if not math.isfinite(stock_multiplier) or not 0.5 <= stock_multiplier <= 2.0:
        raise ValueError(f"Invalid stock_multiplier: {stock_multiplier}. Must be between 0.5 and 2.0.")
    
    z_score = Z_SCORES[service_level]
    sqrt_lead_time = math.sqrt(lead_time)
    
    rows = []
    
    for series_id, input_data in inputs.items():
        # Validate input matches TypeScript validation
        current_stock = input_data.current_stock * stock_multiplier
        if not math.isfinite(current_stock) or current_stock < 0:
            raise ValueError(f"Invalid current_stock for {series_id}")
        
        # Validate sigma_daily is non-negative
        if not math.isfinite(input_data.sigma_daily) or input_data.sigma_daily < 0:
            raise ValueError(f"Invalid sigma_daily for {series_id}")
        
        # Validate yhat_future has enough elements
        if len(input_data.yhat_future) < horizon:
            raise ValueError(f"yhat_future too short for {series_id}")
        
        # Validate all yhat_future values are non-negative
        for i, yhat in enumerate(input_data.yhat_future[:horizon]):
            if not math.isfinite(yhat) or yhat < 0:
                raise ValueError(f"Negative yhat_future[{i}] for {series_id}")
        
        forecast_demand = sum(input_data.yhat_future[:horizon])
        safety_stock = z_score * input_data.sigma_daily * sqrt_lead_time
        if not math.isfinite(forecast_demand) or not math.isfinite(safety_stock):
            raise ValueError(f"Non-finite restock calculation for {series_id}")
        restock_qty = math.ceil(forecast_demand + safety_stock - current_stock)
        restock_qty = max(0, restock_qty)
        
        if forecast_demand > 0:
            days_of_cover = current_stock / (forecast_demand / horizon)
        else:
            days_of_cover = MAX_DAYS_OF_COVER

        if days_of_cover < lead_time:
            priority = "HIGH"
        elif days_of_cover < horizon:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        
        rows.append(RestockRow(
            series_id=series_id,
            store=input_data.store,
            item=input_data.item,
            current_stock=current_stock,
            forecast_demand=forecast_demand,
            safety_stock=safety_stock,
            restock_qty=restock_qty,
            days_of_cover=days_of_cover,
            priority=priority
        ))
    
    # Sort by days_of_cover ascending, then by series_id for stable sort
    rows.sort(key=lambda r: (r.days_of_cover, r.series_id))
    
    return rows


def summarize_restock(rows: List[RestockRow]) -> dict:
    """Compute summary matching TypeScript summarizeRestock."""
    total_products = len(rows)
    total_units = sum(row.restock_qty for row in rows)
    high_priority = sum(1 for row in rows if row.priority == "HIGH")
    
    if total_products > 0:
        avg_days_of_cover = sum(row.days_of_cover for row in rows) / total_products
    else:
        avg_days_of_cover = 0.0
    
    return {
        "total_products": total_products,
        "total_units": total_units,
        "high_priority": high_priority,
        "avg_days_of_cover": avg_days_of_cover
    }


def filter_restock(
    rows: List[RestockRow],
    store_filter: Optional[int] = None,
    priority_filter: Optional[str] = None,
    only_restock: bool = False
) -> List[RestockRow]:
    """Filter restock rows matching TypeScript filterSortRestock (without sorting)."""
    result = rows
    
    # Filter by store
    if store_filter is not None:
        result = [r for r in result if r.store == store_filter]
    
    # Filter by priority
    if priority_filter is not None:
        result = [r for r in result if r.priority == priority_filter]
    
    # Filter only restock (restock_qty > 0)
    if only_restock:
        result = [r for r in result if r.restock_qty > 0]
    
    return result


def load_restock_inputs() -> dict[str, RestockInput]:
    """Load restock inputs from data layer."""
    return store.load_restock_inputs()
