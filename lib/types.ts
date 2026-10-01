export type Horizon = 14 | 30
export type Mode = "backtest" | "future"

export interface Point { ds: string; y: number }
export interface ForecastPoint { ds: string; yhat: number; yhat_lower: number; yhat_upper: number }
export interface BaselinePoint { ds: string; yhat: number }
export interface ErrorMetrics { mape: number; rmse: number }
export interface HorizonMetrics { model: ErrorMetrics; baseline: ErrorMetrics; seasonal_naive?: ErrorMetrics }

export interface SeriesData {
  schema_version: 1
  series_id: string
  store: number
  item: number
  history: Point[]
  backtest: {
    actual: Point[]
    model: ForecastPoint[]
    baseline: BaselinePoint[]
    seasonal_naive?: BaselinePoint[]
  }
  future: { model: ForecastPoint[] }
  metrics: {
    h14: HorizonMetrics
    h30: HorizonMetrics
    coverage_80: number
    winner: "model" | "baseline"
  }
}

export interface RestockInput {
  store: number
  item: number
  current_stock: number
  avg_daily_28: number
  sigma_daily: number
  yhat_future: number[]
}

export interface RestockRow {
  series_id: string
  store: number
  item: number
  current_stock: number
  forecast_demand: number
  safety_stock: number
  restock_qty: number
  days_of_cover: number
  priority: "HIGH" | "MEDIUM" | "LOW"
}

export interface PortfolioRow {
  series_id: string
  store: number
  item: number
  model_mape: number
  baseline_mape: number
  improvement_pct: number
  winner: "model" | "baseline"
}

export interface EdaData {
  monthly_total: { month: string; sales: number; rolling_12m?: number }[]
  weekday_avg: { store: number; dow: 0 | 1 | 2 | 3 | 4 | 5 | 6; avg_sales: number }[]
  weekend_vs_weekday: { store: number; weekday_avg: number; weekend_avg: number }[]
  month_year_heatmap?: { year: number; month: number; avg_sales: number }[]
  // Optional breakdown keeps store filtering exact without changing getEda()'s signature.
  by_store?: Record<number, EdaData>
}
