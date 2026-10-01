"""Pydantic v2 models mirroring lib/types.ts exactly."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel


class Point(BaseModel):
    """ds: string; y: number"""
    ds: str
    y: float


class ForecastPoint(BaseModel):
    """ds: string; yhat: number; yhat_lower: number; yhat_upper: number"""
    ds: str
    yhat: float
    yhat_lower: float
    yhat_upper: float


class BaselinePoint(BaseModel):
    """ds: string; yhat: number"""
    ds: str
    yhat: float


class ErrorMetrics(BaseModel):
    """mape: number; rmse: number"""
    mape: float
    rmse: float


class HorizonMetrics(BaseModel):
    """model: ErrorMetrics; baseline: ErrorMetrics; seasonal_naive?: ErrorMetrics"""
    model: ErrorMetrics
    baseline: ErrorMetrics
    seasonal_naive: Optional[ErrorMetrics] = None


class Backtest(BaseModel):
    """actual: Point[]; model: ForecastPoint[]; baseline: BaselinePoint[]; seasonal_naive?: BaselinePoint[]"""
    actual: List[Point]
    model: List[ForecastPoint]
    baseline: List[BaselinePoint]
    seasonal_naive: Optional[List[BaselinePoint]] = None


class Future(BaseModel):
    """model: ForecastPoint[]"""
    model: List[ForecastPoint]


class Metrics(BaseModel):
    """h14: HorizonMetrics; h30: HorizonMetrics; coverage_80: number; winner: "model"|"baseline" """
    h14: HorizonMetrics
    h30: HorizonMetrics
    coverage_80: float
    winner: Literal["model", "baseline"]


class SeriesData(BaseModel):
    """Full SeriesData from lib/types.ts"""
    schema_version: Literal[1]
    series_id: str
    store: int
    item: int
    history: List[Point]
    backtest: Backtest
    future: Future
    metrics: Metrics


class RestockInput(BaseModel):
    """store: number; item: number; current_stock: number; avg_daily_28: number; sigma_daily: number; yhat_future: number[]"""
    store: int
    item: int
    current_stock: float
    avg_daily_28: float
    sigma_daily: float
    yhat_future: List[float]


class RestockRow(BaseModel):
    """series_id: string; store: number; item: number; current_stock: number; forecast_demand: number; safety_stock: number; restock_qty: number; days_of_cover: number; priority: "HIGH"|"MEDIUM"|"LOW" """
    series_id: str
    store: int
    item: int
    current_stock: float
    forecast_demand: float
    safety_stock: float
    restock_qty: int
    days_of_cover: float
    priority: Literal["HIGH", "MEDIUM", "LOW"]


class RestockSummary(BaseModel):
    total_products: int
    total_units: int
    high_priority: int
    avg_days_of_cover: float


class RestockResponse(BaseModel):
    rows: List[RestockRow]
    summary: RestockSummary
    stock_source: Optional[str] = None


class RefitMetrics(BaseModel):
    model: ErrorMetrics
    baseline: ErrorMetrics


class ForecastRefitResponse(BaseModel):
    series_id: str
    train_end: str
    horizon: int
    forecast: List[ForecastPoint]
    actual: List[Point]
    metrics: Optional[RefitMetrics] = None
    fit_seconds: float
    cached: bool
    params: Dict[str, Any]


class WhatIfTopChange(BaseModel):
    series_id: str
    qty_before: int
    qty_after: int
    priority_before: Literal["HIGH", "MEDIUM", "LOW"]
    priority_after: Literal["HIGH", "MEDIUM", "LOW"]


class WhatIfDelta(BaseModel):
    total_units_change: int
    products_changing_priority: int
    top_changes: List[WhatIfTopChange]


class WhatIfResult(BaseModel):
    rows: List[RestockRow]
    summary: RestockSummary


class WhatIfResponse(BaseModel):
    baseline: WhatIfResult
    scenario: WhatIfResult
    delta: WhatIfDelta
    disclaimer: str
    stock_source: Optional[str] = None


class PortfolioRow(BaseModel):
    """series_id: string; store: number; item: number; model_mape: number; baseline_mape: number; improvement_pct: number; winner: "model"|"baseline" """
    series_id: str
    store: int
    item: int
    model_mape: float
    baseline_mape: float
    improvement_pct: float
    winner: Literal["model", "baseline"]


class MonthlyTotal(BaseModel):
    """month: string; sales: number; rolling_12m?: number"""
    month: str
    sales: float
    rolling_12m: Optional[float] = None


class WeekdayAvg(BaseModel):
    """store: number; dow: 0-6; avg_sales: number"""
    store: int
    dow: Literal[0, 1, 2, 3, 4, 5, 6]
    avg_sales: float


class WeekendVsWeekday(BaseModel):
    """store: number; weekday_avg: number; weekend_avg: number"""
    store: int
    weekday_avg: float
    weekend_avg: float


class MonthYearHeatmap(BaseModel):
    """year: number; month: number; avg_sales: number"""
    year: int
    month: int
    avg_sales: float


class EdaData(BaseModel):
    """Full EdaData from lib/types.ts"""
    monthly_total: List[MonthlyTotal]
    weekday_avg: List[WeekdayAvg]
    weekend_vs_weekday: List[WeekendVsWeekday]
    month_year_heatmap: Optional[List[MonthYearHeatmap]] = None
    by_store: Optional[Dict[int, EdaData]] = None


class Manifest(BaseModel):
    """stores: number[]; items: number[]; series_ids: string[]; train_end: string; test_start: string; test_end: string; future_end: string"""
    stores: List[int]
    items: List[int]
    series_ids: List[str]
    train_end: str
    test_start: str
    test_end: str
    future_end: str