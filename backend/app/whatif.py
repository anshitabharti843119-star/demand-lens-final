"""Scenario analysis on top of existing forecasts for POST /api/whatif.

No new modelling: scales existing yhat and recomputes restock.
"""

from typing import Optional, List, Dict

from .restock import (
    compute_restock, summarize_restock, filter_restock, load_restock_inputs,
    Z_SCORES,
)
from .store import store
from .stock import get_stock_state, get_stock_source_info
from .schemas import RestockInput, RestockRow


DISCLAIMER = "Scenario scales the existing forecast; it is not a re-trained model."


def compute_scenario_restock(
    inputs: Dict[str, RestockInput],
    horizon: int,
    service_level: float,
    lead_time: int,
    stock_multiplier: float,
    demand_uplift_pct: float,
    start_day: int,
    end_day: int
) -> List[RestockRow]:
    """
    Compute restock with demand scenario applied.
    
    Scales yhat_future for days start_day..end_day by (1 + uplift/100).
    Also scales sigma_daily by the same factor (average over the horizon).
    """
    if horizon not in (14, 30):
        raise ValueError(f"Invalid horizon: {horizon}. Must be 14 or 30.")
    if service_level not in Z_SCORES:
        raise ValueError(f"Invalid service_level: {service_level}. Must be 0.9, 0.95, or 0.99.")
    if isinstance(lead_time, bool) or not isinstance(lead_time, int) or not 1 <= lead_time <= 14:
        raise ValueError(f"Invalid lead_time: {lead_time}. Must be an integer from 1 to 14.")
    if not 0.5 <= stock_multiplier <= 2.0:
        raise ValueError(f"Invalid stock_multiplier: {stock_multiplier}. Must be between 0.5 and 2.0.")
    if demand_uplift_pct < -50 or demand_uplift_pct > 200:
        raise ValueError(f"Invalid demand_uplift_pct: {demand_uplift_pct}. Must be -50..200.")
    if start_day < 1 or start_day > 30:
        raise ValueError(f"Invalid start_day: {start_day}. Must be 1..30.")
    if end_day < 1 or end_day > 30:
        raise ValueError(f"Invalid end_day: {end_day}. Must be 1..30.")
    if start_day > end_day:
        raise ValueError(f"start_day ({start_day}) > end_day ({end_day})")
    
    uplift_factor = 1.0 + demand_uplift_pct / 100.0
    adjusted_inputs: Dict[str, RestockInput] = {}

    for series_id, input_data in inputs.items():
        yhat_future = list(input_data.yhat_future)
        if len(yhat_future) < horizon:
            raise ValueError(f"yhat_future too short for {series_id}")

        selected_end = min(end_day, horizon)
        selected_days = max(0, selected_end - start_day + 1)
        for index in range(start_day - 1, selected_end):
            yhat_future[index] *= uplift_factor
        average_factor = 1 + (uplift_factor - 1) * selected_days / horizon
        adjusted_inputs[series_id] = input_data.model_copy(
            update={
                "yhat_future": yhat_future,
                "sigma_daily": input_data.sigma_daily * average_factor,
            }
        )

    return compute_restock(
        adjusted_inputs,
        horizon,
        service_level,
        lead_time,
        stock_multiplier,
    )


def compute_whatif(
    scenario: dict,
    options: dict,
    series_id_filter: Optional[str] = None,
    use_uploaded_stock: bool = False
) -> dict:
    """
    Compute what-if scenario analysis.
    
    Args:
        scenario: {demand_uplift_pct, start_day, end_day}
        options: {horizon, service_level, lead_time, stock_multiplier, store?, priority?, only_restock?}
        series_id_filter: Optional series_id filter
        use_uploaded_stock: If True, use uploaded stock for series that have it
    
    Returns:
        {
            baseline: {rows, summary},
            scenario: {rows, summary},
            delta: {
                total_units_change,
                products_changing_priority: int,
                top_changes: [...]
            },
            disclaimer: str
        }
    """
    # Validate scenario parameters
    demand_uplift_pct = scenario.get("demand_uplift_pct", 0)
    start_day = scenario.get("start_day", 1)
    end_day = scenario.get("end_day", 30)
    
    horizon = options.get("horizon", 30)
    service_level = options.get("service_level", 0.95)
    lead_time = options.get("lead_time", 3)
    stock_multiplier = options.get("stock_multiplier", 1.0)
    store_filter = options.get("store")
    priority_filter = options.get("priority")
    only_restock = options.get("only_restock", False)
    
    # Load inputs
    inputs = load_restock_inputs()
    
    # If using uploaded stock, override current_stock
    if use_uploaded_stock:
        state = get_stock_state()
        if state:
            for sid, stock in state.rows.items():
                if sid in inputs:
                    inputs[sid] = inputs[sid].model_copy(
                        update={"current_stock": stock}
                    )
    
    # Filter to specific series if requested
    if series_id_filter:
        if series_id_filter not in inputs:
            raise ValueError(f"Series not found: {series_id_filter}")
        inputs = {series_id_filter: inputs[series_id_filter]}
    
    # Compute baseline
    baseline_rows = compute_restock(inputs, horizon, service_level, lead_time, stock_multiplier)
    
    # Apply filters to baseline
    baseline_rows = filter_restock(baseline_rows, store_filter, priority_filter, only_restock)
    
    scenario_rows = compute_scenario_restock(
        inputs, horizon, service_level, lead_time, stock_multiplier,
        demand_uplift_pct, start_day, end_day
    )
    
    # Apply filters to scenario (same filters)
    scenario_rows = filter_restock(scenario_rows, store_filter, priority_filter, only_restock)
    
    # Compute summaries
    baseline_summary = summarize_restock(baseline_rows)
    scenario_summary = summarize_restock(scenario_rows)
    
    # Compute delta
    total_units_change = scenario_summary["total_units"] - baseline_summary["total_units"]
    
    baseline_map = {r.series_id: r for r in baseline_rows}
    scenario_map = {r.series_id: r for r in scenario_rows}
    products_changing_priority = sum(
        1 for sid, before in baseline_map.items()
        if sid in scenario_map and before.priority != scenario_map[sid].priority
    )
    
    # Find top 10 changes (greatest absolute change in restock_qty)
    changes = []
    for sid in baseline_map.keys() & scenario_map.keys():
        b_row = baseline_map[sid]
        s_row = scenario_map[sid]
        qty_change = s_row.restock_qty - b_row.restock_qty
        if qty_change == 0 and s_row.priority == b_row.priority:
            continue
        changes.append({
            "series_id": b_row.series_id,
            "qty_before": b_row.restock_qty,
            "qty_after": s_row.restock_qty,
            "priority_before": b_row.priority,
            "priority_after": s_row.priority,
            "qty_change": qty_change
        })
    
    # Sort by absolute change descending, take top 10
    changes.sort(key=lambda c: (-abs(c["qty_change"]), c["series_id"]))
    top_changes = [
        {
            "series_id": c["series_id"],
            "qty_before": c["qty_before"],
            "qty_after": c["qty_after"],
            "priority_before": c["priority_before"],
            "priority_after": c["priority_after"]
        }
        for c in changes[:10]
    ]
    
    # Determine stock source info
    relevant_series = {
        row.series_id for row in baseline_rows + scenario_rows
    }
    stock_source, _ = get_stock_source_info(
        use_uploaded_stock,
        list(relevant_series),
    )
    
    return {
        "baseline": {"rows": baseline_rows, "summary": baseline_summary},
        "scenario": {"rows": scenario_rows, "summary": scenario_summary},
        "delta": {
            "total_units_change": total_units_change,
            "products_changing_priority": products_changing_priority,
            "top_changes": top_changes
        },
        "disclaimer": DISCLAIMER,
        "stock_source": stock_source
    }
